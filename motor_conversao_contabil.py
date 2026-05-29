import pandas as pd
from pathlib import Path
from typing import Callable

from config import CONTAS_PRIORITARIAS
from conversor._entrada import validar_parametros, carregar_e_normalizar
from conversor._exclusao import aplicar_exclusao_grupo
from conversor._ajuste import aplicar_passos_1_a_3
from conversor._saida import validar_e_formatar
from observabilidade import get_logger, log_event


logger = get_logger(__name__)


def _emit_progress(progress_callback: Callable[[float, str], None] | None, value: float, message: str) -> None:
    if not progress_callback:
        return
    progress_callback(max(0.0, min(1.0, value)), message)


def gerar_contabilidade_consorciada(
    arquivo_origem,
    percentual,
    cod_empresa,
    cod_obra,
    conta_arredondamento=None,
    repasse_ativo=None,
    repasse_passivo=None,
    grupo_excluido=None,
    sheet_name: str = "",
    account_substitutions: list[dict[str, str]] | None = None,
    input_layouts: list[dict[str, list[str]]] | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
):
    """
    Transforma lançamentos do Consórcio para a Empresa Consorciada.

    CONTAS PRIORITÁRIAS (SAGRADAS): Devem fechar 100% em todos os níveis.
    conta_arredondamento: Conta usada para lançamentos de ajuste de arredondamento.
    """
    _emit_progress(progress_callback, 0.03, "Validando parâmetros")
    validar_parametros(arquivo_origem, percentual, cod_empresa, cod_obra, conta_arredondamento)

    _emit_progress(progress_callback, 0.08, "Carregando e normalizando dados")
    df_original, new_df = carregar_e_normalizar(
        arquivo_origem,
        cod_empresa,
        cod_obra,
        sheet_name=sheet_name,
        input_layouts=input_layouts,
    )

    _emit_progress(progress_callback, 0.12, "Aplicando exclusão de grupo")
    new_df = aplicar_exclusao_grupo(new_df, repasse_ativo, repasse_passivo, grupo_excluido)

    _emit_progress(progress_callback, 0.14, "Iniciando conversão por linhas")

    def progresso_linhas(valor: float, mensagem: str) -> None:
        # Faixa principal dedicada ao progresso por linha convertida.
        _emit_progress(progress_callback, 0.14 + (0.72 * valor), mensagem)

    new_df = aplicar_passos_1_a_3(
        new_df,
        percentual,
        CONTAS_PRIORITARIAS,
        progress_callback=progresso_linhas,
    )

    _emit_progress(progress_callback, 0.90, "Validando fechamento e formatando")
    new_df = validar_e_formatar(
        new_df,
        df_original,
        percentual,
        CONTAS_PRIORITARIAS,
        account_substitutions=account_substitutions,
    )

    _emit_progress(progress_callback, 0.97, "Conversão calculada")
    return new_df


# --- PROCESSAMENTO EM LOTE ---
# Coloque os arquivos de entrada em: ./entrada
# Os arquivos .xlsx serão gerados em: ./saida

def gerar_para_multiplas_consorciadas(arquivo_origem, lista_consorciadas):
    """
    Gera lançamentos para múltiplas consorciadas em um único arquivo.

    Args:
        arquivo_origem: Path do arquivo do consórcio
        lista_consorciadas: Lista de dicts com 'cod_empresa', 'cod_obra', 'percentual'

    Returns:
        DataFrame com todos os lançamentos concatenados
    """
    resultados = []
    for consorciada in lista_consorciadas:
        df_consorciada = gerar_contabilidade_consorciada(
            arquivo_origem,
            consorciada['percentual'],
            consorciada['cod_empresa'],
            consorciada['cod_obra']
        )
        resultados.append(df_consorciada)
    return pd.concat(resultados, ignore_index=True)


def processar_pasta_entrada(
    percentual,
    cod_empresa,
    cod_obra,
    conta_arredondamento=None,
    nome_consorciada="",
    account_substitutions: list[dict[str, str]] | None = None,
    input_layouts: list[dict[str, list[str]]] | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
):
    base_dir = Path(__file__).resolve().parent
    pasta_entrada = base_dir / 'entrada'
    pasta_saida = base_dir / 'saida'

    pasta_entrada.mkdir(parents=True, exist_ok=True)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    arquivos = [p for p in pasta_entrada.iterdir() if p.is_file()]
    _emit_progress(progress_callback, 0.05, "Mapeando arquivos da pasta de entrada")

    if not arquivos:
        print(f"Nenhum arquivo encontrado em {pasta_entrada}")
        log_event(logger, 30, "lote_sem_arquivos", etapa="lote")
        _emit_progress(progress_callback, 1.0, "Nenhum arquivo encontrado")
        return

    total_arquivos = len(arquivos)
    for idx, arquivo in enumerate(arquivos, start=1):
        base = (idx - 1) / total_arquivos
        faixa = 1 / total_arquivos

        def progresso_arquivo(valor: float, mensagem: str) -> None:
            percentual_global = base + (max(0.0, min(1.0, valor)) * faixa)
            _emit_progress(progress_callback, percentual_global, f"[{idx}/{total_arquivos}] {mensagem}")

        try:
            resultado = gerar_contabilidade_consorciada(
                arquivo,
                percentual,
                cod_empresa,
                cod_obra,
                conta_arredondamento,
                account_substitutions=account_substitutions,
                input_layouts=input_layouts,
                progress_callback=progresso_arquivo,
            )
            progresso_arquivo(0.95, "Salvando arquivo de saída")
            if nome_consorciada:
                saida = pasta_saida / f"{arquivo.stem} - {nome_consorciada} - Arquivo de Saída para Importação no UAU.xlsx"
            else:
                saida = pasta_saida / f"{arquivo.stem} - Arquivo de Saída para Importação no UAU.xlsx"
            resultado.to_excel(saida, index=False)
            print(f"Arquivo gerado: {saida}")
            log_event(logger, 20, "lote_arquivo_processado", etapa="lote", arquivo=arquivo)
            progresso_arquivo(1.0, f"Concluído: {arquivo.name}")
        except (PermissionError, FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
            log_event(logger, 40, "lote_arquivo_falhou", etapa="lote", arquivo=arquivo)
            print(f"Falha ao processar {arquivo.name}: {exc}")

    _emit_progress(progress_callback, 1.0, "Processamento em lote concluído")


# --- EXEMPLO DE USO ---
# percentual_participacao = 0.50  (para 50%)
# processar_pasta_entrada(0.5, 97, 972)

if __name__ == "__main__":
    percentual_participacao = 0.50  # 50% de participação
    codigo_empresa = 97
    codigo_obra = 972
    processar_pasta_entrada(percentual_participacao, codigo_empresa, codigo_obra)
