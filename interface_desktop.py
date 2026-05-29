#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CONVERSOR CONTÁBIL - INTERFACE GRÁFICA
Sistema de Conversão de Lançamentos para Empresa Consorciada

FUNCIONALIDADES:
- Interface gráfica dark theme profissional
- Conversão de lançamentos com percentual de participação
- Cadastros rápidos de consorciadas
- Sistema de memorização de contas de arredondamento
- Processamento em lote de múltiplos arquivos
- Garantia de fechamento 100% em 13 contas prioritárias
- Fechamento perfeito de todas as sequências (D=C)
- Ajuste automático de arredondamento

ARQUITETURA:
- interface_desktop.py (ESTE): Interface gráfica + controle
- motor_conversao_contabil.py: Motor de conversão e cálculos
- config.py: 13 contas sagradas (não modificar)
- cadastros.json: Persistência de cadastros

USO:
    python interface_desktop.py
    ou
    Clicar em INICIAR.bat
"""

import tkinter as tk
from tkinter import filedialog
from pathlib import Path
import threading
import os
import sys
import json
import re
import customtkinter as ctk
import pandas as pd
from PIL import Image, ImageTk

from camadas.persistencia import CadastrosRepository
from camadas.servico import ConversorAppService
from erros import CadastroErro, ConfiguracaoErro, ConversaoErro, PersistenciaErro
from observabilidade import get_logger, log_event


APP_DISPLAY_NAME = "Conversor Contabil"
APP_DATA_FOLDER = "Data"
DEFAULT_ACCOUNT_SUBSTITUTIONS = [
    {"de": "3.6.03.03.000002", "para": "1.1.11.04.000005"},
]
DEFAULT_INPUT_LAYOUTS = [
    {"nome": "Fiscal", "termos": ["fiscal"]},
    {"nome": "Societario", "termos": ["19", "42", "ajuste societario", "societario"]},
]


def get_runtime_base_dir():
    """Retorna a pasta persistente da aplicação."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_user_data_dir() -> Path:
    """Retorna a pasta estável de dados do usuário para instalações empacotadas."""
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / APP_DISPLAY_NAME / APP_DATA_FOLDER
    return Path.home() / "AppData" / "Local" / APP_DISPLAY_NAME / APP_DATA_FOLDER


