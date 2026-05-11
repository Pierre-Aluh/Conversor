import pandas as pd
from pathlib import Path

from config import CONTAS_PRIORITARIAS
from conversor._entrada import validar_parametros, carregar_e_normalizar
from conversor._exclusao import aplicar_exclusao_grupo
from conversor._ajuste import aplicar_passos_1_a_3
from conversor._saida import validar_e_formatar
from observabilidade import get_logger, log_event


logger = get_logger(__name__)


def gerar_contabilidade_consorciada(arquivo_origem, percentual, cod_empresa, cod_obra, conta_arredondamento=None,
                                    repasse_ativo=None, repasse_passivo=None, grupo_excluido=None):
    """
    Transforma lançamentos do Consórcio para a Empresa Consorciada.

    CONTAS PRIORITÁRIAS (SAGRADAS): Devem fechar 100% em todos os níveis.
    conta_arredondamento: Conta usada para lançamentos de ajuste de arredondamento.
    """
    validar_parametros(arquivo_origem, percentual, cod_empresa, cod_obra, conta_arredondamento)
    df_original, new_df = carregar_e_normalizar(arquivo_origem, cod_empresa, cod_obra)
    new_df = aplicar_exclusao_grupo(new_df, repasse_ativo, repasse_passivo, grupo_excluido)
    new_df = aplicar_passos_1_a_3(new_df, percentual, CONTAS_PRIORITARIAS)
    new_df = validar_e_formatar(new_df, df_original, percentual, CONTAS_PRIORITARIAS)
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


def processar_pasta_entrada(percentual, cod_empresa, cod_obra, conta_arredondamento=None, nome_consorciada=""):
    base_dir = Path(__file__).resolve().parent
    pasta_entrada = base_dir / 'entrada'
    pasta_saida = base_dir / 'saida'

    pasta_entrada.mkdir(parents=True, exist_ok=True)
    pasta_saida.mkdir(parents=True, exist_ok=True)

    arquivos = [p for p in pasta_entrada.iterdir() if p.is_file()]

    if not arquivos:
        print(f"Nenhum arquivo encontrado em {pasta_entrada}")
        log_event(logger, 30, "lote_sem_arquivos", etapa="lote")
        return

    for arquivo in arquivos:
        try:
            resultado = gerar_contabilidade_consorciada(
                arquivo, percentual, cod_empresa, cod_obra, conta_arredondamento
            )
            if nome_consorciada:
                saida = pasta_saida / f"{arquivo.stem} - {nome_consorciada} - Arquivo de Saída para Importação no UAU.xlsx"
            else:
                saida = pasta_saida / f"{arquivo.stem} - Arquivo de Saída para Importação no UAU.xlsx"
            resultado.to_excel(saida, index=False)
            print(f"Arquivo gerado: {saida}")
            log_event(logger, 20, "lote_arquivo_processado", etapa="lote", arquivo=arquivo)
        except (PermissionError, FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
            log_event(logger, 40, "lote_arquivo_falhou", etapa="lote", arquivo=arquivo)
            print(f"Falha ao processar {arquivo.name}: {exc}")


# --- EXEMPLO DE USO ---
# percentual_participacao = 0.50  (para 50%)
# processar_pasta_entrada(0.5, 97, 972)

if __name__ == "__main__":
    percentual_participacao = 0.50  # 50% de participação
    codigo_empresa = 97
    codigo_obra = 972
    processar_pasta_entrada(percentual_participacao, codigo_empresa, codigo_obra)
