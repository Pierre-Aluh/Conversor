# -*- coding: utf-8 -*-
"""Validacao de parametros, carga e normalizacao do arquivo de entrada."""

import shutil
import tempfile
import time

import pandas as pd
from pathlib import Path

from observabilidade import get_logger, log_event


logger = get_logger(__name__)


def validar_parametros(arquivo_origem, percentual, cod_empresa, cod_obra, conta_arredondamento):
    if conta_arredondamento is None or not str(conta_arredondamento).strip():
        raise ValueError("❌ ERRO: Conta de arredondamento é obrigatória")

    if not isinstance(percentual, (int, float)) or percentual <= 0 or percentual > 1:
        raise ValueError(f"❌ ERRO: Percentual inválido: {percentual} (deve estar entre 0 e 1)")

    if not isinstance(cod_empresa, int) or cod_empresa <= 0:
        raise ValueError(f"❌ ERRO: Código de empresa inválido: {cod_empresa}")

    if not isinstance(cod_obra, int) or cod_obra <= 0:
        raise ValueError(f"❌ ERRO: Código de obra inválido: {cod_obra}")


def carregar_e_normalizar(arquivo_origem, cod_empresa, cod_obra):
    """
    Carrega o arquivo de origem, normaliza colunas e retorna
    (df_original_com_acao_limpa, new_df).

    df_original_com_acao_limpa e usado na validacao final (passo 4).
    new_df e o DataFrame de trabalho para os passos seguintes.
    """
    arquivo_origem = Path(arquivo_origem)
    try:
        if arquivo_origem.suffix.lower() in {'.xls', '.xlsx'}:
            df = None
            ultimo_erro = None
            for _ in range(3):
                try:
                    df = pd.read_excel(arquivo_origem)
                    break
                except PermissionError as e:
                    ultimo_erro = e
                    time.sleep(0.8)

            if df is None:
                try:
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        tmp_file = Path(tmp_dir) / arquivo_origem.name
                        shutil.copy2(arquivo_origem, tmp_file)
                        df = pd.read_excel(tmp_file)
                except PermissionError as e:
                    raise PermissionError(
                        f"❌ ARQUIVO BLOQUEADO - Não consegui acessar: {arquivo_origem}\n"
                        f"\nSoluções:\n"
                        f"1. Feche o arquivo se estiver aberto no Excel\n"
                        f"2. Aguarde a sincronização do OneDrive completar\n"
                        f"3. Verifique permissões da pasta\n"
                        f"\nTente novamente em alguns segundos."
                    ) from e
                except (OSError, ValueError, pd.errors.ParserError) as e:
                    if ultimo_erro is not None:
                        raise PermissionError(
                            f"❌ ARQUIVO BLOQUEADO - Não consegui acessar: {arquivo_origem}\n"
                            f"\nSoluções:\n"
                            f"1. Feche o arquivo se estiver aberto no Excel\n"
                            f"2. Aguarde a sincronização do OneDrive completar\n"
                            f"3. Verifique permissões da pasta\n"
                            f"\nDetalhe técnico: {e}"
                        ) from ultimo_erro
                    log_event(logger, 40, "entrada_falha_fallback", etapa="entrada", arquivo=arquivo_origem)
                    raise OSError("Falha ao copiar arquivo para leitura temporária") from e
        else:
            df = pd.read_csv(arquivo_origem, sep=None, engine='python', encoding='utf-8-sig')
    except FileNotFoundError:
        log_event(logger, 40, "entrada_arquivo_nao_encontrado", etapa="entrada", arquivo=arquivo_origem)
        raise FileNotFoundError(f"❌ ARQUIVO NÃO ENCONTRADO: {arquivo_origem}")
    except (PermissionError, OSError, ValueError, pd.errors.ParserError):
        raise
    except (TypeError, UnicodeError) as e:
        log_event(logger, 40, "entrada_falha_carregamento", etapa="entrada", arquivo=arquivo_origem)
        raise RuntimeError(f"❌ ERRO ao carregar arquivo: {str(e)}") from e

    colunas_obrigatorias = ['Valor', 'Conta', 'Ação']
    colunas_faltantes = [col for col in colunas_obrigatorias if col not in df.columns]
    if colunas_faltantes:
        raise ValueError(
            f"❌ ERRO: Colunas obrigatórias não encontradas no arquivo: {', '.join(colunas_faltantes)}"
        )

    mapping = {
        'Documento': 'DOC',
        'Cheque': 'NUMCHEQUE',
        'Categ. mov. fin.': 'CategoriaMovimentacaoFinanceira',
        'Data': 'Data',
        'Conta': 'CONTA',
        'Ação': 'ACAO',
        'Histórico lançamento contábil': 'HISTORICO',
        'Sequência': 'NumSequencia',
        'Contra part.': 'ContaContraPartida',
    }

    new_df = pd.DataFrame()

    col_tipo = next((c for c in df.columns if 'tipo' in c.lower() and 'lan' in c.lower()), None)
    tipo_arquivo = 'FISCAL'
    if col_tipo:
        eh_societario = df[col_tipo].astype(str).str.contains(
            '19|42|ajuste societario', case=False, na=False
        ).any()
        if eh_societario:
            tipo_arquivo = 'SOCIETARIO'

    print(f"\n[✓] Tipo de arquivo detectado: {tipo_arquivo}")
    log_event(logger, 20, "entrada_tipo_detectado", etapa="entrada", arquivo=arquivo_origem, tipo=tipo_arquivo)

    new_df['Lancamento'] = [tipo_arquivo] * len(df)
    new_df['VALOR_ORIGINAL'] = df['Valor'].values

    for old_col, new_col in mapping.items():
        if old_col in df.columns:
            new_df[new_col] = df[old_col]

    if 'Data' not in new_df.columns:
        new_df['Data'] = ''

    new_df['Empresa'] = cod_empresa
    new_df['Obra'] = cod_obra
    new_df['TipoLancamento'] = 0

    if 'NUMCHEQUE' in new_df.columns:
        new_df['NUMCHEQUE'] = new_df['NUMCHEQUE'].fillna(0)
    else:
        new_df['NUMCHEQUE'] = 0

    if 'DOC' in new_df.columns:
        new_df['DOC'] = new_df['DOC'].fillna(0)
    else:
        new_df['DOC'] = ''

    new_df['ACAO_LIMPA'] = new_df['ACAO'].str.strip()
    new_df['CONTA'] = new_df['CONTA'].str.strip()

    if 'HISTORICO' in new_df.columns:
        new_df['HISTORICO'] = new_df['HISTORICO'].fillna('').str.strip()
    else:
        new_df['HISTORICO'] = ''

    if 'NumSequencia' in new_df.columns:
        new_df['NumSequencia'] = pd.to_numeric(new_df['NumSequencia'], errors='coerce').fillna(0)
    else:
        new_df['NumSequencia'] = 0

    if 'ContaContraPartida' in new_df.columns:
        new_df['ContaContraPartida'] = new_df['ContaContraPartida'].fillna('').astype(str).str.strip()
    else:
        new_df['ContaContraPartida'] = ''

    if 'CategoriaMovimentacaoFinanceira' in new_df.columns:
        new_df['CategoriaMovimentacaoFinanceira'] = (
            new_df['CategoriaMovimentacaoFinanceira'].fillna('').astype(str).str.strip()
        )
    else:
        new_df['CategoriaMovimentacaoFinanceira'] = ''

    # Prepara df_original com ACAO_LIMPA para uso na validacao final (passo 4)
    df = df.copy()
    df['ACAO_LIMPA'] = df['Ação'].str.strip()
    df['Conta'] = df['Conta'].str.strip()

    # Marcador de linhas preservadas em 100% (preenchido pelo passo de exclusao)
    new_df['_preservar_100'] = False

    return df, new_df
