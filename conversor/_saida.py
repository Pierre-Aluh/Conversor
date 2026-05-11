# -*- coding: utf-8 -*-
"""Passos 4 e 4.5: validacao final, piso de 0,01, formatacao e reordenacao para o layout UAU."""

import pandas as pd
from decimal import Decimal, ROUND_HALF_UP

from config import TOLERANCIA_CONTAS_PRIORITARIAS, TOLERANCIA_GLOBAL
from observabilidade import get_logger, log_event


logger = get_logger(__name__)


def validar_e_formatar(new_df, df_original, percentual, contas_prioritarias):
    """
    Executa a validacao final (passo 4), aplica o piso de 0,01 (passo 4.5),
    formata as colunas e reordena para o layout UAU.

    Parametros:
        new_df             - DataFrame de trabalho (com ACAO_LIMPA e VALOR_CENTS)
        df_original        - DataFrame do arquivo de origem (com ACAO_LIMPA e Conta)
        percentual         - percentual de participacao (0 < p <= 1)
        contas_prioritarias - conjunto de contas sagradas

    Retorna new_df pronto para exportacao.
    """
    # --- PASSO 4: Validacao final ---
    print("\n[PASSO 4] Validação final...")

    total_d_cents = new_df[new_df['ACAO_LIMPA'] == 'D - Débito']['VALOR_CENTS'].sum()
    total_c_cents = new_df[new_df['ACAO_LIMPA'] == 'C - Crédito']['VALOR_CENTS'].sum()
    dif_global = total_d_cents - total_c_cents

    print(f"  Total Débitos: {total_d_cents / 100:,.2f}")

    # Validacao DETALHADA de sequencias
    seq_desbalanceadas = 0
    seq_details = []
    for seq in new_df['NumSequencia'].unique():
        if pd.isna(seq):
            continue
        seq_mask = new_df['NumSequencia'] == seq
        d = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'D - Débito'), 'VALOR_CENTS'].sum()
        c = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'C - Crédito'), 'VALOR_CENTS'].sum()
        dif_seq = d - c
        if dif_seq != 0:
            seq_desbalanceadas += 1
            if seq_desbalanceadas <= 5:
                seq_details.append((seq, dif_seq / 100))

    if seq_desbalanceadas > 0:
        print(f"  [ERR] {seq_desbalanceadas} Sequências desbalanceadas:")
        for seq, diff in seq_details:
            print(f"    - Seq {seq}: diferença {diff:.2f}")
            log_event(logger, 30, "sequencia_desbalanceada", etapa="saida_validacao", sequencia=seq, diferenca=diff)
    else:
        print("  [OK] Sequências balanceadas (D=C)")

    # Validar contas prioritarias
    erros_prioritarios = 0
    for conta in contas_prioritarias:
        for acao in ['D - Débito', 'C - Crédito']:
            mask = (new_df['CONTA'] == conta) & (new_df['ACAO_LIMPA'] == acao)
            if not mask.any():
                continue
            total_origem = df_original[
                (df_original['Conta'] == conta) & (df_original['ACAO_LIMPA'] == acao)
            ]['Valor'].sum()
            if total_origem == 0:
                continue
            total_decimal = Decimal(str(total_origem)) * Decimal(str(percentual))
            total_esperado_cents = int(
                (total_decimal * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            )
            total_atual_cents = int(new_df.loc[mask, 'VALOR_CENTS'].sum())
            diferenca_cents = abs(total_atual_cents - total_esperado_cents)
            if diferenca_cents > TOLERANCIA_CONTAS_PRIORITARIAS:
                erros_prioritarios += 1
                print(
                    f"  [ERR] ERRO PRIORITÁRIO: {conta} ({acao}): "
                    f"Esperado {total_esperado_cents/100:.2f}, "
                    f"Atual {total_atual_cents/100:.2f}, "
                    f"Dif: {diferenca_cents/100:.2f}"
                )
                log_event(
                    logger,
                    40,
                    "conta_prioritaria_divergente",
                    etapa="saida_validacao",
                    conta=conta,
                    diferenca=diferenca_cents / 100,
                )

    if erros_prioritarios == 0:
        print(f"  [OK] TODAS AS {len(contas_prioritarias)} CONTAS PRIORITÁRIAS FECHADAS 100%")

    # Validar outras contas
    erros_conta = 0
    for (conta, acao), grupo_orig in df_original.groupby(['Conta', 'ACAO_LIMPA']):
        if conta in contas_prioritarias:
            continue
        total_origem = grupo_orig['Valor'].sum()
        total_decimal = Decimal(str(total_origem)) * Decimal(str(percentual))
        total_esperado_cents = int(
            (total_decimal * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        )
        mask = (new_df['CONTA'] == conta) & (new_df['ACAO_LIMPA'] == acao)
        total_atual_cents = int(new_df.loc[mask, 'VALOR_CENTS'].sum())
        if total_atual_cents != total_esperado_cents:
            erros_conta += 1

    if erros_conta == 0:
        print("  [OK] Outras contas/ações fechadas conforme percentual")
    else:
        print(f"  [WARN] {erros_conta} outras contas/ações com pequenas diferenças")

    seq_desbalanceadas = 0
    for seq in new_df['NumSequencia'].unique():
        if pd.isna(seq):
            continue
        seq_mask = new_df['NumSequencia'] == seq
        d = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'D - Débito'), 'VALOR_CENTS'].sum()
        c = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'C - Crédito'), 'VALOR_CENTS'].sum()
        if d != c:
            seq_desbalanceadas += 1

    if seq_desbalanceadas == 0:
        print("  [OK] Sequências balanceadas (D=C)")
    else:
        print(f"  [ERR] {seq_desbalanceadas} Sequências desbalanceadas")

    if dif_global == 0:
        print("  [OK] Global balanceado (D=C)")
    elif abs(dif_global) <= TOLERANCIA_GLOBAL:
        print(f"  [OK] Global balanceado (D=C) - Dentro da tolerância: {dif_global / 100:,.2f}")
    else:
        print(f"  [ERR] Global desbalanceado: diferença de {dif_global / 100:,.2f}")
        log_event(logger, 40, "global_desbalanceado", etapa="saida_validacao", diferenca=dif_global / 100)

    print("=" * 70)

    # --- PASSO 4.5: Piso de 0,01 centavos ---
    print("\n[PASSO 4.5] Aplicando piso de 0,01 centavos...")
    zeros_encontrados = (new_df['VALOR_CENTS'] == 0).sum()
    if zeros_encontrados > 0:
        new_df.loc[new_df['VALOR_CENTS'] == 0, 'VALOR_CENTS'] = 1
        print(f"  Encontrados {zeros_encontrados} valores 0,00 → convertidos para 0,01")
        print(f"  Reconvergindo sequências quebradas...")
        seq_rebalanceadas = 0
        for seq in new_df['NumSequencia'].unique():
            if pd.isna(seq):
                continue
            seq_mask = new_df['NumSequencia'] == seq
            d_cents = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'D - Débito'), 'VALOR_CENTS'].sum()
            c_cents = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'C - Crédito'), 'VALOR_CENTS'].sum()
            dif = d_cents - c_cents
            if dif != 0:
                debitos_mask = seq_mask & (new_df['ACAO_LIMPA'] == 'D - Débito')
                creditos_mask = seq_mask & (new_df['ACAO_LIMPA'] == 'C - Crédito')
                if dif > 0 and creditos_mask.any():
                    idx = new_df.loc[creditos_mask, 'VALOR_CENTS'].abs().idxmax()
                    new_df.loc[idx, 'VALOR_CENTS'] += dif
                elif dif < 0 and debitos_mask.any():
                    idx = new_df.loc[debitos_mask, 'VALOR_CENTS'].abs().idxmax()
                    new_df.loc[idx, 'VALOR_CENTS'] -= dif
                seq_rebalanceadas += 1
        print(f"  {seq_rebalanceadas} sequências reconvergidas")
    else:
        print("  Nenhum valor zero encontrado")

    # Converter de volta para VALOR (decimal)
    new_df['VALOR'] = (new_df['VALOR_CENTS'] / 100).round(2)

    new_df = new_df.drop(columns=['ACAO_LIMPA', 'VALOR_CENTS'])

    # Remover colunas temporarias criadas durante processamento
    cols_temp = ['_lance_id', 'VALOR_ORIGINAL']
    new_df = new_df.drop(columns=[c for c in cols_temp if c in new_df.columns])

    # Substituir conta 3.6.03.03.000002 por 1.1.11.04.000005 em debitos
    mask_substituir = (new_df['CONTA'] == '3.6.03.03.000002') & (new_df['ACAO'] == 'D - Débito')
    new_df.loc[mask_substituir, 'CONTA'] = '1.1.11.04.000005'

    # Formatar data para DD/MM/YYYY
    if 'Data' in new_df.columns and not new_df['Data'].isna().all():
        new_df['Data'] = pd.to_datetime(new_df['Data'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('')
    else:
        new_df['Data'] = ''

    # Simplificar ACAO: "C - Credito" -> "C" e "D - Debito" -> "D"
    new_df['ACAO'] = new_df['ACAO'].str.replace('C - Crédito', 'C').str.replace('D - Débito', 'D').str.strip()

    # Limpeza final de espacamento em colunas textuais
    new_df['HISTORICO'] = new_df['HISTORICO'].str.strip()
    new_df['CONTA'] = new_df['CONTA'].str.strip()
    new_df['ContaContraPartida'] = new_df['ContaContraPartida'].str.strip()

    # Remover TODAS as colunas temporarias/tecnicas antes do retorno
    cols_temp = ['_reclassificado', '_lance_id_temp', '_CONTA_NORM', '_CONTRA_NORM', '_preservar_100']
    new_df = new_df.drop(columns=[c for c in cols_temp if c in new_df.columns])

    # Reordenar colunas para o layout final do UAU
    cols_order = [
        'Lancamento', 'DOC', 'NUMCHEQUE', 'CategoriaMovimentacaoFinanceira',
        'Empresa', 'Data', 'VALOR', 'CONTA', 'ACAO', 'HISTORICO',
        'Obra', 'NumSequencia', 'ContaContraPartida', 'TipoLancamento',
    ]
    return new_df[cols_order]
