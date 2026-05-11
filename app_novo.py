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
- app_novo.py (ESTE): Interface gráfica + controle
- Conversor.py: Motor de conversão e cálculos
- config.py: 13 contas sagradas (não modificar)
- cadastros.json: Persistência de cadastros

USO:
    python app_novo.py
    ou
    Clicar em INICIAR.bat
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import threading
import os
import sys
from PIL import Image, ImageTk

from camadas.persistencia import CadastrosRepository
from camadas.servico import ConversorAppService
from erros import CadastroErro, ConfiguracaoErro, ConversaoErro, PersistenciaErro
from observabilidade import get_logger, log_event


def get_runtime_base_dir():
    """Retorna a pasta persistente da aplicação."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


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

    base_dir = get_runtime_base_dir()
    local_file = base_dir / "cadastros.local.json"
    if local_file.exists():
        return local_file

    return base_dir / "cadastros.json"

class TelaConversor:
    def __init__(self, root):
        self.root = root
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
        
        # Estilo Dark
        self._setup_dark_theme()
        
        self._create_widgets()
        self._load_cadastros()
        self._mostrar_boas_vindas()
    
    def _setup_dark_theme(self):
        """Configura tema dark profissional - Azul Escuro + Laranja"""
        style = ttk.Style()
        
        # Paleta de cores: Dark Blue + Orange
        bg_principal = "#0a1628"      # Azul escuro muito escuro (quase preto)
        bg_frames = "#132440"          # Azul escuro para frames
        bg_input = "#1e3a5f"           # Azul escuro médio para campos
        fg_light = "#e8eef5"           # Texto branco azulado
        accent_orange = "#ff6b35"      # Laranja vibrante (accent principal)
        hover_orange = "#e55a2b"       # Laranja escuro (hover)
        border_color = "#2d4a6f"       # Bordas azul médio
        bg_button = "#ff6b35"          # Botões laranja
        
        # Fundo da janela principal
        self.root.configure(bg=bg_principal)
        
        # Configurar tema clam como base
        style.theme_use('clam')
        
        # Frames e Labels
        style.configure('TFrame', background=bg_principal, foreground=fg_light)
        style.configure('TLabelFrame', background=bg_frames, foreground=fg_light, borderwidth=2, relief="solid", bordercolor=border_color)
        style.configure('TLabelFrame.Label', background=bg_frames, foreground=accent_orange, font=('TkDefaultFont', 10, 'bold'))
        style.configure('TLabel', background=bg_frames, foreground=fg_light)
        
        # Botões com laranja vibrante
        style.configure('TButton', 
                       background=bg_button, 
                       foreground="#ffffff",
                       borderwidth=0, 
                       padding=8,
                       relief="flat",
                       focuscolor='none',
                       font=('TkDefaultFont', 9, 'bold'))
        style.map('TButton',
                 background=[('active', hover_orange), ('pressed', '#d14d1f'), ('disabled', '#4a4a4a')],
                 foreground=[('active', '#ffffff'), ('disabled', '#808080')])
        
        # Entrada de texto
        style.configure('TEntry', 
                       fieldbackground=bg_input, 
                       background=bg_input,
                       foreground=fg_light, 
                       borderwidth=1, 
                       padding=5,
                       relief="solid",
                       insertcolor=accent_orange)
        
        # Spinbox
        style.configure('TSpinbox', 
                       fieldbackground=bg_input, 
                       background=bg_input,
                       foreground=fg_light, 
                       borderwidth=1,
                       relief="solid",
                       insertcolor=accent_orange)
        
        # Combobox
        style.configure('TCombobox', 
                       fieldbackground=bg_input, 
                       background=bg_input, 
                       foreground=fg_light,
                       borderwidth=1,
                       relief="solid",
                       arrowcolor=accent_orange)
        
        # Checkbutton (para flags)
        style.configure('TCheckbutton', 
                       background=bg_frames, 
                       foreground=fg_light,
                       focuscolor='none',
                       relief="flat")
        style.map('TCheckbutton',
                 background=[('active', bg_frames)],
                 foreground=[('active', accent_orange)])
        
        # Text widget (log)
        style.configure('TText', 
                       background=bg_input, 
                       foreground=fg_light, 
                       borderwidth=1,
                       relief="solid",
                       insertcolor=accent_orange)
        
        # Scrollbar
        style.configure('Vertical.TScrollbar', 
                       background=bg_input, 
                       troughcolor=bg_principal,
                       borderwidth=0,
                       arrowcolor=accent_orange)
        style.configure('Horizontal.TScrollbar', 
                       background=bg_input, 
                       troughcolor=bg_principal,
                       borderwidth=0,
                       arrowcolor=accent_orange)

    def _get_app_base_dir(self):
        """Retorna a pasta base do app (suporta modo empacotado)"""
        return get_runtime_base_dir()

    def _ensure_cadastros_file(self):
        """Garante um arquivo de cadastros persistente ao lado do executável."""
        bundled_file = get_resource_path("cadastros.json")
        self.repository.ensure_file_exists(bundled_file)

    def _ensure_app_dirs(self):
        """Garante que pastas essenciais existam"""
        for pasta in ("entrada", "saida"):
            (self.base_dir / pasta).mkdir(parents=True, exist_ok=True)
        
    def _create_widgets(self):
        """Cria os elementos da interface"""
        
        # ===== FRAME SUPERIOR: SELEÇÃO DE ARQUIVO =====
        frame_arquivo = ttk.LabelFrame(self.root, text="📁 Arquivo de Entrada", padding=10)
        frame_arquivo.pack(fill="x", padx=10, pady=5)
        
        self.archivo_var = tk.StringVar(value="")
        entry_arquivo = ttk.Entry(frame_arquivo, textvariable=self.archivo_var, width=60, state="readonly")
        entry_arquivo.pack(side="left", fill="x", expand=True, padx=5)
        
        btn_browse = ttk.Button(frame_arquivo, text="Procurar", command=self._browse_file)
        btn_browse.pack(side="left", padx=5)
        
        btn_processar_pasta = ttk.Button(frame_arquivo, text="Processar Pasta", command=self._processar_pasta)
        btn_processar_pasta.pack(side="left", padx=5)
        
        # ===== FRAME CONFIGURAÇÕES: PERCENTUAL E EMPRESA =====
        frame_config = ttk.LabelFrame(self.root, text="⚙️ Configurações", padding=10)
        frame_config.pack(fill="x", padx=10, pady=5)
        
        # Linha 1: Percentual
        ttk.Label(frame_config, text="Percentual (%):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.percentual_var = tk.StringVar(value="50.0")
        spinbox_perc = ttk.Spinbox(frame_config, from_=0, to=100, textvariable=self.percentual_var, width=10)
        spinbox_perc.grid(row=0, column=1, sticky="w", padx=5)
        
        # Linha 2: Código Empresa
        ttk.Label(frame_config, text="Código Empresa:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.empresa_var = tk.StringVar(value="97")
        entry_empresa = ttk.Entry(frame_config, textvariable=self.empresa_var, width=10)
        entry_empresa.grid(row=1, column=1, sticky="w", padx=5)
        
        # Linha 3: Código Obra
        ttk.Label(frame_config, text="Código Obra:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.obra_var = tk.StringVar(value="972")
        entry_obra = ttk.Entry(frame_config, textvariable=self.obra_var, width=10)
        entry_obra.grid(row=2, column=1, sticky="w", padx=5)
        
        # Linha 4: Conta de Arredondamento
        ttk.Label(frame_config, text="Conta Arredondamento:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.conta_arred_var = tk.StringVar(value="")
        entry_conta_arred = ttk.Entry(frame_config, textvariable=self.conta_arred_var, width=20)
        entry_conta_arred.grid(row=3, column=1, sticky="w", padx=5)
        ttk.Label(frame_config, text="(ex: 1.1.01.01.000001)", font=("Courier", 8)).grid(row=3, column=2, sticky="w", padx=2)
        
        # Linha 5: Checkbox Memorizar Conta
        self.memorizar_conta_var = tk.BooleanVar(value=False)
        check_memorizar = ttk.Checkbutton(frame_config, text="Memorizar esta conta de arredondamento", 
                                          variable=self.memorizar_conta_var)
        check_memorizar.grid(row=4, column=0, columnspan=3, sticky="w", padx=5, pady=5)
        
        # Linha 6: Conta de Repasse do Ativo
        ttk.Label(frame_config, text="Conta Repasse Ativo:").grid(row=5, column=0, sticky="w", padx=5, pady=5)
        self.conta_repasse_ativo_var = tk.StringVar(value="")
        entry_repasse_ativo = ttk.Entry(frame_config, textvariable=self.conta_repasse_ativo_var, width=20)
        entry_repasse_ativo.grid(row=5, column=1, sticky="w", padx=5)
        
        # Linha 7: Conta de Repasse do Passivo
        ttk.Label(frame_config, text="Conta Repasse Passivo:").grid(row=6, column=0, sticky="w", padx=5, pady=5)
        self.conta_repasse_passivo_var = tk.StringVar(value="")
        entry_repasse_passivo = ttk.Entry(frame_config, textvariable=self.conta_repasse_passivo_var, width=20)
        entry_repasse_passivo.grid(row=6, column=1, sticky="w", padx=5)
        
        # Linha 8: Grupo a ser Excluído
        ttk.Label(frame_config, text="Grupo a ser Excluído:").grid(row=7, column=0, sticky="w", padx=5, pady=5)
        self.grupo_excluido_var = tk.StringVar(value="")
        entry_grupo_excluido = ttk.Entry(frame_config, textvariable=self.grupo_excluido_var, width=20)
        entry_grupo_excluido.grid(row=7, column=1, sticky="w", padx=5)
        
        # ===== FRAME CADASTROS: PRESETS DE CONSORCIADAS =====
        frame_cadastros = ttk.LabelFrame(self.root, text="📋 Cadastros Rápidos", padding=10)
        frame_cadastros.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(frame_cadastros, text="Consorciada:").pack(side="left", padx=5)
        self.cadastro_var = tk.StringVar()
        self.combo_cadastros = ttk.Combobox(frame_cadastros, textvariable=self.cadastro_var, 
                                            state="readonly", width=30)
        self.combo_cadastros.pack(side="left", padx=5, fill="x", expand=True)
        self.combo_cadastros.bind('<<ComboboxSelected>>', self._on_cadastro_selected)
        
        btn_novo = ttk.Button(frame_cadastros, text="✨ Novo", command=self._new_cadastro)
        btn_novo.pack(side="left", padx=2)
        
        btn_editar = ttk.Button(frame_cadastros, text="✏️ Editar", command=self._edit_cadastro)
        btn_editar.pack(side="left", padx=2)
        
        btn_deletar = ttk.Button(frame_cadastros, text="🗑️ Deletar", command=self._delete_cadastro)
        btn_deletar.pack(side="left", padx=2)
        
        # ===== FRAME BOTÕES DE AÇÃO =====
        frame_botoes = ttk.Frame(self.root)
        frame_botoes.pack(fill="x", padx=10, pady=10)
        
        btn_converter = ttk.Button(frame_botoes, text="▶️ Converter", command=self._converter)
        btn_converter.pack(side="left", padx=5, ipadx=10, ipady=5)
        
        btn_abrir_saida = ttk.Button(frame_botoes, text="📂 Abrir Saída", command=self._open_output_dir)
        btn_abrir_saida.pack(side="left", padx=5, ipadx=10, ipady=5)
        
        btn_limpar_log = ttk.Button(frame_botoes, text="🗑️ Limpar Log", command=self._clear_log)
        btn_limpar_log.pack(side="left", padx=5, ipadx=10, ipady=5)
        
        btn_sair = ttk.Button(frame_botoes, text="❌ Sair", command=self.root.quit)
        btn_sair.pack(side="right", padx=5, ipadx=10, ipady=5)
        
        # ===== FRAME LOG: SAÍDA DO CONVERSOR =====
        frame_log = ttk.LabelFrame(self.root, text="📝 Log de Execução", padding=5)
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(frame_log)
        scrollbar.pack(side="right", fill="y")
        
        self.log_text = tk.Text(frame_log, height=15, width=100, yscrollcommand=scrollbar.set, 
                               bg="#f0f0f0", font=("Courier", 9))
        self.log_text.pack(fill="both", expand=True)
        scrollbar.config(command=self.log_text.yview)
        
        # Status bar
        self.status_var = tk.StringVar(value="Pronto")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken")
        status_bar.pack(fill="x", padx=1, pady=1)
        
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
            initialdir=self.base_dir / "entrada"
        )
        if arquivo:
            self.archivo_var.set(arquivo)
            self._log(f"✓ Arquivo selecionado: {Path(arquivo).name}")
    
    def _load_cadastros(self):
        """Carrega lista de cadastros do JSON"""
        try:
            nomes = self.service.carregar_nomes_cadastros()
            self.combo_cadastros['values'] = nomes
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
    
    def _new_cadastro(self):
        """Cria novo cadastro"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Novo Cadastro")
        dialog.geometry("550x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Variável para controlar se foi salvo
        foi_salvo = [False]
        
        def on_close():
            if not foi_salvo[0]:
                if messagebox.askyesno("Confirmar", "Fechar sem salvar?", parent=dialog):
                    dialog.destroy()
            else:
                dialog.destroy()
        
        dialog.protocol("WM_DELETE_WINDOW", on_close)
        
        # Criar canvas scrollável
        canvas = tk.Canvas(dialog, bg="#132440", highlightthickness=0)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Scroll com mouse
        def _on_mousewheel_dialog(event):
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _on_mousewheel_dialog)
        
        # Seção: Identificação do Consórcio
        frame_consortio = ttk.LabelFrame(scrollable_frame, text="🏢 Identificação do Consórcio", padding=15)
        frame_consortio.pack(fill="x", padx=15, pady=10)
        
        ttk.Label(frame_consortio, text="Nome do Consórcio:").grid(row=0, column=0, sticky="w", padx=5, pady=8)
        entry_nome_cons = ttk.Entry(frame_consortio, width=40)
        entry_nome_cons.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
        frame_consortio.columnconfigure(1, weight=1)
        
        ttk.Label(frame_consortio, text="Código do Consórcio:").grid(row=1, column=0, sticky="w", padx=5, pady=8)
        entry_cons = ttk.Entry(frame_consortio, width=40)
        entry_cons.grid(row=1, column=1, padx=5, pady=8, sticky="ew")
        
        ttk.Label(frame_consortio, text="Código da Obra:").grid(row=2, column=0, sticky="w", padx=5, pady=8)
        entry_obra_cons = ttk.Entry(frame_consortio, width=40)
        entry_obra_cons.grid(row=2, column=1, padx=5, pady=8, sticky="ew")
        
        # Seção: Dados da Consorciada
        frame_consorciada = ttk.LabelFrame(scrollable_frame, text="📊 Dados da Consorciada", padding=15)
        frame_consorciada.pack(fill="x", padx=15, pady=10)
        
        ttk.Label(frame_consorciada, text="Nome da Consorciada:").grid(row=0, column=0, sticky="w", padx=5, pady=8)
        entry_nome = ttk.Entry(frame_consorciada, width=40)
        entry_nome.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
        frame_consorciada.columnconfigure(1, weight=1)
        
        ttk.Label(frame_consorciada, text="Percentual (%):").grid(row=1, column=0, sticky="w", padx=5, pady=8)
        entry_perc = ttk.Spinbox(frame_consorciada, from_=0, to=100, width=10)
        entry_perc.set(50)
        entry_perc.grid(row=1, column=1, sticky="w", padx=5, pady=8)
        
        ttk.Label(frame_consorciada, text="Código Empresa:").grid(row=2, column=0, sticky="w", padx=5, pady=8)
        entry_emp = ttk.Entry(frame_consorciada, width=10)
        entry_emp.insert(0, "97")
        entry_emp.grid(row=2, column=1, sticky="w", padx=5, pady=8)
        
        ttk.Label(frame_consorciada, text="Código Obra:").grid(row=3, column=0, sticky="w", padx=5, pady=8)
        entry_obra = ttk.Entry(frame_consorciada, width=10)
        entry_obra.insert(0, "972")
        entry_obra.grid(row=3, column=1, sticky="w", padx=5, pady=8)
        
        # Seção: Contas de Repasse
        frame_repasse = ttk.LabelFrame(scrollable_frame, text="💰 Contas de Repasse", padding=15)
        frame_repasse.pack(fill="x", padx=15, pady=10)
        
        ttk.Label(frame_repasse, text="Conta de Repasse do Ativo:").grid(row=0, column=0, sticky="w", padx=5, pady=8)
        entry_conta_repasse_ativo = ttk.Entry(frame_repasse, width=30)
        entry_conta_repasse_ativo.insert(0, "")
        entry_conta_repasse_ativo.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
        frame_repasse.columnconfigure(1, weight=1)
        
        ttk.Label(frame_repasse, text="Conta de Repasse do Passivo:").grid(row=1, column=0, sticky="w", padx=5, pady=8)
        entry_conta_repasse_passivo = ttk.Entry(frame_repasse, width=30)
        entry_conta_repasse_passivo.insert(0, "")
        entry_conta_repasse_passivo.grid(row=1, column=1, padx=5, pady=8, sticky="ew")
        
        ttk.Label(frame_repasse, text="Grupo a ser Excluído:").grid(row=2, column=0, sticky="w", padx=5, pady=8)
        entry_grupo_excluido = ttk.Entry(frame_repasse, width=30)
        entry_grupo_excluido.insert(0, "")
        entry_grupo_excluido.grid(row=2, column=1, padx=5, pady=8, sticky="ew")
        
        # Seção: Conta de Arredondamento
        frame_arredondo = ttk.LabelFrame(scrollable_frame, text="🔧 Conta de Arredondamento", padding=15)
        frame_arredondo.pack(fill="x", padx=15, pady=10)
        
        ttk.Label(frame_arredondo, text="Conta:").grid(row=0, column=0, sticky="w", padx=5, pady=8)
        entry_conta = ttk.Entry(frame_arredondo, width=30)
        entry_conta.insert(0, "1.1.01.01.000099")
        entry_conta.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
        frame_arredondo.columnconfigure(1, weight=1)
        
        memorizar_var = tk.BooleanVar(value=False)
        check_memorizar = ttk.Checkbutton(frame_arredondo, text="Memorizar esta conta", variable=memorizar_var)
        check_memorizar.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=8)
        
        # Frame de botões
        frame_botoes = ttk.Frame(scrollable_frame)
        frame_botoes.pack(fill="x", padx=15, pady=15)
        
        def save_cadastro():
            try:
                payload = {
                    "nome": entry_nome.get().strip(),
                    "nome_consortio": entry_nome_cons.get().strip(),
                    "codigo_consortio": entry_cons.get().strip(),
                    "codigo_obra_consortio": entry_obra_cons.get().strip(),
                    "percentual": entry_perc.get(),
                    "codigo_empresa": entry_emp.get(),
                    "codigo_obra": entry_obra.get(),
                    "conta_repasse_ativo": entry_conta_repasse_ativo.get().strip(),
                    "conta_repasse_passivo": entry_conta_repasse_passivo.get().strip(),
                    "grupo_excluido": entry_grupo_excluido.get().strip(),
                    "conta_arredondamento": entry_conta.get().strip(),
                    "memorizar_conta": memorizar_var.get(),
                }

                self.service.criar_cadastro(payload)

                self._log(f"✓ Cadastro '{payload['nome']}' ({payload['nome_consortio']}) criado com sucesso")
                self._load_cadastros()
                foi_salvo[0] = True
                dialog.destroy()
            except ValueError as e:
                messagebox.showwarning("Validação", str(e))
            except CadastroErro as e:
                messagebox.showerror("Erro", f"Erro ao salvar: {e}")
        
        ttk.Button(frame_botoes, text="Salvar", command=save_cadastro).pack(side="right", padx=5)
        ttk.Button(frame_botoes, text="Cancelar", command=dialog.destroy).pack(side="right", padx=5)
    
    def _edit_cadastro(self):
        """Edita cadastro selecionado"""
        selecionado = self.cadastro_var.get()
        if not selecionado:
            messagebox.showwarning("Seleção", "Selecione um cadastro para editar")
            return
        
        try:
            cadastro = self.service.obter_cadastro(selecionado)
            if not cadastro:
                return
            
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Editar - {selecionado}")
            dialog.geometry("550x600")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Criar canvas scrollável
            canvas = tk.Canvas(dialog, bg="#132440", highlightthickness=0)
            scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Scroll com mouse
            def _on_mousewheel_edit(event):
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

            canvas.bind("<MouseWheel>", _on_mousewheel_edit)
            
            # Seção: Identificação do Consórcio
            frame_consortio = ttk.LabelFrame(scrollable_frame, text="🏢 Identificação do Consórcio", padding=15)
            frame_consortio.pack(fill="x", padx=15, pady=10)
            
            ttk.Label(frame_consortio, text="Nome do Consórcio:").grid(row=0, column=0, sticky="w", padx=5, pady=8)
            entry_nome_cons = ttk.Entry(frame_consortio, width=40)
            entry_nome_cons.insert(0, str(cadastro.get("nome_consortio", "")))
            entry_nome_cons.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
            frame_consortio.columnconfigure(1, weight=1)
            
            ttk.Label(frame_consortio, text="Código do Consórcio:").grid(row=1, column=0, sticky="w", padx=5, pady=8)
            entry_cons = ttk.Entry(frame_consortio, width=40)
            entry_cons.insert(0, str(cadastro.get("codigo_consortio", "")))
            entry_cons.grid(row=1, column=1, padx=5, pady=8, sticky="ew")
            
            ttk.Label(frame_consortio, text="Código da Obra:").grid(row=2, column=0, sticky="w", padx=5, pady=8)
            entry_obra_cons = ttk.Entry(frame_consortio, width=40)
            entry_obra_cons.insert(0, str(cadastro.get("codigo_obra_consortio", "")))
            entry_obra_cons.grid(row=2, column=1, padx=5, pady=8, sticky="ew")
            
            # Seção: Dados da Consorciada
            frame_consorciada = ttk.LabelFrame(scrollable_frame, text="📊 Dados da Consorciada", padding=15)
            frame_consorciada.pack(fill="x", padx=15, pady=10)
            
            ttk.Label(frame_consorciada, text="Nome da Consorciada:").grid(row=0, column=0, sticky="w", padx=5, pady=8)
            entry_nome = ttk.Entry(frame_consorciada, width=40)
            entry_nome.insert(0, selecionado)
            entry_nome.config(state="readonly")
            entry_nome.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
            frame_consorciada.columnconfigure(1, weight=1)
            
            ttk.Label(frame_consorciada, text="Percentual (%):").grid(row=1, column=0, sticky="w", padx=5, pady=8)
            entry_perc = ttk.Spinbox(frame_consorciada, from_=0, to=100, width=10)
            entry_perc.set(cadastro["percentual"])
            entry_perc.grid(row=1, column=1, sticky="w", padx=5, pady=8)
            
            ttk.Label(frame_consorciada, text="Código Empresa:").grid(row=2, column=0, sticky="w", padx=5, pady=8)
            entry_emp = ttk.Entry(frame_consorciada, width=10)
            entry_emp.insert(0, str(cadastro["codigo_empresa"]))
            entry_emp.grid(row=2, column=1, sticky="w", padx=5, pady=8)
            
            ttk.Label(frame_consorciada, text="Código Obra:").grid(row=3, column=0, sticky="w", padx=5, pady=8)
            entry_obra = ttk.Entry(frame_consorciada, width=10)
            entry_obra.insert(0, str(cadastro["codigo_obra"]))
            entry_obra.grid(row=3, column=1, sticky="w", padx=5, pady=8)
            
            # Seção: Contas de Repasse
            frame_repasse = ttk.LabelFrame(scrollable_frame, text="💰 Contas de Repasse", padding=15)
            frame_repasse.pack(fill="x", padx=15, pady=10)
            
            ttk.Label(frame_repasse, text="Conta de Repasse do Ativo:").grid(row=0, column=0, sticky="w", padx=5, pady=8)
            entry_conta_repasse_ativo = ttk.Entry(frame_repasse, width=30)
            entry_conta_repasse_ativo.insert(0, cadastro.get("conta_repasse_ativo", ""))
            entry_conta_repasse_ativo.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
            frame_repasse.columnconfigure(1, weight=1)
            
            ttk.Label(frame_repasse, text="Conta de Repasse do Passivo:").grid(row=1, column=0, sticky="w", padx=5, pady=8)
            entry_conta_repasse_passivo = ttk.Entry(frame_repasse, width=30)
            entry_conta_repasse_passivo.insert(0, cadastro.get("conta_repasse_passivo", ""))
            entry_conta_repasse_passivo.grid(row=1, column=1, padx=5, pady=8, sticky="ew")
            
            ttk.Label(frame_repasse, text="Grupo a ser Excluído:").grid(row=2, column=0, sticky="w", padx=5, pady=8)
            entry_grupo_excluido = ttk.Entry(frame_repasse, width=30)
            entry_grupo_excluido.insert(0, cadastro.get("grupo_excluido", ""))
            entry_grupo_excluido.grid(row=2, column=1, padx=5, pady=8, sticky="ew")
            
            # Seção: Conta de Arredondamento
            frame_arredondo = ttk.LabelFrame(scrollable_frame, text="🔧 Conta de Arredondamento", padding=15)
            frame_arredondo.pack(fill="x", padx=15, pady=10)
            
            ttk.Label(frame_arredondo, text="Conta:").grid(row=0, column=0, sticky="w", padx=5, pady=8)
            entry_conta = ttk.Entry(frame_arredondo, width=30)
            entry_conta.insert(0, cadastro.get("conta_arredondamento", "1.1.01.01.000099"))
            entry_conta.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
            frame_arredondo.columnconfigure(1, weight=1)
            
            memorizar_var = tk.BooleanVar(value=cadastro.get("memorizar_conta", False))
            check_memorizar = ttk.Checkbutton(frame_arredondo, text="Memorizar esta conta", variable=memorizar_var)
            check_memorizar.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=8)
            
            # Frame de botões
            frame_botoes = ttk.Frame(scrollable_frame)
            frame_botoes.pack(fill="x", padx=15, pady=15)
            
            def save_changes():
                try:
                    updates = {
                        "nome_consortio": entry_nome_cons.get().strip(),
                        "codigo_consortio": entry_cons.get().strip(),
                        "codigo_obra_consortio": entry_obra_cons.get().strip(),
                        "percentual": entry_perc.get(),
                        "codigo_empresa": entry_emp.get(),
                        "codigo_obra": entry_obra.get(),
                        "conta_repasse_ativo": entry_conta_repasse_ativo.get().strip(),
                        "conta_repasse_passivo": entry_conta_repasse_passivo.get().strip(),
                        "grupo_excluido": entry_grupo_excluido.get().strip(),
                        "conta_arredondamento": entry_conta.get().strip(),
                        "memorizar_conta": memorizar_var.get(),
                    }

                    self.service.atualizar_cadastro(selecionado, updates)
                    
                    self._log(f"✓ Cadastro '{selecionado}' atualizado")
                    self._load_cadastros()
                    dialog.destroy()
                except ValueError as e:
                    messagebox.showwarning("Validação", str(e))
                except CadastroErro as e:
                    messagebox.showerror("Erro", f"Erro ao salvar: {e}")
            
            ttk.Button(frame_botoes, text="Salvar", command=save_changes).pack(side="right", padx=5)
            ttk.Button(frame_botoes, text="Cancelar", command=dialog.destroy).pack(side="right", padx=5)
        except CadastroErro as e:
            messagebox.showerror("Erro", f"Erro ao editar: {e}")
    
    def _delete_cadastro(self):
        """Deleta cadastro selecionado"""
        selecionado = self.cadastro_var.get()
        if not selecionado:
            messagebox.showwarning("Seleção", "Selecione um cadastro para deletar")
            return
        
        if messagebox.askyesno("Confirmação", f"Deletar cadastro '{selecionado}'?"):
            try:
                removido = self.service.deletar_cadastro(selecionado)
                if not removido:
                    messagebox.showwarning("Seleção", f"Cadastro '{selecionado}' não encontrado")
                    return
                
                self._log(f"✓ Cadastro '{selecionado}' deletado")
                self._load_cadastros()
                self.cadastro_var.set("")
            except CadastroErro as e:
                messagebox.showerror("Erro", f"Erro ao deletar: {e}")
    
    def _converter(self):
        """Executa conversão em thread"""
        arquivo = self.archivo_var.get().strip()
        if not arquivo or not Path(arquivo).exists():
            messagebox.showerror("Erro", "Selecione um arquivo válido")
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
            messagebox.showerror("Erro", str(e))
            return
        
        # Executar em thread para não congelar GUI
        thread = threading.Thread(target=self._run_conversion, 
                                 args=(arquivo, percentual, empresa, obra, conta_arred,
                                       self.conta_repasse_ativo_var.get().strip(),
                                       self.conta_repasse_passivo_var.get().strip(),
                                       self.grupo_excluido_var.get().strip(),
                                       self.cadastro_var.get().strip()))
        thread.daemon = True
        thread.start()
    
    def _run_conversion(self, arquivo, percentual, empresa, obra, conta_arred, repasse_ativo, repasse_passivo, grupo_excluido, nome_consorciada=""):
        """Executa a conversão"""
        try:
            self.status_var.set("⏳ Processando...")
            self.log_text.config(state="normal")
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
            saida_dir = self.base_dir / "saida"
            saida_dir.mkdir(parents=True, exist_ok=True)
            
            # Incluir nome da consorciada no arquivo de saída
            if nome_consorciada:
                nome_saida = f"{Path(arquivo).stem} - {nome_consorciada} - Convertido.xlsx"
            else:
                nome_saida = f"{Path(arquivo).stem} - Convertido.xlsx"
            arquivo_saida = saida_dir / nome_saida
            resultado.to_excel(arquivo_saida, index=False)
            
            self._log(f"\n✓ Arquivo salvo com sucesso!")
            self._log(f"Saída: {arquivo_saida}")
            self._log(f"Lançamentos processados: {len(resultado)}")
            self._log("=" * 70)
            
            # Atualizar cadastro se checkbox memorizar estiver marcado
            self._salvar_conta_memorizada_se_necessario(conta_arred)
            
            self.status_var.set(f"✓ Conversão concluída - {len(resultado)} lançamentos")
            
            # Mostrar mensagem apropriada
            if tem_aviso_grupo:
                messagebox.showwarning(
                    "Conversão Concluída com Aviso", 
                    f"Conversão realizada com sucesso!\n" \
                    f"{len(resultado)} lançamentos processados\n\n" \
                    f"⚠️ AVISO: Grupo para exclusão não foi encontrado no arquivo.\n" \
                    f"O filtro de exclusão não foi aplicado."
                )
            else:
                messagebox.showinfo("Sucesso", f"Conversão realizada!\n{len(resultado)} lançamentos processados")
            
        except PermissionError as e:
            self._log(f"\n✗ ERRO DE PERMISSÃO: {e}")
            self.status_var.set(f"✗ Arquivo bloqueado")
            messagebox.showerror("Erro de Permissão", str(e))
        except FileNotFoundError as e:
            self._log(f"\n✗ ARQUIVO NÃO ENCONTRADO: {e}")
            self.status_var.set(f"✗ Arquivo não encontrado")
            messagebox.showerror("Arquivo Não Encontrado", str(e))
        except ConversaoErro as e:
            self._log(f"\n✗ ERRO: {e}")
            self.status_var.set(f"✗ Erro na conversão")
            messagebox.showerror("Erro", f"Erro na conversão:\n{e}")
            log_event(self.logger, 40, "ui_conversao_falhou", etapa="ui", arquivo=arquivo)
    
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
        conta_arred = self.conta_arred_var.get().strip()
        try:
            percentual, empresa, obra, conta_arred = self.service.parse_config(
                self.percentual_var.get(),
                self.empresa_var.get(),
                self.obra_var.get(),
                conta_arred,
            )
        except ConfiguracaoErro as e:
            messagebox.showerror("Erro", str(e))
            return
        
        thread = threading.Thread(target=self._run_batch_conversion, 
                                 args=(percentual, empresa, obra, conta_arred, self.cadastro_var.get().strip()))
        thread.daemon = True
        thread.start()
    
    def _run_batch_conversion(self, percentual, empresa, obra, conta_arred, nome_consorciada=""):
        """Processa lote de arquivos"""
        try:
            self.status_var.set("⏳ Processando pasta...")
            self.log_text.config(state="normal")
            self.log_text.delete("1.0", "end")
            
            self._log("=" * 70)
            self._log(f"PROCESSAMENTO EM LOTE")
            self._log("=" * 70)
            if nome_consorciada:
                self._log(f"Consorciada: {nome_consorciada}")
            self._log(f"Percentual: {percentual*100:.1f}%")
            self._log(f"Empresa: {empresa}, Obra: {obra}")
            self._log(f"Conta Arredondamento: {conta_arred}\n")
            
            self.service.executar_lote(percentual, empresa, obra, conta_arred, nome_consorciada)
            
            self._log("\n✓ Processamento em lote concluído!")
            self.status_var.set("✓ Processamento em lote concluído")
            messagebox.showinfo("Sucesso", "Todos os arquivos foram processados!")
            
        except PermissionError as e:
            self._log(f"\n✗ ERRO DE PERMISSÃO: {e}")
            self.status_var.set("✗ Arquivo bloqueado")
            messagebox.showerror("Erro de Permissão", str(e))
        except FileNotFoundError as e:
            self._log(f"\n✗ ARQUIVO NÃO ENCONTRADO: {e}")
            self.status_var.set("✗ Arquivo não encontrado")
            messagebox.showerror("Arquivo Não Encontrado", str(e))
        except ConversaoErro as e:
            self._log(f"\n✗ ERRO: {e}")
            self.status_var.set("✗ Erro no processamento")
            messagebox.showerror("Erro", f"Erro:\n{e}")
            log_event(self.logger, 40, "ui_lote_falhou", etapa="ui")
    
    def _open_output_dir(self):
        """Abre pasta de saída"""
        saida_dir = self.base_dir / "saida"
        saida_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(saida_dir))
        self._log(f"📂 Abrindo pasta: {saida_dir}")
    
    def _clear_log(self):
        """Limpa o log"""
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.status_var.set("Pronto")
    
    def _criar_cadastros_padrao(self):
        """Cria arquivo de cadastros padrão"""
        try:
            self.repository.write_data(self.repository.default_data())
            self._log(f"✓ Arquivo cadastros.json criado com exemplos padrão")
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
    root = tk.Tk()
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
    
    app = TelaConversor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
