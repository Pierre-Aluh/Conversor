from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Callable

from Conversor import gerar_contabilidade_consorciada, processar_pasta_entrada
from erros import CadastroErro, CadastroNaoEncontradoErro, ConfiguracaoErro, ConversaoErro, PersistenciaErro
from observabilidade import get_logger, log_event

from .persistencia import CadastrosRepository


class ConversorAppService:
    def __init__(
        self,
        repository: CadastrosRepository,
        conversao_fn: Callable[..., Any] = gerar_contabilidade_consorciada,
        lote_fn: Callable[..., Any] = processar_pasta_entrada,
    ):
        self.repository = repository
        self.conversao_fn = conversao_fn
        self.lote_fn = lote_fn
        self.logger = get_logger(__name__)

    def carregar_nomes_cadastros(self) -> list[str]:
        try:
            return self.repository.list_names()
        except PersistenciaErro as exc:
            log_event(self.logger, 40, "cadastro_lista_falhou", etapa="cadastro")
            raise CadastroErro("Falha ao carregar cadastros") from exc

    def obter_cadastro(self, nome: str) -> dict[str, Any] | None:
        try:
            return self.repository.find_by_name(nome)
        except PersistenciaErro as exc:
            log_event(self.logger, 40, "cadastro_busca_falhou", etapa="cadastro", cadastro=nome)
            raise CadastroErro("Falha ao buscar cadastro") from exc

    def criar_cadastro(self, payload: dict[str, str | bool]) -> None:
        nome_cons = str(payload.get("nome_consortio", "")).strip()
        if not nome_cons:
            raise ValueError("Nome do consórcio não pode estar vazio")

        cod_cons = str(payload.get("codigo_consortio", "")).strip()
        if not cod_cons:
            raise ValueError("Código do consórcio não pode estar vazio")

        cod_obra_cons = str(payload.get("codigo_obra_consortio", "")).strip()
        if not cod_obra_cons:
            raise ValueError("Código da obra do consórcio não pode estar vazio")

        nome = str(payload.get("nome", "")).strip()
        if not nome:
            raise ValueError("Nome da consorciada não pode estar vazio")

        conta = str(payload.get("conta_arredondamento", "")).strip()
        if not conta:
            raise ValueError("Conta de arredondamento não pode estar vazia")

        cadastro = {
            "nome": nome,
            "nome_consortio": nome_cons,
            "codigo_consortio": cod_cons,
            "codigo_obra_consortio": cod_obra_cons,
            "percentual": float(str(payload.get("percentual", "0"))),
            "codigo_empresa": int(str(payload.get("codigo_empresa", "0"))),
            "codigo_obra": int(str(payload.get("codigo_obra", "0"))),
            "conta_repasse_ativo": str(payload.get("conta_repasse_ativo", "")).strip(),
            "conta_repasse_passivo": str(payload.get("conta_repasse_passivo", "")).strip(),
            "grupo_excluido": str(payload.get("grupo_excluido", "")).strip(),
            "conta_arredondamento": conta,
            "memorizar_conta": bool(payload.get("memorizar_conta", False)),
        }
        try:
            self.repository.add_cadastro(cadastro)
            log_event(self.logger, 20, "cadastro_criado", etapa="cadastro", cadastro=nome)
        except PersistenciaErro as exc:
            log_event(self.logger, 40, "cadastro_falha_persistencia", etapa="cadastro", cadastro=nome)
            raise CadastroErro("Falha ao salvar cadastro") from exc
        except ValueError as exc:
            log_event(self.logger, 30, "cadastro_duplicado", etapa="cadastro", cadastro=nome)
            raise CadastroErro(str(exc)) from exc

    def atualizar_cadastro(self, nome: str, updates: dict[str, str | bool]) -> None:
        payload = {
            "nome_consortio": str(updates.get("nome_consortio", "")).strip(),
            "codigo_consortio": str(updates.get("codigo_consortio", "")).strip(),
            "codigo_obra_consortio": str(updates.get("codigo_obra_consortio", "")).strip(),
            "percentual": float(str(updates.get("percentual", "0"))),
            "codigo_empresa": int(str(updates.get("codigo_empresa", "0"))),
            "codigo_obra": int(str(updates.get("codigo_obra", "0"))),
            "conta_repasse_ativo": str(updates.get("conta_repasse_ativo", "")).strip(),
            "conta_repasse_passivo": str(updates.get("conta_repasse_passivo", "")).strip(),
            "grupo_excluido": str(updates.get("grupo_excluido", "")).strip(),
            "conta_arredondamento": str(updates.get("conta_arredondamento", "")).strip(),
            "memorizar_conta": bool(updates.get("memorizar_conta", False)),
        }
        if not payload["conta_arredondamento"]:
            raise ValueError("Conta de arredondamento não pode estar vazia")
        try:
            self.repository.update_cadastro(nome, payload)
            log_event(self.logger, 20, "cadastro_atualizado", etapa="cadastro", cadastro=nome)
        except CadastroNaoEncontradoErro as exc:
            log_event(self.logger, 30, "cadastro_nao_encontrado", etapa="cadastro", cadastro=nome)
            raise CadastroErro(str(exc)) from exc
        except PersistenciaErro as exc:
            log_event(self.logger, 40, "cadastro_falha_persistencia", etapa="cadastro", cadastro=nome)
            raise CadastroErro("Falha ao atualizar cadastro") from exc

    def deletar_cadastro(self, nome: str) -> bool:
        try:
            removido = self.repository.delete_cadastro(nome)
            log_event(self.logger, 20, "cadastro_deletado", etapa="cadastro", cadastro=nome, removido=removido)
            return removido
        except PersistenciaErro as exc:
            log_event(self.logger, 40, "cadastro_falha_persistencia", etapa="cadastro", cadastro=nome)
            raise CadastroErro("Falha ao deletar cadastro") from exc

    def memorizar_conta(self, nome: str, conta_arredondamento: str, ativo: bool) -> bool:
        if not ativo or not nome:
            return False
        try:
            self.repository.update_cadastro(
                nome,
                {
                    "conta_arredondamento": conta_arredondamento,
                    "memorizar_conta": True,
                },
            )
            log_event(self.logger, 20, "conta_memorizada", etapa="cadastro", cadastro=nome)
            return True
        except (CadastroNaoEncontradoErro, PersistenciaErro) as exc:
            log_event(self.logger, 30, "conta_memorizacao_falhou", etapa="cadastro", cadastro=nome)
            raise CadastroErro("Não foi possível memorizar a conta no cadastro") from exc

    def parse_config(self, percentual_texto: str, empresa_texto: str, obra_texto: str, conta_arred: str) -> tuple[float, int, int, str]:
        conta = conta_arred.strip()
        if not conta:
            raise ConfiguracaoErro("Informe a conta de arredondamento")

        try:
            percentual = float(percentual_texto.strip()) / 100
        except ValueError as exc:
            raise ConfiguracaoErro(f"Percentual inválido: '{percentual_texto}' (usar apenas números, ex: 52.5)") from exc

        try:
            empresa = int(empresa_texto.strip())
        except ValueError as exc:
            raise ConfiguracaoErro(f"Código Empresa inválido: '{empresa_texto}' (usar apenas números inteiros)") from exc

        try:
            obra = int(obra_texto.strip())
        except ValueError as exc:
            raise ConfiguracaoErro(f"Código Obra inválido: '{obra_texto}' (usar apenas números inteiros)") from exc

        return percentual, empresa, obra, conta

    def executar_conversao(
        self,
        arquivo: str,
        percentual: float,
        empresa: int,
        obra: int,
        conta_arred: str,
        repasse_ativo: str,
        repasse_passivo: str,
        grupo_excluido: str,
    ) -> dict[str, Any]:
        arquivo_path = Path(arquivo)
        if not arquivo_path.exists():
            raise FileNotFoundError("Selecione um arquivo válido")

        console_output = io.StringIO()
        try:
            with redirect_stdout(console_output):
                resultado = self.conversao_fn(
                    arquivo,
                    percentual,
                    empresa,
                    obra,
                    conta_arred,
                    repasse_ativo,
                    repasse_passivo,
                    grupo_excluido,
                )
        except (ValueError, RuntimeError) as exc:
            log_event(self.logger, 40, "conversao_falha_negocio", etapa="conversao", arquivo=arquivo)
            raise ConversaoErro(str(exc)) from exc
        except (PermissionError, FileNotFoundError, OSError) as exc:
            log_event(self.logger, 40, "conversao_falha_io", etapa="conversao", arquivo=arquivo)
            raise

        captured_text = console_output.getvalue()
        log_event(self.logger, 20, "conversao_ok", etapa="conversao", arquivo=arquivo, aviso_grupo="Grupo para exclusão não encontrado" in captured_text)
        return {
            "resultado": resultado,
            "log_capturado": captured_text,
            "tem_aviso_grupo": "Grupo para exclusão não encontrado" in captured_text,
        }

    def executar_lote(self, percentual: float, empresa: int, obra: int, conta_arred: str, nome_consorciada: str = "") -> None:
        try:
            self.lote_fn(percentual, empresa, obra, conta_arred, nome_consorciada)
            log_event(self.logger, 20, "lote_ok", etapa="lote", cadastro=nome_consorciada or None)
        except (ValueError, RuntimeError) as exc:
            log_event(self.logger, 40, "lote_falha_negocio", etapa="lote", cadastro=nome_consorciada or None)
            raise ConversaoErro(str(exc)) from exc