def get_bundle_base_dir():
    """Retorna a pasta de recursos embutidos quando empacotado."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def get_resource_path(*parts):
    """Monta o caminho de um recurso do app."""
    return get_bundle_base_dir().joinpath(*parts)


def resolve_cadastros_file() -> Path:
    """Resolve o arquivo de cadastros priorizando configuração local."""
    override = os.environ.get("CONVERSOR_CADASTROS_FILE")
    if override:
        return Path(override).expanduser()

    if getattr(sys, 'frozen', False):
        return get_user_data_dir() / "cadastros.local.json"

    base_dir = get_runtime_base_dir()
    local_file = base_dir / "cadastros.local.json"
    if local_file.exists():
        return local_file

    return base_dir / "cadastros.json"


def get_legacy_cadastros_candidates() -> list[Path]:
    """Lista fontes legadas para migracao no primeiro uso da versao nova."""
    base_dir = get_runtime_base_dir()
    candidates = [
        base_dir / "cadastros.local.json",
        base_dir / "cadastros.json",
    ]
    unique_candidates: list[Path] = []
    for candidate in candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return unique_candidates

class TelaConversor:
    def __init__(self, root):
        self.root = root
        self.palette = {}
        self._mask_updating = False
        self.root.title("Conversor Contábil - Empresa Consorciada")
        self.root.geometry("900x750")
        self.root.resizable(True, True)
        
        # Cache de arquivo de cadastros
        self.base_dir = get_runtime_base_dir()
        self.cadastros_file = resolve_cadastros_file()
        self.repository = CadastrosRepository(self.cadastros_file)
        self.service = ConversorAppService(self.repository)
        self.logger = get_logger(__name__)
        self.log_text = None
        self._ensure_app_dirs()
        self._ensure_cadastros_file()
        self._loading_anim_job = None
        self._loading_phase = 0
        self._loading_text = "LOADING"
        self._converter_anim_job = None
        self._converter_anim_phase = 0
        self.input_dir = str(self.base_dir / "entrada")
        self.output_dir = str(self.base_dir / "saida")
        self.account_substitutions = [dict(item) for item in DEFAULT_ACCOUNT_SUBSTITUTIONS]
        self.input_layouts = [
            {"nome": item["nome"], "termos": list(item["termos"])}
            for item in DEFAULT_INPUT_LAYOUTS
        ]
        self.selected_input_file = ""
        self.file_name_var = tk.StringVar(value="Arquivo: --")
        self.sheet_name_var = tk.StringVar(value="Planilha: --")
        self._selected_sheet_by_file: dict[str, str] = {}
        self._selected_sheet_history: set[tuple[str, str]] = set()
        
        # Estilo Dark
        self._setup_dark_theme()
        self._load_folder_settings()
        
        self._create_widgets()
        self._load_cadastros()
        self._mostrar_boas_vindas()
    
    def _setup_dark_theme(self):
        """Configura tema visual moderno com CustomTkinter."""
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.palette = {
            "bg_principal": "#08131f",
            "bg_frames": "#122338",
            "bg_input": "#1a3556",
            "fg_light": "#e6edf5",
            "accent": "#31f0ff",
            "accent_hover": "#18d9ea",
            "converter_bg": "#2adfed",
            "converter_hover": "#20d2e2",
            "converter_border": "#9bf7ff",
            "button_text": "#062336",
            "muted": "#9fb0c4",
        }
        self.font_title = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        self.font_body = ctk.CTkFont(family="Segoe UI", size=12)
        self.font_mono = ctk.CTkFont(family="Consolas", size=11)
        self.font_button = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        self.root.configure(fg_color=self.palette["bg_principal"])

    def _get_app_base_dir(self):
        """Retorna a pasta base do app (suporta modo empacotado)"""
        return get_runtime_base_dir()

    def _ensure_cadastros_file(self):
        """Garante um arquivo de cadastros persistente no local apropriado da instalação."""
        bundled_file = get_resource_path("cadastros.json")
        self.repository.ensure_file_exists(
            bundled_file,
            migration_candidates=get_legacy_cadastros_candidates(),
        )

    def _ensure_app_dirs(self):
        """Garante que pastas essenciais existam"""
        for pasta in ("entrada", "saida"):
            (self.base_dir / pasta).mkdir(parents=True, exist_ok=True)

    def _settings_file_path(self) -> Path:
        if getattr(sys, 'frozen', False):
            return get_user_data_dir() / "interface.settings.json"
        return self.base_dir / "interface.settings.local.json"

    def _load_folder_settings(self) -> None:
        settings_file = self._settings_file_path()
        try:
            if settings_file.exists():
                data = json.loads(settings_file.read_text(encoding="utf-8"))
                entrada = str(data.get("entrada", "")).strip()
                saida = str(data.get("saida", "")).strip()
                if entrada:
                    self.input_dir = entrada
                if saida:
                    self.output_dir = saida

                substituicoes = data.get("substituicoes_conta", [])
                substituicoes_validas = []
                if isinstance(substituicoes, list):
                    for item in substituicoes:
                        if not isinstance(item, dict):
                            continue
                        origem = self._format_account_value(str(item.get("de", "")).strip())
                        destino = self._format_account_value(str(item.get("para", "")).strip())
                        if self._is_valid_account(origem) and self._is_valid_account(destino):
                            substituicoes_validas.append({"de": origem, "para": destino})
                if substituicoes_validas:
                    self.account_substitutions = substituicoes_validas

                layouts = data.get("layouts_entrada", [])
                layouts_validos = self._sanitize_input_layouts(layouts)
                if layouts_validos:
                    self.input_layouts = layouts_validos
        except (OSError, ValueError, TypeError):
            # Se o arquivo estiver inválido, mantém os padrões sem interromper a UI.
            pass

    def _save_folder_settings(self) -> None:
        settings_file = self._settings_file_path()
        payload = {
            "entrada": self.input_dir,
            "saida": self.output_dir,
            "substituicoes_conta": self.account_substitutions,
            "layouts_entrada": self.input_layouts,
        }
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _sanitize_input_layouts(self, layouts) -> list[dict[str, list[str]]]:
        sane_layouts = []
        seen_names = set()
        if not isinstance(layouts, list):
            return sane_layouts

        for raw_layout in layouts:
            if not isinstance(raw_layout, dict):
                continue

            nome = str(raw_layout.get("nome", "")).strip()
            if not nome:
                continue

            raw_terms = raw_layout.get("termos", [])
            if isinstance(raw_terms, str):
                terms_list = [part.strip() for part in re.split(r"[;,\n]+", raw_terms) if part.strip()]
            elif isinstance(raw_terms, list):
                terms_list = [str(part).strip() for part in raw_terms if str(part).strip()]
            else:
                terms_list = []

            dedup_terms = []
            seen_terms = set()
            for term in terms_list:
                normalized = term.casefold()
                if normalized in seen_terms:
                    continue
                seen_terms.add(normalized)
                dedup_terms.append(term)

            if not dedup_terms:
                continue

            normalized_name = nome.casefold()
            if normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)
            sane_layouts.append({"nome": nome, "termos": dedup_terms})

        return sane_layouts

    def _validate_account_substitution(self, origem: str, destino: str) -> tuple[bool, str]:
        if not self._is_valid_account(origem) or not self._is_valid_account(destino):
            return False, "Formato de conta incorreto"
        if origem == destino:
            return False, "A conta de origem deve ser diferente da conta de destino"
        return True, ""

    def _new_section(self, parent, title):
        """Cria seção visual com cabeçalho e container interno."""
        section = ctk.CTkFrame(parent, fg_color=self.palette["bg_frames"], corner_radius=12)
        section.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(
            section,
            text=title,
            font=self.font_title,
            text_color=self.palette["accent"],
        ).pack(anchor="w", padx=14, pady=(10, 2))
        content = ctk.CTkFrame(section, fg_color="transparent")
        content.pack(fill="x", padx=12, pady=(0, 10))
        return content
        
    def _create_widgets(self):
        """Cria os elementos da interface com layout fluido em CTk."""
        self.root.grid_rowconfigure(4, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        frame_topo = ctk.CTkFrame(self.root, fg_color="transparent")
        frame_topo.pack(fill="x", padx=12, pady=(8, 0))
        self.btn_settings = ctk.CTkButton(
            frame_topo,
            text="⚙",
            width=38,
            height=34,
            command=self._open_folder_settings_dialog,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
        )
        self.btn_settings.pack(side="left")

        frame_arquivo = self._new_section(self.root, "Arquivo de Entrada")
        frame_arquivo.pack(fill="x")
        self.file_info_badge = ctk.CTkFrame(
            frame_arquivo,
            fg_color="#0a2742",
            border_width=2,
            border_color="#31f0ff",
            corner_radius=10,
        )
        self.file_info_badge.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkLabel(
            self.file_info_badge,
            text="ARQUIVO",
            text_color="#7dd3fc",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(4, 0))
        self.file_name_label = ctk.CTkLabel(
            self.file_info_badge,
            textvariable=self.file_name_var,
            text_color="#ecfeff",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            anchor="w",
            justify="left",
        )
        self.file_name_label.pack(anchor="w", padx=10, pady=(0, 5))
        self.sheet_info_badge = ctk.CTkFrame(
            frame_arquivo,
            fg_color="#0a2742",
            border_width=2,
            border_color="#31f0ff",
            corner_radius=10,
        )
        self.sheet_info_badge.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            self.sheet_info_badge,
            text="ABA ATIVA",
            text_color="#7dd3fc",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
        ).pack(anchor="w", padx=10, pady=(4, 0))
        self.sheet_info_label = ctk.CTkLabel(
            self.sheet_info_badge,
            textvariable=self.sheet_name_var,
            text_color="#ecfeff",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            width=210,
            anchor="w",
        )
        self.sheet_info_label.pack(anchor="w", padx=10, pady=(0, 5))
        self.btn_procurar = ctk.CTkButton(
            frame_arquivo,
            text="Trocar planilha",
            command=self._trocar_planilha,
            width=170,
            height=56,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
        )
        self.btn_procurar.pack(side="left", padx=4)
        self.btn_processar_pasta = ctk.CTkButton(
            frame_arquivo,
            text="Adicionar Arquivo",
            command=self._browse_file,
            width=170,
            height=56,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
        )
        self.btn_processar_pasta.pack(side="left", padx=4)

        frame_diretorios = ctk.CTkFrame(self.root, fg_color="transparent")
        frame_diretorios.pack(fill="x", padx=12, pady=(0, 4))
        self.btn_entrada_dir = ctk.CTkButton(
            frame_diretorios,
            text="Entrada",
            width=130,
            command=self._open_input_dir,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
        )
        self.btn_entrada_dir.pack(side="left", padx=(0, 6))
        self.btn_saida_dir = ctk.CTkButton(
            frame_diretorios,
            text="Saída",
            width=130,
            command=self._open_output_dir,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
        )
        self.btn_saida_dir.pack(side="left", padx=(0, 6))

        frame_config = self._new_section(self.root, "Configurações de Conversão")
        frame_config.pack(fill="x")
        for col in (0, 1, 2, 3):
            frame_config.grid_columnconfigure(col, weight=1 if col in (1, 3) else 0)

        self.percentual_var = tk.StringVar(value="50.0")
        self.empresa_var = tk.StringVar(value="97")
        self.obra_var = tk.StringVar(value="972")
        self.conta_arred_var = tk.StringVar(value="")
        self.memorizar_conta_var = tk.BooleanVar(value=False)
        self.conta_repasse_ativo_var = tk.StringVar(value="")
        self.conta_repasse_passivo_var = tk.StringVar(value="")
        self.grupo_excluido_var = tk.StringVar(value="")

        self._attach_mask_var(self.conta_arred_var, self._format_account_value)
        self._attach_mask_var(self.conta_repasse_ativo_var, self._format_account_value)
        self._attach_mask_var(self.conta_repasse_passivo_var, self._format_account_value)
        self._attach_mask_var(self.grupo_excluido_var, self._format_group_value)

        ctk.CTkLabel(frame_config, text="Percentual (%)").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ctk.CTkEntry(frame_config, textvariable=self.percentual_var, width=120, fg_color=self.palette["bg_input"]).grid(row=0, column=1, sticky="ew", padx=6, pady=6)
        ctk.CTkLabel(frame_config, text="Código Empresa").grid(row=0, column=2, sticky="w", padx=6, pady=6)
        ctk.CTkEntry(frame_config, textvariable=self.empresa_var, width=120, fg_color=self.palette["bg_input"]).grid(row=0, column=3, sticky="ew", padx=6, pady=6)

        ctk.CTkLabel(frame_config, text="Código Obra").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        ctk.CTkEntry(frame_config, textvariable=self.obra_var, width=120, fg_color=self.palette["bg_input"]).grid(row=1, column=1, sticky="ew", padx=6, pady=6)
        ctk.CTkLabel(frame_config, text="Conta Arredondamento").grid(row=1, column=2, sticky="w", padx=6, pady=6)
        ctk.CTkEntry(
            frame_config,
            textvariable=self.conta_arred_var,
            fg_color=self.palette["bg_input"],
            placeholder_text="x.x.xx.xx.xxxxxx",
        ).grid(row=1, column=3, sticky="ew", padx=6, pady=6)

        ctk.CTkLabel(frame_config, text="Conta Repasse Ativo").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        ctk.CTkEntry(
            frame_config,
            textvariable=self.conta_repasse_ativo_var,
            fg_color=self.palette["bg_input"],
            placeholder_text="x.x.xx.xx.xxxxxx",
        ).grid(row=2, column=1, sticky="ew", padx=6, pady=6)
        ctk.CTkLabel(frame_config, text="Conta Repasse Passivo").grid(row=2, column=2, sticky="w", padx=6, pady=6)
        ctk.CTkEntry(
            frame_config,
            textvariable=self.conta_repasse_passivo_var,
            fg_color=self.palette["bg_input"],
            placeholder_text="x.x.xx.xx.xxxxxx",
        ).grid(row=2, column=3, sticky="ew", padx=6, pady=6)

        ctk.CTkLabel(frame_config, text="Grupo a Excluir").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        ctk.CTkEntry(
            frame_config,
            textvariable=self.grupo_excluido_var,
            fg_color=self.palette["bg_input"],
            placeholder_text="x.x.xx.xx",
        ).grid(row=3, column=1, sticky="ew", padx=6, pady=6)
        ctk.CTkCheckBox(
            frame_config,
            text="Memorizar conta de arredondamento",
            variable=self.memorizar_conta_var,
            onvalue=True,
            offvalue=False,
            checkbox_width=18,
            checkbox_height=18,
        ).grid(row=3, column=2, columnspan=2, sticky="w", padx=6, pady=6)

        frame_cadastros = self._new_section(self.root, "Cadastros Rápidos")
        frame_cadastros.pack(fill="x")
        ctk.CTkLabel(frame_cadastros, text="Consorciada").pack(side="left", padx=(0, 8))
        self.cadastro_var = tk.StringVar()
        self.combo_cadastros = ctk.CTkComboBox(
            frame_cadastros,
            variable=self.cadastro_var,
            values=[],
            command=self._on_cadastro_selected,
            width=360,
            fg_color=self.palette["bg_input"],
            button_color=self.palette["accent"],
            button_hover_color=self.palette["accent_hover"],
        )
        self.combo_cadastros.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.btn_novo_cadastro = ctk.CTkButton(
            frame_cadastros,
            text="Novo",
            width=80,
            command=self._new_cadastro,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
        )
        self.btn_novo_cadastro.pack(side="left", padx=3)
        self.btn_editar_cadastro = ctk.CTkButton(
            frame_cadastros,
            text="Editar",
            width=80,
            command=self._edit_cadastro,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
        )
        self.btn_editar_cadastro.pack(side="left", padx=3)
        self.btn_excluir_cadastro = ctk.CTkButton(
            frame_cadastros,
            text="Excluir",
            width=80,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=self._delete_cadastro,
        )
        self.btn_excluir_cadastro.pack(side="left", padx=3)

        frame_botoes = ctk.CTkFrame(self.root, fg_color="transparent")
        frame_botoes.pack(fill="x", padx=12, pady=(6, 8))
        self.btn_converter = ctk.CTkButton(
            frame_botoes,
            text="Converter",
            width=140,
            command=self._converter,
            fg_color=self.palette["converter_bg"],
            hover_color=self.palette["converter_hover"],
            border_width=2,
            border_color=self.palette["converter_border"],
            text_color=self.palette["button_text"],
            font=self.font_button,
        )
        self.btn_converter.pack(side="left", padx=4)
        self.btn_limpar_log = ctk.CTkButton(
            frame_botoes,
            text="Limpar Log",
            width=120,
            command=self._clear_log,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
        )
        self.btn_limpar_log.pack(side="left", padx=4)
        ctk.CTkButton(
            frame_botoes,
            text="Sair",
            width=100,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=self.root.quit,
        ).pack(side="right", padx=4)

        self.progress_panel = ctk.CTkFrame(
            frame_botoes,
            fg_color="#061524",
            border_width=2,
            border_color="#31f0ff",
            corner_radius=12,
            width=320,
            height=92,
        )
        self.progress_title_var = tk.StringVar(value="LOADING")
        self.progress_pct_var = tk.StringVar(value="0%")
        self.progress_hint_var = tk.StringVar(value="Aguardando início")

        header = ctk.CTkFrame(self.progress_panel, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8, 0))

        self.progress_title_label = ctk.CTkLabel(
            header,
            textvariable=self.progress_title_var,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#31f0ff",
        )
        self.progress_title_label.pack(side="left")

        ctk.CTkLabel(
            header,
            textvariable=self.progress_pct_var,
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#31f0ff",
        ).pack(side="right")

        self.progress = ctk.CTkProgressBar(
            self.progress_panel,
            mode="determinate",
            width=296,
            height=16,
            progress_color="#31f0ff",
            fg_color="#12314f",
            border_width=2,
            border_color="#31f0ff",
            corner_radius=8,
        )
        self.progress.set(0)
        self.progress.pack(anchor="center", pady=(8, 2), padx=10)

        ctk.CTkLabel(
            self.progress_panel,
            textvariable=self.progress_hint_var,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#8ab5d7",
        ).pack(anchor="w", padx=10, pady=(0, 8))
        self.progress_panel.pack_forget()

        frame_log = self._new_section(self.root, "Log de Execução")
        frame_log.pack(fill="both", expand=True)
        self.log_text = ctk.CTkTextbox(
            frame_log,
            height=300,
            fg_color="#091827",
            border_width=1,
            border_color=self.palette["bg_input"],
            font=self.font_mono,
        )
        self.log_text.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="Pronto")
        status_bar = ctk.CTkLabel(
            self.root,
            textvariable=self.status_var,
            text_color=self.palette["muted"],
            anchor="w",
            fg_color="#0f172a",
            corner_radius=0,
        )
        status_bar.pack(fill="x", side="bottom", padx=12)
        self._start_converter_animation()

    def _set_busy_state(self, active, texto_status):
        """Controla feedback visual durante operacoes longas."""
        self.status_var.set(texto_status)
        state = "disabled" if active else "normal"
        for btn in (
            self.btn_converter,
            self.btn_processar_pasta,
            self.btn_procurar,
            self.btn_settings,
            self.btn_entrada_dir,
            self.btn_saida_dir,
            self.btn_novo_cadastro,
            self.btn_editar_cadastro,
            self.btn_excluir_cadastro,
            self.btn_limpar_log,
        ):
            btn.configure(state=state)

        if active:
            self._loading_text = "LOADING"
            self.progress_title_var.set("LOADING")
            self.progress_pct_var.set("0%")
            self.progress_hint_var.set("Preparando conversão...")
            self.progress.set(0)
            self.progress_panel.pack(side="right", padx=8)
            self._start_loading_animation()
        else:
            self._stop_loading_animation()
            self.progress_panel.pack_forget()

    def _update_progress(self, progress: float, mensagem: str) -> None:
        """Atualiza barra e texto de progresso com percentual real."""
        valor = max(0.0, min(1.0, progress))
        percentual = int(round(valor * 100))
        texto = (mensagem or "Processando")
        self.progress.set(valor)
        self.progress_pct_var.set(f"{percentual}%")
        self._loading_text = texto.upper()
        self.progress_hint_var.set(texto)
        self.status_var.set(f"{texto} ({percentual}%)")

    def _start_loading_animation(self) -> None:
        if self._loading_anim_job is None:
            self._loading_phase = 0
            self._tick_loading_animation()

    def _stop_loading_animation(self) -> None:
        if self._loading_anim_job is not None:
            self.root.after_cancel(self._loading_anim_job)
            self._loading_anim_job = None

    def _tick_loading_animation(self) -> None:
        dots = "." * ((self._loading_phase % 4) + 1)
        self.progress_title_var.set(f"{self._loading_text}{dots}")
        glow_colors = ["#31f0ff", "#86f8ff", "#31f0ff", "#1cd8ff"]
        glow = glow_colors[self._loading_phase % len(glow_colors)]
        self.progress.configure(progress_color=glow, border_color=glow)
        self.progress_title_label.configure(text_color=glow)
        self._loading_phase += 1
        self._loading_anim_job = self.root.after(180, self._tick_loading_animation)

    def _start_converter_animation(self) -> None:
        if self._converter_anim_job is None:
            self._converter_anim_phase = 0
            self._tick_converter_animation()

    def _tick_converter_animation(self) -> None:
        if not hasattr(self, "btn_converter") or not self.btn_converter.winfo_exists():
            self._converter_anim_job = None
            return

        state = str(self.btn_converter.cget("state"))
        if state == "disabled":
            self.btn_converter.configure(
                fg_color=self.palette["converter_bg"],
                hover_color=self.palette["converter_hover"],
                border_color=self.palette["converter_border"],
            )
            self._converter_anim_job = self.root.after(220, self._tick_converter_animation)
            return

        glow_bg = ["#2adfed", "#35e9f7", "#2adfed", "#27d7e5"]
        glow_hover = ["#20d2e2", "#2adfed", "#20d2e2", "#1fcddd"]
        glow_border = ["#9bf7ff", "#d6fdff", "#9bf7ff", "#7af4ff"]
        idx = self._converter_anim_phase % len(glow_bg)

        self.btn_converter.configure(
            fg_color=glow_bg[idx],
            hover_color=glow_hover[idx],
            border_color=glow_border[idx],
        )
        self._converter_anim_phase += 1
        self._converter_anim_job = self.root.after(220, self._tick_converter_animation)

    def _emit_progress_threadsafe(self, progress: float, mensagem: str) -> None:
        self.root.after(0, lambda: self._update_progress(progress, mensagem))

    @staticmethod
    def _digits_only(value: str) -> str:
        return "".join(ch for ch in str(value or "") if ch.isdigit())

    def _format_by_groups(self, value: str, groups: tuple[int, ...]) -> str:
        digits = self._digits_only(value)
        parts = []
        pos = 0
        for group in groups:
            if pos >= len(digits):
                break
            part = digits[pos:pos + group]
            if part:
                parts.append(part)
            pos += group
        return ".".join(parts)

    def _format_account_value(self, value: str) -> str:
        return self._format_by_groups(value, (1, 1, 2, 2, 6))

    def _format_group_value(self, value: str) -> str:
        return self._format_by_groups(value, (1, 1, 2, 2))

    def _attach_mask_var(self, var: tk.StringVar, formatter) -> None:
        def _on_change(*_):
            if self._mask_updating:
                return
            current = var.get()
            formatted = formatter(current)
            if current != formatted:
                self._mask_updating = True
                var.set(formatted)
                self._mask_updating = False

        var.trace_add("write", _on_change)

    def _attach_mask_entry(self, entry, formatter) -> None:
        def _on_key_release(_event=None):
            current = entry.get()
            formatted = formatter(current)
            if current != formatted:
                entry.delete(0, "end")
                entry.insert(0, formatted)

        entry.bind("<KeyRelease>", _on_key_release)

    def _is_valid_account(self, value: str) -> bool:
        return len(self._digits_only(value)) == 12

    def _is_valid_group(self, value: str) -> bool:
        return len(self._digits_only(value)) == 6

    def _validate_account_inputs(self, conta_arred, repasse_ativo, repasse_passivo, grupo_excluido) -> bool:
        if not self._is_valid_account(conta_arred):
            self._show_error("Erro", "Formato de conta incorreto")
            return False

        if repasse_ativo and not self._is_valid_account(repasse_ativo):
            self._show_error("Erro", "Formato de conta incorreto")
            return False

        if repasse_passivo and not self._is_valid_account(repasse_passivo):
            self._show_error("Erro", "Formato de conta incorreto")
            return False

        if grupo_excluido and not self._is_valid_group(grupo_excluido):
            self._show_error("Erro", "Formato de grupo incorreto")
            return False

        return True

    def _show_custom_dialog(
        self,
        kind: str,
        title: str,
        message: str,
        parent=None,
        buttons=("OK",),
        default_button=None,
    ) -> str:
        """Renderiza dialogo modal seguindo a identidade visual da aplicacao."""
        owner = parent or self.root
        selected = {"value": default_button or buttons[0]}

        kind_cfg = {
            "info": {"icon": "i", "color": "#31f0ff"},
            "warning": {"icon": "!", "color": "#f59e0b"},
            "error": {"icon": "x", "color": "#ef4444"},
            "question": {"icon": "?", "color": "#22c55e"},
        }
        cfg = kind_cfg.get(kind, kind_cfg["info"])

        dialog = ctk.CTkToplevel(owner)
        dialog.title(title)
        dialog.configure(fg_color=self.palette["bg_principal"])
        dialog.geometry("620x300")
        dialog.minsize(500, 240)
        dialog.transient(owner)
        dialog.grab_set()

        container = ctk.CTkFrame(
            dialog,
            fg_color=self.palette["bg_frames"],
            border_width=2,
            border_color=cfg["color"],
            corner_radius=12,
        )
        container.pack(fill="both", expand=True, padx=14, pady=14)

        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 8))

        badge = ctk.CTkLabel(
            header,
            text=cfg["icon"].upper(),
            width=28,
            height=28,
            corner_radius=14,
            fg_color=cfg["color"],
            text_color="#0b1220",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
        )
        badge.pack(side="left")

        ctk.CTkLabel(
            header,
            text=title,
            text_color=self.palette["fg_light"],
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
        ).pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            container,
            text=message,
            justify="left",
            anchor="w",
            wraplength=570,
            text_color=self.palette["fg_light"],
            font=self.font_body,
        ).pack(fill="both", expand=True, padx=16, pady=(4, 10))

        footer = ctk.CTkFrame(container, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(0, 12))

        def close_with(value: str):
            selected["value"] = value
            dialog.destroy()

        for label in reversed(buttons):
            fg = self.palette["accent"]
            hover = self.palette["accent_hover"]

            ctk.CTkButton(
                footer,
                text=label,
                width=110,
                fg_color=fg,
                hover_color=hover,
                text_color=self.palette["button_text"],
                font=self.font_button,
                command=lambda value=label: close_with(value),
            ).pack(side="right", padx=4)

        dialog.update_idletasks()
        owner.update_idletasks()
        x = owner.winfo_rootx() + max(0, (owner.winfo_width() - dialog.winfo_width()) // 2)
        y = owner.winfo_rooty() + max(0, (owner.winfo_height() - dialog.winfo_height()) // 2)
        dialog.geometry(f"+{x}+{y}")

        dialog.focus_force()
        dialog.protocol("WM_DELETE_WINDOW", lambda: close_with(default_button or buttons[-1]))
        dialog.wait_window()
        return selected["value"]

    def _dialog_dispatch(
        self,
        kind: str,
        title: str,
        message: str,
        parent=None,
        buttons=("OK",),
        default_button=None,
        wait_response=False,
    ):
        """Garante abertura segura de dialogos CTk no thread principal."""
        if threading.current_thread() is threading.main_thread():
            return self._show_custom_dialog(
                kind,
                title,
                message,
                parent=parent,
                buttons=buttons,
                default_button=default_button,
            )

        if not wait_response:
            self.root.after(
                0,
                lambda: self._show_custom_dialog(
                    kind,
                    title,
                    message,
                    parent=parent,
                    buttons=buttons,
                    default_button=default_button,
                ),
            )
            return default_button or buttons[0]

        result = {"value": default_button or buttons[0]}
        done = threading.Event()

        def open_and_store():
            result["value"] = self._show_custom_dialog(
                kind,
                title,
                message,
                parent=parent,
                buttons=buttons,
                default_button=default_button,
            )
            done.set()

        self.root.after(0, open_and_store)
        done.wait()
        return result["value"]

    def _show_info(self, title: str, message: str, parent=None) -> None:
        self._dialog_dispatch("info", title, message, parent=parent)

    def _show_warning(self, title: str, message: str, parent=None) -> None:
        self._dialog_dispatch("warning", title, message, parent=parent)

    def _show_error(self, title: str, message: str, parent=None) -> None:
        self._dialog_dispatch("error", title, message, parent=parent)

    def _ask_yes_no(self, title: str, message: str, parent=None) -> bool:
        answer = self._dialog_dispatch(
            "question",
            title,
            message,
            parent=parent,
            buttons=("Não", "Sim"),
            default_button="Não",
            wait_response=True,
        )
        return answer.lower() == "sim"

    def _show_custom_input_dialog(
        self,
        title: str,
        message: str,
        initial_value: str = "",
        parent=None,
    ) -> str | None:
        """Exibe diálogo de entrada de texto no tema do app e retorna valor ou None."""
        owner = parent or self.root
        result = {"value": None}

        dialog = ctk.CTkToplevel(owner)
        dialog.title(title)
        dialog.configure(fg_color=self.palette["bg_principal"])
        dialog.geometry("620x250")
        dialog.minsize(520, 220)
        dialog.transient(owner)
        dialog.grab_set()

        container = ctk.CTkFrame(
            dialog,
            fg_color=self.palette["bg_frames"],
            border_width=2,
            border_color=self.palette["accent"],
            corner_radius=12,
        )
        container.pack(fill="both", expand=True, padx=14, pady=14)

        ctk.CTkLabel(
            container,
            text=title,
            text_color=self.palette["fg_light"],
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(12, 6))

        ctk.CTkLabel(
            container,
            text=message,
            justify="left",
            anchor="w",
            wraplength=560,
            text_color=self.palette["fg_light"],
            font=self.font_body,
        ).pack(fill="x", padx=14, pady=(0, 8))

        entry_var = tk.StringVar(value=initial_value)
        entry = ctk.CTkEntry(
            container,
            textvariable=entry_var,
            fg_color=self.palette["bg_input"],
        )
        entry.pack(fill="x", padx=14, pady=(0, 10))

        footer = ctk.CTkFrame(container, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(0, 12))

        def close_cancel():
            result["value"] = None
            dialog.destroy()

        def close_ok():
            result["value"] = entry_var.get().strip()
            dialog.destroy()

        ctk.CTkButton(
            footer,
            text="Cancelar",
            width=110,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=close_cancel,
        ).pack(side="right", padx=4)
        ctk.CTkButton(
            footer,
            text="Salvar",
            width=110,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=close_ok,
        ).pack(side="right", padx=4)

        dialog.update_idletasks()
        owner.update_idletasks()
        x = owner.winfo_rootx() + max(0, (owner.winfo_width() - dialog.winfo_width()) // 2)
        y = owner.winfo_rooty() + max(0, (owner.winfo_height() - dialog.winfo_height()) // 2)
        dialog.geometry(f"+{x}+{y}")

        entry.focus_force()
        entry.select_range(0, "end")
        dialog.protocol("WM_DELETE_WINDOW", close_cancel)
        dialog.wait_window()
        return result["value"]

    def _ask_text_input(self, title: str, message: str, initial_value: str = "", parent=None) -> str | None:
        """Abre diálogo de texto no thread principal e aguarda resposta quando necessário."""
        if threading.current_thread() is threading.main_thread():
            return self._show_custom_input_dialog(title, message, initial_value=initial_value, parent=parent)

        result = {"value": None}
        done = threading.Event()

        def open_and_store():
            result["value"] = self._show_custom_input_dialog(
                title,
                message,
                initial_value=initial_value,
                parent=parent,
            )
            done.set()

        self.root.after(0, open_and_store)
        done.wait()
        return result["value"]

    @staticmethod
    def _is_valid_excel_sheet_name(name: str) -> bool:
        if not name:
            return False
        if len(name) > 31:
            return False
        invalid_chars = set('[]:*?/\\')
        return not any(ch in invalid_chars for ch in name)

    def _maybe_rename_output_sheet(self, arquivo_saida: Path) -> None:
        """Após gerar o arquivo, pergunta se deseja renomear a planilha e aplica alteração."""
        if not self._ask_yes_no(
            "Renomear planilha",
            "Deseja trocar o nome da planilha da pasta de trabalho gerada?",
        ):
            return

        try:
            from openpyxl import load_workbook
        except ImportError:
            self._show_warning(
                "Renomear planilha",
                "Não foi possível renomear a planilha porque a biblioteca openpyxl não está disponível.",
            )
            return

        workbook = load_workbook(str(arquivo_saida))
        if not workbook.sheetnames:
            self._show_warning("Renomear planilha", "Nenhuma planilha encontrada no arquivo gerado.")
            return

        current_name = workbook.sheetnames[0]
        novo_nome = self._ask_text_input(
            "Nome da planilha",
            "Digite o novo nome da planilha (máx. 31 caracteres, sem []:*?/\\).",
            initial_value=current_name,
        )
        if novo_nome is None:
            self._log("ℹ Renomeação da planilha cancelada pelo usuário")
            return

        novo_nome = novo_nome.strip()
        if not self._is_valid_excel_sheet_name(novo_nome):
            self._show_error(
                "Nome inválido",
                "Nome de planilha inválido. Use até 31 caracteres e evite []:*?/\\",
            )
            return

        if novo_nome == current_name:
            self._log("ℹ Nome da planilha mantido sem alterações")
            return

        try:
            workbook[ current_name ].title = novo_nome
            workbook.save(str(arquivo_saida))
            self._log(f"✓ Planilha renomeada para: {novo_nome}")
        except (ValueError, OSError) as exc:
            self._show_error("Erro", f"Não foi possível renomear a planilha: {exc}")
        finally:
            workbook.close()
        
    def _log(self, mensagem):
        """Adiciona mensagem ao log"""
        if self.log_text:
            self.log_text.insert("end", mensagem + "\n")
            self.log_text.see("end")
            self.root.update_idletasks()
    
    def _browse_file(self):
        """Abre diálogo para selecionar arquivo"""
        arquivo = filedialog.askopenfilename(
            title="Selecione arquivo para conversão",
            filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=self.input_dir
        )
        if arquivo:
            selected_sheet = ""
            if Path(arquivo).suffix.lower() in {".xls", ".xlsx"}:
                sheet_names = self._listar_planilhas_arquivo(arquivo)
                if not sheet_names:
                    self._show_error("Erro", "Nenhuma planilha encontrada no arquivo selecionado")
                    return
                selected_sheet = self._abrir_dialogo_planilhas(arquivo, sheet_names)
                if not selected_sheet:
                    self._show_warning("Seleção cancelada", "Nenhuma planilha foi selecionada")
                    return

            self.selected_input_file = arquivo
            self.file_name_var.set(f"Arquivo: {Path(arquivo).name}")
            self.btn_processar_pasta.configure(text="Trocar Arquivo")
            if selected_sheet:
                self.sheet_name_var.set(f"Planilha: {selected_sheet}")
            elif Path(arquivo).suffix.lower() == ".csv":
                self.sheet_name_var.set("Planilha: CSV")
            else:
                self.sheet_name_var.set("Planilha: --")
            self._log(f"✓ Arquivo selecionado: {Path(arquivo).name}")
            if selected_sheet:
                self._log(f"  Planilha selecionada: {selected_sheet}")

    def _trocar_planilha(self):
        """Permite trocar apenas a planilha ativa do arquivo já selecionado."""
        arquivo = self.selected_input_file.strip()
        if not arquivo or not Path(arquivo).exists():
            self._show_warning("Seleção", "Selecione um arquivo primeiro em Trocar Arquivo")
            return

        if Path(arquivo).suffix.lower() not in {".xls", ".xlsx"}:
            self._show_warning("Seleção", "Troca de planilha disponível apenas para arquivos Excel")
            return

        sheet_names = self._listar_planilhas_arquivo(arquivo)
        if not sheet_names:
            self._show_error("Erro", "Nenhuma planilha encontrada no arquivo selecionado")
            return

        selected_sheet = self._abrir_dialogo_planilhas(arquivo, sheet_names)
        if not selected_sheet:
            return

        self.sheet_name_var.set(f"Planilha: {selected_sheet}")
        self._log(f"✓ Planilha trocada para: {selected_sheet}")

    def _listar_planilhas_arquivo(self, arquivo: str) -> list[str]:
        try:
            with pd.ExcelFile(arquivo) as excel_file:
                return [str(name) for name in excel_file.sheet_names]
        except (ValueError, OSError, PermissionError) as exc:
            self._show_error("Erro", f"Não foi possível ler as planilhas: {exc}")
            return []

    def _abrir_dialogo_planilhas(self, arquivo: str, sheet_names: list[str]) -> str:
        arquivo_key = str(Path(arquivo).resolve())
        selected = {"value": self._selected_sheet_by_file.get(arquivo_key, "")}
        active_label_var = tk.StringVar(
            value=f"Aba ativa: {selected['value']}" if selected["value"] else "Aba ativa: nenhuma"
        )
        active_button_ref = {"button": None}
        glow_job = {"id": None}
        glow_phase = {"value": 0}

        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Selecionar planilha")
        dialog.geometry("640x520")
        dialog.minsize(560, 420)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(fg_color=self.palette["bg_principal"])

        shell = ctk.CTkFrame(
            dialog,
            fg_color=self.palette["bg_frames"],
            border_width=2,
            border_color=self.palette["accent"],
            corner_radius=12,
        )
        shell.pack(fill="both", expand=True, padx=12, pady=12)

        header = ctk.CTkFrame(shell, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 6))
        ctk.CTkLabel(
            header,
            text="Selecione a planilha de entrada",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=self.palette["fg_light"],
        ).pack(side="left")

        def close_dialog():
            if glow_job["id"] is not None:
                dialog.after_cancel(glow_job["id"])
                glow_job["id"] = None
            dialog.destroy()

        ctk.CTkButton(
            header,
            text="X",
            width=34,
            height=30,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=close_dialog,
        ).pack(side="right")

        ctk.CTkLabel(
            shell,
            text=f"Arquivo: {Path(arquivo).name}",
            text_color=self.palette["muted"],
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(
            shell,
            textvariable=active_label_var,
            text_color="#67e8f9",
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        ).pack(fill="x", padx=14, pady=(0, 8))

        scroller = ctk.CTkScrollableFrame(shell, fg_color=self.palette["bg_principal"])
        scroller.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        for idx, sheet in enumerate(sheet_names):
            is_active = sheet == selected["value"]
            row_frame = ctk.CTkFrame(
                scroller,
                fg_color="#0a1f33" if is_active else "transparent",
                border_width=2 if is_active else 0,
                border_color="#67e8f9" if is_active else self.palette["bg_principal"],
                corner_radius=10,
            )
            row_frame.pack(fill="x", padx=6, pady=4)

            btn = ctk.CTkButton(
                row_frame,
                text=sheet,
                anchor="w",
                fg_color="#0891b2" if is_active else self.palette["bg_input"],
                hover_color="#0e7490" if is_active else "#234266",
                text_color=self.palette["fg_light"],
                font=self.font_button,
                command=lambda sheet_name=sheet: self._selecionar_planilha_dialog(
                    dialog,
                    arquivo_key,
                    selected,
                    sheet_name,
                ),
            )
            btn.pack(fill="x")
            if is_active:
                active_button_ref["button"] = btn

            if is_active:
                ctk.CTkLabel(
                    row_frame,
                    text="ATIVA",
                    text_color="#67e8f9",
                    fg_color="#08314d",
                    corner_radius=8,
                    padx=8,
                    pady=1,
                    font=ctk.CTkFont(size=10, weight="bold"),
                ).place(relx=0.0, rely=0.0, anchor="nw", x=8, y=6)

            if (arquivo_key, sheet) in self._selected_sheet_history:
                ctk.CTkLabel(
                    row_frame,
                    text="☑️",
                    text_color="#22c55e",
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).place(relx=1.0, rely=0.0, anchor="ne", x=-8, y=6)

        def _pulse_active_button() -> None:
            active_btn = active_button_ref["button"]
            if active_btn is None or not active_btn.winfo_exists() or not dialog.winfo_exists():
                glow_job["id"] = None
                return

            glow_colors = ["#0891b2", "#06b6d4", "#22d3ee", "#06b6d4"]
            hover_colors = ["#0e7490", "#0891b2", "#0ea5b7", "#0891b2"]
            idx = glow_phase["value"] % len(glow_colors)
            active_btn.configure(fg_color=glow_colors[idx], hover_color=hover_colors[idx])
            glow_phase["value"] += 1
            glow_job["id"] = dialog.after(220, _pulse_active_button)

        if active_button_ref["button"] is not None:
            _pulse_active_button()

        footer = ctk.CTkFrame(shell, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkButton(
            footer,
            text="Cancelar",
            width=120,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=close_dialog,
        ).pack(side="right", padx=4)

        dialog.wait_window()
        return selected["value"]

    def _selecionar_planilha_dialog(
        self,
        dialog,
        arquivo_key: str,
        selected_ref: dict[str, str],
        sheet_name: str,
    ) -> None:
        selected_ref["value"] = sheet_name
        self._selected_sheet_by_file[arquivo_key] = sheet_name
        self._selected_sheet_history.add((arquivo_key, sheet_name))
        dialog.destroy()
    
    def _load_cadastros(self):
        """Carrega lista de cadastros do JSON"""
        try:
            nomes = self.service.carregar_nomes_cadastros()
            valores = nomes if nomes else [""]
            self.combo_cadastros.configure(values=valores)
            if nomes:
                self.cadastro_var.set(nomes[0])
            self._log(f"✓ {len(nomes)} cadastros carregados")
        except CadastroErro as e:
            self._log(f"✗ Erro ao carregar cadastros: {e}")
            log_event(self.logger, 40, "ui_cadastros_carregar_falhou", etapa="ui")
    
    def _mostrar_boas_vindas(self):
        """Exibe mensagem de boas-vindas no log"""
        self._log("=" * 70)
        self._log("🏢 CONVERSOR CONTÁBIL - EMPRESAS CONSORCIADAS")
        self._log("=" * 70)
        self._log("")
        self._log("✨ Sistema 100% pronto para uso!")
        self._log("")
        self._log("📋 Como usar:")
        self._log("  1. Selecione uma consorciada cadastrada (ou preencha manualmente)")
        self._log("  2. Clique em 'Procurar' e selecione o arquivo Excel")
        self._log("  3. Verifique os dados preenchidos automaticamente")
        self._log("  4. Clique em '▶️ Converter'")
        self._log("")
        self._log("🔧 Características:")
        self._log("  ✓ 13 contas prioritárias sempre fecham 100%")
        self._log("  ✓ Todas as sequências balanceadas (D=C)")
        self._log("  ✓ Ajuste automático de arredondamento")
        self._log("  ✓ Processamento em lote disponível")
        self._log("")
        self._log("Pronto para conversão!")
        self._log("=" * 70)
    
    def _on_cadastro_selected(self, event=None):
        """Carrega TODOS os dados do cadastro selecionado"""
        try:
            selecionado = self.cadastro_var.get()
            c = self.service.obter_cadastro(selecionado)
            if not c:
                return

            # Carregar TODOS os campos
            self.percentual_var.set(c.get("percentual", 50.0))
            self.empresa_var.set(c.get("codigo_empresa", "97"))
            self.obra_var.set(c.get("codigo_obra", "972"))

            # Conta de arredondamento - SEMPRE carregar se existir no cadastro
            conta = c.get("conta_arredondamento", "1.1.01.01.000099")
            self.conta_arred_var.set(conta)

            # Checkbox memorizar - FORÇAR update do valor
            memorizar = c.get("memorizar_conta", False)
            self.memorizar_conta_var.set(memorizar)

            # Contas de Repasse - SEMPRE carregar se existirem no cadastro
            repasse_ativo = c.get("conta_repasse_ativo", "")
            repasse_passivo = c.get("conta_repasse_passivo", "")
            grupo_excluido = c.get("grupo_excluido", "")

            self.conta_repasse_ativo_var.set(repasse_ativo)
            self.conta_repasse_passivo_var.set(repasse_passivo)
            self.grupo_excluido_var.set(grupo_excluido)

            # Log detalhado
            self._log(f"✓ Cadastro '{selecionado}' carregado")
            self._log(f"  Percentual: {c.get('percentual')}% | Empresa: {c.get('codigo_empresa')} | Obra: {c.get('codigo_obra')}")
            if memorizar:
                self._log(f"  Conta Arredondamento: {conta} (MEMORIZADA)")
            else:
                self._log(f"  Conta Arredondamento: {conta}")
            if repasse_ativo or repasse_passivo or grupo_excluido:
                self._log(f"  Contas de Repasse:")
                if repasse_ativo:
                    self._log(f"    └─ Ativo: {repasse_ativo}")
                if repasse_passivo:
                    self._log(f"    └─ Passivo: {repasse_passivo}")
                if grupo_excluido:
                    self._log(f"    └─ Grupo Excluído: {grupo_excluido}")
        except CadastroErro as e:
            self._log(f"✗ Erro ao carregar cadastro: {e}")
            log_event(self.logger, 40, "ui_cadastro_selecao_falhou", etapa="ui", cadastro=self.cadastro_var.get().strip())
    
    def _dialog_section(self, parent, title):
        frame = ctk.CTkFrame(parent, fg_color=self.palette["bg_frames"], corner_radius=10)
        frame.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.palette["accent"],
        ).pack(anchor="w", padx=12, pady=(8, 2))
        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.pack(fill="x", padx=10, pady=(0, 10))
        content.grid_columnconfigure(1, weight=1)
        return content

    def _open_cadastro_dialog(self, modo, selecionado=None, cadastro=None):
        """Abre dialogo de cadastro em modo novo/editar com layout CTk."""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Novo Cadastro" if modo == "novo" else f"Editar - {selecionado}")
        dialog.geometry("680x680")
        dialog.minsize(620, 560)
        dialog.transient(self.root)
        dialog.grab_set()

        foi_salvo = [False]

        def on_close():
            if modo == "novo" and not foi_salvo[0]:
                if not self._ask_yes_no("Confirmar", "Fechar sem salvar?", parent=dialog):
                    return
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_close)

        form = ctk.CTkScrollableFrame(dialog, fg_color=self.palette["bg_principal"])
        form.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        frame_consortio = self._dialog_section(form, "Identificacao do Consorcio")
        ctk.CTkLabel(frame_consortio, text="Nome do Consorcio").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        entry_nome_cons = ctk.CTkEntry(frame_consortio, fg_color=self.palette["bg_input"])
        entry_nome_cons.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ctk.CTkLabel(frame_consortio, text="Codigo do Consorcio").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        entry_cons = ctk.CTkEntry(frame_consortio, fg_color=self.palette["bg_input"])
        entry_cons.grid(row=1, column=1, sticky="ew", padx=6, pady=6)

        ctk.CTkLabel(frame_consortio, text="Codigo da Obra").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        entry_obra_cons = ctk.CTkEntry(frame_consortio, fg_color=self.palette["bg_input"])
        entry_obra_cons.grid(row=2, column=1, sticky="ew", padx=6, pady=6)

        frame_consorciada = self._dialog_section(form, "Dados da Consorciada")
        ctk.CTkLabel(frame_consorciada, text="Nome da Consorciada").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        entry_nome = ctk.CTkEntry(frame_consorciada, fg_color=self.palette["bg_input"])
        entry_nome.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ctk.CTkLabel(frame_consorciada, text="Percentual (%)").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        entry_perc = ctk.CTkEntry(frame_consorciada, fg_color=self.palette["bg_input"])
        entry_perc.grid(row=1, column=1, sticky="ew", padx=6, pady=6)

        ctk.CTkLabel(frame_consorciada, text="Codigo Empresa").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        entry_emp = ctk.CTkEntry(frame_consorciada, fg_color=self.palette["bg_input"])
        entry_emp.grid(row=2, column=1, sticky="ew", padx=6, pady=6)

        ctk.CTkLabel(frame_consorciada, text="Codigo Obra").grid(row=3, column=0, sticky="w", padx=6, pady=6)
        entry_obra = ctk.CTkEntry(frame_consorciada, fg_color=self.palette["bg_input"])
        entry_obra.grid(row=3, column=1, sticky="ew", padx=6, pady=6)

        frame_repasse = self._dialog_section(form, "Contas de Repasse")
        ctk.CTkLabel(frame_repasse, text="Conta de Repasse do Ativo").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        entry_conta_repasse_ativo = ctk.CTkEntry(
            frame_repasse,
            fg_color=self.palette["bg_input"],
            placeholder_text="x.x.xx.xx.xxxxxx",
        )
        entry_conta_repasse_ativo.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ctk.CTkLabel(frame_repasse, text="Conta de Repasse do Passivo").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        entry_conta_repasse_passivo = ctk.CTkEntry(
            frame_repasse,
            fg_color=self.palette["bg_input"],
            placeholder_text="x.x.xx.xx.xxxxxx",
        )
        entry_conta_repasse_passivo.grid(row=1, column=1, sticky="ew", padx=6, pady=6)

        ctk.CTkLabel(frame_repasse, text="Grupo a ser Excluido").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        entry_grupo_excluido = ctk.CTkEntry(
            frame_repasse,
            fg_color=self.palette["bg_input"],
            placeholder_text="x.x.xx.xx",
        )
        entry_grupo_excluido.grid(row=2, column=1, sticky="ew", padx=6, pady=6)

        frame_arredondo = self._dialog_section(form, "Conta de Arredondamento")
        ctk.CTkLabel(frame_arredondo, text="Conta").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        entry_conta = ctk.CTkEntry(
            frame_arredondo,
            fg_color=self.palette["bg_input"],
            placeholder_text="x.x.xx.xx.xxxxxx",
        )
        entry_conta.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        self._attach_mask_entry(entry_conta_repasse_ativo, self._format_account_value)
        self._attach_mask_entry(entry_conta_repasse_passivo, self._format_account_value)
        self._attach_mask_entry(entry_conta, self._format_account_value)
        self._attach_mask_entry(entry_grupo_excluido, self._format_group_value)

        memorizar_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            frame_arredondo,
            text="Memorizar esta conta",
            variable=memorizar_var,
            onvalue=True,
            offvalue=False,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=6, pady=6)

        if modo == "novo":
            entry_perc.insert(0, "50")
            entry_emp.insert(0, "97")
            entry_obra.insert(0, "972")
            entry_conta.insert(0, self._format_account_value("1.1.01.01.000099"))
        else:
            entry_nome.insert(0, selecionado)
            entry_nome.configure(state="disabled")
            entry_nome_cons.insert(0, str(cadastro.get("nome_consortio", "")))
            entry_cons.insert(0, str(cadastro.get("codigo_consortio", "")))
            entry_obra_cons.insert(0, str(cadastro.get("codigo_obra_consortio", "")))
            entry_perc.insert(0, str(cadastro.get("percentual", "50")))
            entry_emp.insert(0, str(cadastro.get("codigo_empresa", "97")))
            entry_obra.insert(0, str(cadastro.get("codigo_obra", "972")))
            entry_conta_repasse_ativo.insert(0, self._format_account_value(str(cadastro.get("conta_repasse_ativo", ""))))
            entry_conta_repasse_passivo.insert(0, self._format_account_value(str(cadastro.get("conta_repasse_passivo", ""))))
            entry_grupo_excluido.insert(0, self._format_group_value(str(cadastro.get("grupo_excluido", ""))))
            entry_conta.insert(0, self._format_account_value(str(cadastro.get("conta_arredondamento", "1.1.01.01.000099"))))
            memorizar_var.set(bool(cadastro.get("memorizar_conta", False)))

        footer = ctk.CTkFrame(dialog, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=10)

        def save_changes():
            try:
                conta_arred = self._format_account_value(entry_conta.get().strip())
                conta_repasse_ativo = self._format_account_value(entry_conta_repasse_ativo.get().strip())
                conta_repasse_passivo = self._format_account_value(entry_conta_repasse_passivo.get().strip())
                grupo_excluido = self._format_group_value(entry_grupo_excluido.get().strip())

                if not self._validate_account_inputs(
                    conta_arred,
                    conta_repasse_ativo,
                    conta_repasse_passivo,
                    grupo_excluido,
                ):
                    return

                payload_base = {
                    "nome_consortio": entry_nome_cons.get().strip(),
                    "codigo_consortio": entry_cons.get().strip(),
                    "codigo_obra_consortio": entry_obra_cons.get().strip(),
                    "percentual": entry_perc.get(),
                    "codigo_empresa": entry_emp.get(),
                    "codigo_obra": entry_obra.get(),
                    "conta_repasse_ativo": conta_repasse_ativo,
                    "conta_repasse_passivo": conta_repasse_passivo,
                    "grupo_excluido": grupo_excluido,
                    "conta_arredondamento": conta_arred,
                    "memorizar_conta": memorizar_var.get(),
                }

                if modo == "novo":
                    payload = {
                        "nome": entry_nome.get().strip(),
                        **payload_base,
                    }
                    self.service.criar_cadastro(payload)
                    self._log(f"✓ Cadastro '{payload['nome']}' ({payload['nome_consortio']}) criado com sucesso")
                else:
                    self.service.atualizar_cadastro(selecionado, payload_base)
                    self._log(f"✓ Cadastro '{selecionado}' atualizado")

                self._load_cadastros()
                foi_salvo[0] = True
                dialog.destroy()
            except ValueError as e:
                self._show_warning("Validação", str(e), parent=dialog)
            except CadastroErro as e:
                self._show_error("Erro", f"Erro ao salvar: {e}", parent=dialog)

        ctk.CTkButton(
            footer,
            text="Cancelar",
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=dialog.destroy,
        ).pack(side="right", padx=4)
        ctk.CTkButton(
            footer,
            text="Salvar",
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=save_changes,
        ).pack(side="right", padx=4)

    def _new_cadastro(self):
        """Cria novo cadastro."""
        self._open_cadastro_dialog("novo")

    def _edit_cadastro(self):
        """Edita cadastro selecionado."""
        selecionado = self.cadastro_var.get().strip()
        if not selecionado:
            self._show_warning("Seleção", "Selecione um cadastro para editar")
            return

        try:
            cadastro = self.service.obter_cadastro(selecionado)
            if not cadastro:
                return
            self._open_cadastro_dialog("editar", selecionado=selecionado, cadastro=cadastro)
        except CadastroErro as e:
            self._show_error("Erro", f"Erro ao editar: {e}")
    
    def _delete_cadastro(self):
        """Deleta cadastro selecionado"""
        selecionado = self.cadastro_var.get()
        if not selecionado:
            self._show_warning("Seleção", "Selecione um cadastro para deletar")
            return
        
        if self._ask_yes_no("Confirmação", f"Deletar cadastro '{selecionado}'?"):
            try:
                removido = self.service.deletar_cadastro(selecionado)
                if not removido:
                    self._show_warning("Seleção", f"Cadastro '{selecionado}' não encontrado")
                    return
                
                self._log(f"✓ Cadastro '{selecionado}' deletado")
                self._load_cadastros()
                self.cadastro_var.set("")
            except CadastroErro as e:
                self._show_error("Erro", f"Erro ao deletar: {e}")
    
    def _converter(self):
        """Executa conversão em thread"""
        arquivo = self.selected_input_file.strip()
        if not arquivo or not Path(arquivo).exists():
            self._show_error("Erro", "Selecione um arquivo válido")
            return

        if not self._validate_account_inputs(
            self.conta_arred_var.get().strip(),
            self.conta_repasse_ativo_var.get().strip(),
            self.conta_repasse_passivo_var.get().strip(),
            self.grupo_excluido_var.get().strip(),
        ):
            return
        
        conta_arred = self.conta_arred_var.get().strip()
        try:
            percentual, empresa, obra, conta_arred = self.service.parse_config(
                self.percentual_var.get(),
                self.empresa_var.get(),
                self.obra_var.get(),
                conta_arred,
            )
        except ConfiguracaoErro as e:
            self._show_error("Erro", str(e))
            return

        self._set_busy_state(True, "⏳ Processando conversão...")

        arquivo_key = str(Path(arquivo).resolve())
        sheet_name = self._selected_sheet_by_file.get(arquivo_key, "")
        
        # Executar em thread para não congelar GUI
        thread = threading.Thread(target=self._run_conversion, 
                                 args=(arquivo, percentual, empresa, obra, conta_arred,
                                       self.conta_repasse_ativo_var.get().strip(),
                                       self.conta_repasse_passivo_var.get().strip(),
                                       self.grupo_excluido_var.get().strip(),
                                       self.cadastro_var.get().strip(),
                                       sheet_name))
        thread.daemon = True
        thread.start()
    
    def _run_conversion(
        self,
        arquivo,
        percentual,
        empresa,
        obra,
        conta_arred,
        repasse_ativo,
        repasse_passivo,
        grupo_excluido,
        nome_consorciada="",
        sheet_name="",
    ):
        """Executa a conversão"""
        try:
            self.status_var.set("⏳ Processando...")
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            
            self._log("=" * 70)
            self._log(f"INICIANDO CONVERSÃO")
            self._log("=" * 70)
            self._log(f"Arquivo: {Path(arquivo).name}")
            if nome_consorciada:
                self._log(f"Consorciada: {nome_consorciada}")
            self._log(f"Percentual: {percentual*100:.1f}%")
            self._log(f"Empresa: {empresa}, Obra: {obra}")
            self._log(f"Conta Arredondamento: {conta_arred}")
            if sheet_name:
                self._log(f"Planilha de entrada: {sheet_name}")
            
            # Informar se há filtro de exclusão de grupo
            if repasse_ativo and repasse_passivo and grupo_excluido:
                self._log(f"\n⚙️ FILTRO DE EXCLUSÃO ATIVO:")
                self._log(f"  Grupo a Excluir: {grupo_excluido}")
                self._log(f"  Conta Repasse Passivo: {repasse_passivo}")
                self._log(f"  Conta Repasse Ativo: {repasse_ativo}")
                self._log(f"  → Lançamentos do grupo serão excluídos")
                self._log(f"  → EXCETO repasse passivo → será reclassificado para ativo (100%)\n")
            
            conversao = self.service.executar_conversao(
                arquivo,
                percentual,
                empresa,
                obra,
                conta_arred,
                repasse_ativo,
                repasse_passivo,
                grupo_excluido,
                sheet_name=sheet_name,
                account_substitutions=self.account_substitutions,
                input_layouts=self.input_layouts,
                progress_callback=self._emit_progress_threadsafe,
            )
            resultado = conversao["resultado"]
            captured_text = conversao["log_capturado"]
            if captured_text:
                # Enviar todo output para o log
                for line in captured_text.strip().split('\n'):
                    self._log(line)
            
            # Detectar se há aviso de grupo não encontrado
            tem_aviso_grupo = conversao["tem_aviso_grupo"]
            
            # Salvar arquivo de saída
            saida_dir = Path(self.output_dir)
            saida_dir.mkdir(parents=True, exist_ok=True)
            
            # Incluir nome da consorciada no arquivo de saída
            if nome_consorciada:
                nome_saida = f"{Path(arquivo).stem} - {nome_consorciada} - Convertido.xlsx"
            else:
                nome_saida = f"{Path(arquivo).stem} - Convertido.xlsx"
            arquivo_saida = saida_dir / nome_saida
            self._emit_progress_threadsafe(0.95, "Salvando arquivo de saída")
            resultado.to_excel(arquivo_saida, index=False)
            self._maybe_rename_output_sheet(arquivo_saida)
            self._emit_progress_threadsafe(1.0, "Conversão concluída")
            
            self._log(f"\n✓ Arquivo salvo com sucesso!")
            self._log(f"Saída: {arquivo_saida}")
            self._log(f"Lançamentos processados: {len(resultado)}")
            self._log("=" * 70)
            
            # Atualizar cadastro se checkbox memorizar estiver marcado
            self._salvar_conta_memorizada_se_necessario(conta_arred)
            
            self.status_var.set(f"✓ Conversão concluída - {len(resultado)} lançamentos")
            
            # Mostrar mensagem apropriada
            if tem_aviso_grupo:
                self._show_warning(
                    "Conversão Concluída com Aviso", 
                    f"Conversão realizada com sucesso!\n" \
                    f"{len(resultado)} lançamentos processados\n\n" \
                    f"⚠️ AVISO: Grupo para exclusão não foi encontrado no arquivo.\n" \
                    f"O filtro de exclusão não foi aplicado."
                )
            else:
                self._show_info("Sucesso", f"Conversão realizada!\n{len(resultado)} lançamentos processados")
            
        except PermissionError as e:
            self._log(f"\n✗ ERRO DE PERMISSÃO: {e}")
            self.status_var.set(f"✗ Arquivo bloqueado")
            self._show_error("Erro de Permissão", str(e))
        except FileNotFoundError as e:
            self._log(f"\n✗ ARQUIVO NÃO ENCONTRADO: {e}")
            self.status_var.set(f"✗ Arquivo não encontrado")
            self._show_error("Arquivo Não Encontrado", str(e))
        except ConversaoErro as e:
            self._log(f"\n✗ ERRO: {e}")
            self.status_var.set(f"✗ Erro na conversão")
            self._show_error("Erro", f"Erro na conversão:\n{e}")
            log_event(self.logger, 40, "ui_conversao_falhou", etapa="ui", arquivo=arquivo)
        finally:
            self.root.after(0, lambda: self._set_busy_state(False, self.status_var.get()))
    
    def _salvar_conta_memorizada_se_necessario(self, conta_arred):
        """Salva a conta de arredondamento no cadastro se a flag memorizar estiver marcada"""
        try:
            # Se checkbox não está marcado, não fazer nada
            if not self.memorizar_conta_var.get():
                self._log("  (Conta não memorizada - checkbox desmarcada)")
                return
            
            # Se não há cadastro selecionado, não fazer nada
            cadastro_selecionado = self.cadastro_var.get()
            if not cadastro_selecionado:
                self._log("  (Nenhum cadastro selecionado para memorizar)")
                return

            self.service.memorizar_conta(cadastro_selecionado, conta_arred, True)
            
            self._log(f"✓ Conta de arredondamento '{conta_arred}' MEMORIZADA no cadastro '{cadastro_selecionado}'")
        except (CadastroErro, ConfiguracaoErro) as e:
            # Não interromper o processo se houver erro ao salvar
            self._log(f"⚠ Aviso: Não foi possível memorizar a conta: {e}")
    
    def _processar_pasta(self):
        """Processa todos os arquivos da pasta entrada/"""
        if not self._validate_account_inputs(
            self.conta_arred_var.get().strip(),
            self.conta_repasse_ativo_var.get().strip(),
            self.conta_repasse_passivo_var.get().strip(),
            self.grupo_excluido_var.get().strip(),
        ):
            return

        conta_arred = self.conta_arred_var.get().strip()
        try:
            percentual, empresa, obra, conta_arred = self.service.parse_config(
                self.percentual_var.get(),
                self.empresa_var.get(),
                self.obra_var.get(),
                conta_arred,
            )
        except ConfiguracaoErro as e:
            self._show_error("Erro", str(e))
            return

        self._set_busy_state(True, "⏳ Processando pasta...")
        
        thread = threading.Thread(target=self._run_batch_conversion, 
                                 args=(percentual, empresa, obra, conta_arred, self.cadastro_var.get().strip()))
        thread.daemon = True
        thread.start()
    
    def _run_batch_conversion(self, percentual, empresa, obra, conta_arred, nome_consorciada=""):
        """Processa lote de arquivos"""
        try:
            self.status_var.set("⏳ Processando pasta...")
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            
            self._log("=" * 70)
            self._log(f"PROCESSAMENTO EM LOTE")
            self._log("=" * 70)
            if nome_consorciada:
                self._log(f"Consorciada: {nome_consorciada}")
            self._log(f"Percentual: {percentual*100:.1f}%")
            self._log(f"Empresa: {empresa}, Obra: {obra}")
            self._log(f"Conta Arredondamento: {conta_arred}\n")
            
            self.service.executar_lote(
                percentual,
                empresa,
                obra,
                conta_arred,
                nome_consorciada,
                account_substitutions=self.account_substitutions,
                input_layouts=self.input_layouts,
                progress_callback=self._emit_progress_threadsafe,
            )
            
            self._log("\n✓ Processamento em lote concluído!")
            self.status_var.set("✓ Processamento em lote concluído")
            self._show_info("Sucesso", "Todos os arquivos foram processados!")
            
        except PermissionError as e:
            self._log(f"\n✗ ERRO DE PERMISSÃO: {e}")
            self.status_var.set("✗ Arquivo bloqueado")
            self._show_error("Erro de Permissão", str(e))
        except FileNotFoundError as e:
            self._log(f"\n✗ ARQUIVO NÃO ENCONTRADO: {e}")
            self.status_var.set("✗ Arquivo não encontrado")
            self._show_error("Arquivo Não Encontrado", str(e))
        except ConversaoErro as e:
            self._log(f"\n✗ ERRO: {e}")
            self.status_var.set("✗ Erro no processamento")
            self._show_error("Erro", f"Erro:\n{e}")
            log_event(self.logger, 40, "ui_lote_falhou", etapa="ui")
        finally:
            self.root.after(0, lambda: self._set_busy_state(False, self.status_var.get()))
    
    def _open_output_dir(self):
        """Abre pasta de saída"""
        saida_dir = Path(self.output_dir)
        saida_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(saida_dir))
        self._log(f"📂 Abrindo pasta: {saida_dir}")

    def _open_input_dir(self):
        """Abre pasta de entrada"""
        entrada_dir = Path(self.input_dir)
        entrada_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(entrada_dir))
        self._log(f"📂 Abrindo pasta: {entrada_dir}")

    def _open_folder_settings_dialog(self):
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Configurações")
        dialog.geometry("700x360")
        dialog.minsize(660, 320)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(fg_color=self.palette["bg_principal"])

        box = ctk.CTkFrame(
            dialog,
            fg_color=self.palette["bg_frames"],
            border_width=2,
            border_color=self.palette["accent"],
            corner_radius=12,
        )
        box.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(
            box,
            text="Configurações de Pastas e Contas",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=self.palette["fg_light"],
        ).pack(anchor="w", padx=14, pady=(12, 8))

        entrada_var = tk.StringVar(value=self.input_dir)
        saida_var = tk.StringVar(value=self.output_dir)

        def choose_entrada():
            selected = filedialog.askdirectory(title="Selecione a pasta de Entrada", initialdir=entrada_var.get())
            if selected:
                entrada_var.set(selected)

        def choose_saida():
            selected = filedialog.askdirectory(title="Selecione a pasta de Saída", initialdir=saida_var.get())
            if selected:
                saida_var.set(selected)

        for titulo, var, cmd in (
            ("Entrada", entrada_var, choose_entrada),
            ("Saída", saida_var, choose_saida),
        ):
            row = ctk.CTkFrame(box, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=6)
            ctk.CTkLabel(row, text=titulo, width=70, anchor="w").pack(side="left")
            ctk.CTkEntry(row, textvariable=var, fg_color=self.palette["bg_input"]).pack(side="left", fill="x", expand=True, padx=(6, 8))
            ctk.CTkButton(
                row,
                text="Selecionar",
                width=110,
                fg_color=self.palette["accent"],
                hover_color=self.palette["accent_hover"],
                text_color=self.palette["button_text"],
                font=self.font_button,
                command=cmd,
            ).pack(side="left")

        row_subs = ctk.CTkFrame(box, fg_color="transparent")
        row_subs.pack(fill="x", padx=14, pady=(6, 8))
        ctk.CTkLabel(row_subs, text="Substituições", width=70, anchor="w").pack(side="left")
        qtd_var = tk.StringVar(value=f"{len(self.account_substitutions)} regra(s) configurada(s)")
        ctk.CTkLabel(row_subs, textvariable=qtd_var, text_color=self.palette["muted"]).pack(side="left", padx=(6, 8))

        def open_substitutions_dialog():
            self._open_account_substitutions_dialog(parent=dialog)
            qtd_var.set(f"{len(self.account_substitutions)} regra(s) configurada(s)")

        ctk.CTkButton(
            row_subs,
            text="Gerenciar",
            width=110,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=open_substitutions_dialog,
        ).pack(side="right")

        row_layouts = ctk.CTkFrame(box, fg_color="transparent")
        row_layouts.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkLabel(row_layouts, text="Layouts", width=70, anchor="w").pack(side="left")
        qtd_layouts_var = tk.StringVar(value=f"{len(self.input_layouts)} layout(s) configurado(s)")
        ctk.CTkLabel(row_layouts, textvariable=qtd_layouts_var, text_color=self.palette["muted"]).pack(side="left", padx=(6, 8))

        def open_layouts_dialog():
            self._open_input_layouts_dialog(parent=dialog)
            qtd_layouts_var.set(f"{len(self.input_layouts)} layout(s) configurado(s)")

        ctk.CTkButton(
            row_layouts,
            text="Gerenciar",
            width=110,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=open_layouts_dialog,
        ).pack(side="right")

        footer = ctk.CTkFrame(box, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(6, 10))

        def save_and_close():
            self.input_dir = entrada_var.get().strip() or str(self.base_dir / "entrada")
            self.output_dir = saida_var.get().strip() or str(self.base_dir / "saida")
            Path(self.input_dir).mkdir(parents=True, exist_ok=True)
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)
            self._save_folder_settings()
            self._log(f"✓ Pasta de entrada configurada: {self.input_dir}")
            self._log(f"✓ Pasta de saída configurada: {self.output_dir}")
            dialog.destroy()

        ctk.CTkButton(
            footer,
            text="Cancelar",
            width=110,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=dialog.destroy,
        ).pack(side="right", padx=4)
        ctk.CTkButton(
            footer,
            text="Salvar",
            width=110,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=save_and_close,
        ).pack(side="right", padx=4)

    def _open_account_substitution_form(self, parent, initial: dict[str, str] | None = None) -> dict[str, str] | None:
        dialog = ctk.CTkToplevel(parent)
        dialog.title("Substituição de Conta")
        dialog.geometry("620x260")
        dialog.minsize(560, 240)
        dialog.transient(parent)
        dialog.grab_set()
        dialog.configure(fg_color=self.palette["bg_principal"])

        box = ctk.CTkFrame(
            dialog,
            fg_color=self.palette["bg_frames"],
            border_width=2,
            border_color=self.palette["accent"],
            corner_radius=12,
        )
        box.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(
            box,
            text="Defina a regra de substituição",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=self.palette["fg_light"],
        ).pack(anchor="w", padx=14, pady=(12, 8))

        origem_var = tk.StringVar(value=str((initial or {}).get("de", "")))
        destino_var = tk.StringVar(value=str((initial or {}).get("para", "")))
        self._attach_mask_var(origem_var, self._format_account_value)
        self._attach_mask_var(destino_var, self._format_account_value)

        for titulo, var in (("De", origem_var), ("Para", destino_var)):
            row = ctk.CTkFrame(box, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=6)
            ctk.CTkLabel(row, text=titulo, width=60, anchor="w").pack(side="left")
            ctk.CTkEntry(
                row,
                textvariable=var,
                fg_color=self.palette["bg_input"],
                placeholder_text="x.x.xx.xx.xxxxxx",
            ).pack(side="left", fill="x", expand=True)

        result = {"value": None}

        def save_rule():
            origem = self._format_account_value(origem_var.get().strip())
            destino = self._format_account_value(destino_var.get().strip())
            ok, msg = self._validate_account_substitution(origem, destino)
            if not ok:
                self._show_error("Erro", msg, parent=dialog)
                return
            result["value"] = {"de": origem, "para": destino}
            dialog.destroy()

        footer = ctk.CTkFrame(box, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(8, 12))
        ctk.CTkButton(
            footer,
            text="Cancelar",
            width=110,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=dialog.destroy,
        ).pack(side="right", padx=4)
        ctk.CTkButton(
            footer,
            text="Salvar",
            width=110,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=save_rule,
        ).pack(side="right", padx=4)

        dialog.wait_window()
        return result["value"]

    def _open_account_substitutions_dialog(self, parent=None) -> None:
        owner = parent or self.root
        dialog = ctk.CTkToplevel(owner)
        dialog.title("Substituições de Conta")
        dialog.geometry("760x420")
        dialog.minsize(700, 360)
        dialog.transient(owner)
        dialog.grab_set()
        dialog.configure(fg_color=self.palette["bg_principal"])

        box = ctk.CTkFrame(
            dialog,
            fg_color=self.palette["bg_frames"],
            border_width=2,
            border_color=self.palette["accent"],
            corner_radius=12,
        )
        box.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(
            box,
            text="Regras de Substituição de Conta",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=self.palette["fg_light"],
        ).pack(anchor="w", padx=14, pady=(12, 8))

        work_rules = [dict(item) for item in self.account_substitutions]
        list_frame = ctk.CTkScrollableFrame(box, fg_color=self.palette["bg_principal"])
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        def render_rules():
            for child in list_frame.winfo_children():
                child.destroy()

            if not work_rules:
                ctk.CTkLabel(
                    list_frame,
                    text="Nenhuma regra cadastrada",
                    text_color=self.palette["muted"],
                ).pack(anchor="w", padx=8, pady=8)
                return

            for idx, rule in enumerate(work_rules):
                row = ctk.CTkFrame(list_frame, fg_color="transparent")
                row.pack(fill="x", padx=6, pady=4)

                ctk.CTkLabel(
                    row,
                    text=f"{rule['de']}  ->  {rule['para']}",
                    anchor="w",
                    text_color=self.palette["fg_light"],
                    font=self.font_body,
                ).pack(side="left", fill="x", expand=True)

                def edit_rule(i=idx):
                    updated = self._open_account_substitution_form(dialog, initial=work_rules[i])
                    if updated:
                        work_rules[i] = updated
                        render_rules()

                def delete_rule(i=idx):
                    if not self._ask_yes_no("Confirmação", "Deseja excluir esta regra?", parent=dialog):
                        return
                    del work_rules[i]
                    render_rules()

                ctk.CTkButton(
                    row,
                    text="Editar",
                    width=90,
                    fg_color=self.palette["accent"],
                    hover_color=self.palette["accent_hover"],
                    text_color=self.palette["button_text"],
                    font=self.font_button,
                    command=edit_rule,
                ).pack(side="right", padx=4)
                ctk.CTkButton(
                    row,
                    text="Excluir",
                    width=90,
                    fg_color=self.palette["accent"],
                    hover_color=self.palette["accent_hover"],
                    text_color=self.palette["button_text"],
                    font=self.font_button,
                    command=delete_rule,
                ).pack(side="right", padx=4)

        render_rules()

        footer = ctk.CTkFrame(box, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(0, 12))

        def add_rule():
            novo = self._open_account_substitution_form(dialog)
            if not novo:
                return
            if any(r["de"] == novo["de"] for r in work_rules):
                self._show_error("Erro", "Já existe regra para esta conta de origem", parent=dialog)
                return
            work_rules.append(novo)
            render_rules()

        def save_rules():
            self.account_substitutions = work_rules
            self._save_folder_settings()
            self._log(f"✓ Regras de substituição atualizadas: {len(self.account_substitutions)}")
            dialog.destroy()

        ctk.CTkButton(
            footer,
            text="Adicionar",
            width=110,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=add_rule,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            footer,
            text="Cancelar",
            width=110,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=dialog.destroy,
        ).pack(side="right", padx=4)
        ctk.CTkButton(
            footer,
            text="Salvar",
            width=110,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=save_rules,
        ).pack(side="right", padx=4)

    def _open_input_layout_form(self, parent, initial: dict[str, list[str]] | None = None) -> dict[str, list[str]] | None:
        dialog = ctk.CTkToplevel(parent)
        dialog.title("Layout de Entrada")
        dialog.geometry("680x340")
        dialog.minsize(620, 320)
        dialog.transient(parent)
        dialog.grab_set()
        dialog.configure(fg_color=self.palette["bg_principal"])

        box = ctk.CTkFrame(
            dialog,
            fg_color=self.palette["bg_frames"],
            border_width=2,
            border_color=self.palette["accent"],
            corner_radius=12,
        )
        box.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(
            box,
            text="Defina o nome do layout e os termos de reconhecimento",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=self.palette["fg_light"],
        ).pack(anchor="w", padx=14, pady=(12, 8))

        nome_var = tk.StringVar(value=str((initial or {}).get("nome", "")))
        termos_iniciais = ", ".join((initial or {}).get("termos", []))
        termos_var = tk.StringVar(value=termos_iniciais)

        row_nome = ctk.CTkFrame(box, fg_color="transparent")
        row_nome.pack(fill="x", padx=14, pady=6)
        ctk.CTkLabel(row_nome, text="Nome", width=90, anchor="w").pack(side="left")
        ctk.CTkEntry(
            row_nome,
            textvariable=nome_var,
            fg_color=self.palette["bg_input"],
            placeholder_text="Ex.: Fiscal",
        ).pack(side="left", fill="x", expand=True)

        row_termos = ctk.CTkFrame(box, fg_color="transparent")
        row_termos.pack(fill="x", padx=14, pady=6)
        ctk.CTkLabel(row_termos, text="Termos", width=90, anchor="w").pack(side="left")
        ctk.CTkEntry(
            row_termos,
            textvariable=termos_var,
            fg_color=self.palette["bg_input"],
            placeholder_text="Ex.: fiscal, ajuste societario, 19",
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            box,
            text="Separe os termos por vírgula, ponto e vírgula ou quebra de linha.",
            text_color=self.palette["muted"],
        ).pack(anchor="w", padx=14, pady=(0, 6))

        result = {"value": None}

        def save_layout():
            nome = nome_var.get().strip()
            termos = [part.strip() for part in re.split(r"[;,\n]+", termos_var.get()) if part.strip()]
            layout_sanitizado = self._sanitize_input_layouts([{"nome": nome, "termos": termos}])
            if not layout_sanitizado:
                self._show_error("Erro", "Informe um nome e pelo menos um termo de reconhecimento", parent=dialog)
                return
            result["value"] = layout_sanitizado[0]
            dialog.destroy()

        footer = ctk.CTkFrame(box, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(8, 12))
        ctk.CTkButton(
            footer,
            text="Cancelar",
            width=110,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=dialog.destroy,
        ).pack(side="right", padx=4)
        ctk.CTkButton(
            footer,
            text="Salvar",
            width=110,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=save_layout,
        ).pack(side="right", padx=4)

        dialog.wait_window()
        return result["value"]

    def _open_input_layouts_dialog(self, parent=None) -> None:
        owner = parent or self.root
        dialog = ctk.CTkToplevel(owner)
        dialog.title("Layouts de Entrada")
        dialog.geometry("780x440")
        dialog.minsize(720, 380)
        dialog.transient(owner)
        dialog.grab_set()
        dialog.configure(fg_color=self.palette["bg_principal"])

        box = ctk.CTkFrame(
            dialog,
            fg_color=self.palette["bg_frames"],
            border_width=2,
            border_color=self.palette["accent"],
            corner_radius=12,
        )
        box.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(
            box,
            text="Layouts de Entrada (Reconhecimento Automático)",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=self.palette["fg_light"],
        ).pack(anchor="w", padx=14, pady=(12, 8))

        work_layouts = [
            {"nome": layout["nome"], "termos": list(layout["termos"])}
            for layout in self.input_layouts
        ]
        list_frame = ctk.CTkScrollableFrame(box, fg_color=self.palette["bg_principal"])
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        def render_layouts():
            for child in list_frame.winfo_children():
                child.destroy()

            if not work_layouts:
                ctk.CTkLabel(
                    list_frame,
                    text="Nenhum layout cadastrado",
                    text_color=self.palette["muted"],
                ).pack(anchor="w", padx=8, pady=8)
                return

            for idx, layout in enumerate(work_layouts):
                row = ctk.CTkFrame(list_frame, fg_color="transparent")
                row.pack(fill="x", padx=6, pady=4)

                termos_texto = ", ".join(layout["termos"])
                ctk.CTkLabel(
                    row,
                    text=f"{layout['nome']} | {termos_texto}",
                    anchor="w",
                    text_color=self.palette["fg_light"],
                    font=self.font_body,
                ).pack(side="left", fill="x", expand=True)

                def edit_layout(i=idx):
                    updated = self._open_input_layout_form(dialog, initial=work_layouts[i])
                    if not updated:
                        return
                    for j, existing in enumerate(work_layouts):
                        if j == i:
                            continue
                        if existing["nome"].casefold() == updated["nome"].casefold():
                            self._show_error("Erro", "Já existe layout com este nome", parent=dialog)
                            return
                    work_layouts[i] = updated
                    render_layouts()

                def delete_layout(i=idx):
                    if not self._ask_yes_no("Confirmação", "Deseja excluir este layout?", parent=dialog):
                        return
                    del work_layouts[i]
                    render_layouts()

                ctk.CTkButton(
                    row,
                    text="Editar",
                    width=90,
                    fg_color=self.palette["accent"],
                    hover_color=self.palette["accent_hover"],
                    text_color=self.palette["button_text"],
                    font=self.font_button,
                    command=edit_layout,
                ).pack(side="right", padx=4)
                ctk.CTkButton(
                    row,
                    text="Excluir",
                    width=90,
                    fg_color=self.palette["accent"],
                    hover_color=self.palette["accent_hover"],
                    text_color=self.palette["button_text"],
                    font=self.font_button,
                    command=delete_layout,
                ).pack(side="right", padx=4)

        render_layouts()

        footer = ctk.CTkFrame(box, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(0, 12))

        def add_layout():
            novo = self._open_input_layout_form(dialog)
            if not novo:
                return
            if any(layout["nome"].casefold() == novo["nome"].casefold() for layout in work_layouts):
                self._show_error("Erro", "Já existe layout com este nome", parent=dialog)
                return
            work_layouts.append(novo)
            render_layouts()

        def save_layouts():
            sane = self._sanitize_input_layouts(work_layouts)
            if not sane:
                self._show_error("Erro", "Cadastre ao menos um layout com termos válidos", parent=dialog)
                return
            self.input_layouts = sane
            self._save_folder_settings()
            self._log(f"✓ Layouts de entrada atualizados: {len(self.input_layouts)}")
            dialog.destroy()

        ctk.CTkButton(
            footer,
            text="Adicionar",
            width=110,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=add_layout,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            footer,
            text="Cancelar",
            width=110,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=dialog.destroy,
        ).pack(side="right", padx=4)
        ctk.CTkButton(
            footer,
            text="Salvar",
            width=110,
            fg_color=self.palette["accent"],
            hover_color=self.palette["accent_hover"],
            text_color=self.palette["button_text"],
            font=self.font_button,
            command=save_layouts,
        ).pack(side="right", padx=4)
    
    def _clear_log(self):
        """Limpa o log"""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.status_var.set("Pronto")
    
    def _criar_cadastros_padrao(self):
        """Cria arquivo de cadastros padrão"""
        try:
            self.repository.write_data(self.repository.default_data())
            self._log(f"✓ Arquivo de cadastros criado com exemplos padrão")
            self._load_cadastros()
        except (CadastroErro, PersistenciaErro) as e:
            self._log(f"✗ Erro ao criar cadastros padrão: {e}")


def show_splash_screen(root):
    """Exibe splash screen com GIF animado por 2.5 segundos"""
    logger = get_logger(__name__)
    try:
        # Criar janela splash
        splash = tk.Toplevel()
        splash.title("")
        splash.overrideredirect(True)  # Remove bordas e barra de título
        
        # Tentar carregar o GIF
        gif_path = get_resource_path("icon", "Intro.gif")
        
        if not gif_path.exists():
            # Se não encontrar o GIF, pula o splash
            splash.destroy()
            return
        
        # Abrir GIF com PIL
        gif = Image.open(str(gif_path))
        
        # Extrair frames e duração
        frames = []
        try:
            while True:
                frame = gif.copy()
                frames.append(ImageTk.PhotoImage(frame))
                gif.seek(len(frames))  # Próximo frame
        except EOFError:
            pass  # Fim dos frames
        
        if not frames:
            splash.destroy()
            return
        
        # Definir tamanho da janela baseado no primeiro frame
        width = frames[0].width()
        height = frames[0].height()
        
        # Centralizar na tela
        screen_width = splash.winfo_screenwidth()
        screen_height = splash.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        splash.geometry(f"{width}x{height}+{x}+{y}")
        splash.configure(bg='#0a1628')
        
        # Label para exibir os frames
        label = tk.Label(splash, bg="#0a1628", bd=0)
        label.pack()
        
        # Variáveis de controle
        frame_index = [0]
        is_running = [True]
        
        def animate():
            if not is_running[0]:
                return
            
            # Atualizar frame
            label.configure(image=frames[frame_index[0]])
            frame_index[0] = (frame_index[0] + 1) % len(frames)
            
            # Próximo frame (assumindo ~40ms por frame = 25fps)
            splash.after(40, animate)
        
        # Iniciar animação
        animate()
        
        # Fechar após 2500ms (2.5 segundos)
        def close_splash():
            is_running[0] = False
            try:
                splash.attributes('-topmost', False)
            except tk.TclError:
                pass
            splash.destroy()
        
        splash.after(2500, close_splash)
        
        # Mostrar splash na frente de tudo
        splash.lift()
        splash.attributes('-topmost', True)
        
    except (tk.TclError, OSError, RuntimeError, ValueError) as e:
        # Se houver qualquer erro, apenas ignora o splash
        print(f"Splash screen error: {e}")
        log_event(logger, 30, "ui_splash_falhou", etapa="ui")
        if 'splash' in locals():
            splash.destroy()


def main():
    logger = get_logger(__name__)
    root = ctk.CTk()
    root.attributes('-topmost', False)

    # Evita comportamento de janela "sempre na frente" ao alternar aplicativos.
    root.bind("<FocusOut>", lambda _e: root.attributes('-topmost', False))
    root.withdraw()  # Ocultar janela principal temporariamente
    
    # Definir ícone customizado (formato .ico funciona melhor na barra de tarefas)
    try:
        icon_path = get_resource_path("icon", "app_icon.ico")
        if icon_path.exists():
            root.iconbitmap(str(icon_path))
    except (tk.TclError, OSError) as e:
        print(f"Aviso: Não foi possível carregar ícone: {e}")
        log_event(logger, 30, "ui_icone_falhou", etapa="ui")
    
    # Mostrar splash screen
    show_splash_screen(root)
    
    # Aguardar splash terminar (2.5s) + buffer
    root.after(2600, lambda: root.deiconify())  # Mostrar janela principal
    root.after(2620, lambda: root.attributes('-topmost', False))
    
    app = TelaConversor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
