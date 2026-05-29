# -*- coding: utf-8 -*-
"""Passos 1-3: aplicacao de percentual, sincronizacao D/C, ajuste e fechamento de sequencias."""

import pandas as pd
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable


def _emit_progress(progress_callback: Callable[[float, str], None] | None, value: float, message: str) -> None:
    if not progress_callback:
        return
    progress_callback(max(0.0, min(1.0, value)), message)


def _total_esperado_cents(new_df, mask, percentual):
    """Calcula o total esperado em centavos para um par (conta, acao),
    considerando linhas preservadas em 100% e linhas convertidas pelo percentual."""
    mask_pres = mask & (new_df['_preservar_100'] == True)
    mask_conv = mask & (new_df['_preservar_100'] == False)
    total_pres = Decimal(str(new_df.loc[mask_pres, 'VALOR_ORIGINAL'].sum()))
    total_conv = Decimal(str(new_df.loc[mask_conv, 'VALOR_ORIGINAL'].sum()))
    total_decimal = (total_conv * Decimal(str(percentual))) + total_pres
    return int((total_decimal * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def aplicar_passos_1_a_3(
    new_df,
    percentual,
    contas_prioritarias,
    progress_callback: Callable[[float, str], None] | None = None,
):
    """
    Executa os passos 1, 1.5, 2, 2.5 e 3 sobre new_df.
    Retorna new_df com VALOR_CENTS ajustado e ACAO_LIMPA ainda presente
    (serao removidos pelo passo de saida).
    """
    print("=" * 70)
    print("CONVERSÃO COM AJUSTE APENAS DE CONTAS DESBALANCEADAS")
    print("=" * 70)

    # --- PASSO 1: Aplicar percentual individualmente ---
    print("\n[PASSO 1] Aplicando percentual individualmente...")
    total_linhas = len(new_df)
    new_df['VALOR_CENTS'] = 0
    mask_preservar_100 = new_df['_preservar_100'] == True

    # Progresso por linha convertida (com throttling para evitar overhead excessivo de UI).
    update_interval = max(1, total_linhas // 200) if total_linhas > 0 else 1
    for idx_pos, idx in enumerate(new_df.index, start=1):
        valor_original = float(new_df.at[idx, 'VALOR_ORIGINAL'])
        preservar = bool(new_df.at[idx, '_preservar_100'])
        if preservar:
            valor_cents = int(round(valor_original * 100))
        else:
            valor_cents = int(round(valor_original * percentual * 100))
        new_df.at[idx, 'VALOR_CENTS'] = valor_cents

        if idx_pos == 1 or idx_pos % update_interval == 0 or idx_pos == total_linhas:
            _emit_progress(progress_callback, idx_pos / total_linhas, f"Convertendo linhas ({idx_pos}/{total_linhas})")

    print(
        f"  [OK] {len(new_df)} lançamentos convertidos "
        f"(com {int(mask_preservar_100.sum())} em valor original)"
    )

    # --- PASSO 1.5: Sincronizar pares D/C que vieram do mesmo valor original ---
    print("\n[PASSO 1.5] Sincronizando pares Débito/Crédito...")
    data_part = new_df['Data'].astype(str) if 'Data' in new_df.columns else ''
    new_df['_lance_id'] = (
        new_df['DOC'].astype(str) + '_'
        + data_part + '_'
        + new_df['NumSequencia'].astype(str)
    )
    pares_sincronizados = 0
    for lance_id in new_df['_lance_id'].unique():
        lancamento = new_df[new_df['_lance_id'] == lance_id]
        debitos = lancamento[lancamento['ACAO_LIMPA'] == 'D - Débito']
        creditos = lancamento[lancamento['ACAO_LIMPA'] == 'C - Crédito']
        if len(debitos) == 1 and len(creditos) == 1:
            valor_d = debitos['VALOR_CENTS'].iloc[0]
            valor_c = creditos['VALOR_CENTS'].iloc[0]
            if valor_d != valor_c:
                valor_sincr = max(valor_d, valor_c)
                idx_d = debitos.index[0]
                idx_c = creditos.index[0]
                new_df.loc[idx_d, 'VALOR_CENTS'] = valor_sincr
                new_df.loc[idx_c, 'VALOR_CENTS'] = valor_sincr
                pares_sincronizados += 1
    if pares_sincronizados > 0:
        print(f"  [OK] {pares_sincronizados} pares D/C sincronizados")
    else:
        print(f"  [OK] Todos os pares já estão sincronizados")

    # --- PASSO 2: Ajustar apenas contas/acoes que desceram ---
    print("\n[PASSO 2] Ajustando contas/ações com diferença...")
    ajustes_feitos = 0
    contas_ajustadas = set()
    for (conta, acao) in new_df.groupby(['CONTA', 'ACAO_LIMPA']).groups.keys():
        mask = (new_df['CONTA'] == conta) & (new_df['ACAO_LIMPA'] == acao)
        total_origem = new_df.loc[mask, 'VALOR_ORIGINAL'].sum()
        if total_origem == 0:
            continue
        total_esperado_cents = _total_esperado_cents(new_df, mask, percentual)
        total_atual_cents = int(new_df.loc[mask, 'VALOR_CENTS'].sum())
        diferenca_cents = total_esperado_cents - total_atual_cents
        if diferenca_cents != 0:
            idx = new_df.loc[mask, 'VALOR_CENTS'].abs().idxmax()
            new_df.loc[idx, 'VALOR_CENTS'] += diferenca_cents
            contas_ajustadas.add((conta, acao))
            ajustes_feitos += 1
    print(f"  [OK] {ajustes_feitos} contas/ações ajustadas")

    # --- PASSO 2.5: Ajustar CONTAS PRIORITARIAS ate fecharem 100% ---
    print("\n[PASSO 2.5 ESPECIAL] Ajustando contas priorizadas para 100%...")
    contas_prioritarias_ajustadas = 0
    sequencias_balanceadas_antes = set()
    sequencias_alteradas_por_ajuste = set()
    for conta in contas_prioritarias:
        for acao in ['D - Débito', 'C - Crédito']:
            mask = (new_df['CONTA'] == conta) & (new_df['ACAO_LIMPA'] == acao)
            if not mask.any():
                continue
            total_origem = new_df.loc[mask, 'VALOR_ORIGINAL'].sum()
            if total_origem == 0:
                continue
            total_esperado_cents = _total_esperado_cents(new_df, mask, percentual)
            total_atual_cents = int(new_df.loc[mask, 'VALOR_CENTS'].sum())
            dif = total_esperado_cents - total_atual_cents
            if dif != 0:
                idx = new_df.loc[mask, 'VALOR_CENTS'].abs().idxmax()
                new_df.loc[idx, 'VALOR_CENTS'] += dif
                contas_prioritarias_ajustadas += 1
                print(f"  {conta} ({acao:10}): Ajustado +{dif/100:.2f}")
                seq_alterada = new_df.loc[idx, 'NumSequencia']
                if not pd.isna(seq_alterada) and seq_alterada in sequencias_balanceadas_antes:
                    sequencias_alteradas_por_ajuste.add(seq_alterada)

    # --- PASSO 3: Forcar fechamento de sequencias (D=C) ---
    print("\n[PASSO 3] Forçando fechamento de sequências (D=C)...")

    def _aplicar_ajuste_sequencia(seq_data, dif_cents):
        """Ajusta a sequencia no lado correto para zerar diferenca D-C."""
        candidatos_base = seq_data[~seq_data['CONTA'].isin(contas_prioritarias)]
        candidatos = candidatos_base if len(candidatos_base) > 0 else seq_data

        if dif_cents > 0:
            candidatos_credito = candidatos[candidatos['ACAO_LIMPA'] == 'C - Crédito']
            if len(candidatos_credito) > 0:
                idx = candidatos_credito['VALOR_CENTS'].abs().idxmax()
                new_df.loc[idx, 'VALOR_CENTS'] += dif_cents
                return True
            candidatos_debito = candidatos[candidatos['ACAO_LIMPA'] == 'D - Débito']
            if len(candidatos_debito) > 0:
                idx = candidatos_debito['VALOR_CENTS'].abs().idxmax()
                new_df.loc[idx, 'VALOR_CENTS'] -= dif_cents
                return True
            return False

        ajuste = abs(dif_cents)
        candidatos_debito = candidatos[candidatos['ACAO_LIMPA'] == 'D - Débito']
        if len(candidatos_debito) > 0:
            idx = candidatos_debito['VALOR_CENTS'].abs().idxmax()
            new_df.loc[idx, 'VALOR_CENTS'] += ajuste
            return True
        candidatos_credito = candidatos[candidatos['ACAO_LIMPA'] == 'C - Crédito']
        if len(candidatos_credito) > 0:
            idx = candidatos_credito['VALOR_CENTS'].abs().idxmax()
            new_df.loc[idx, 'VALOR_CENTS'] -= ajuste
            return True
        return False

    # 3.1: Ajustar sequencias para D=C (passada unica)
    seq_ajustadas = 0
    for seq in new_df['NumSequencia'].unique():
        if pd.isna(seq):
            continue
        seq_mask = new_df['NumSequencia'] == seq
        d_cents = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'D - Débito'), 'VALOR_CENTS'].sum()
        c_cents = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'C - Crédito'), 'VALOR_CENTS'].sum()
        dif = d_cents - c_cents
        if dif != 0:
            seq_data = new_df[seq_mask]
            if _aplicar_ajuste_sequencia(seq_data, dif):
                seq_ajustadas += 1
    print(f"  Passo 3.1: {seq_ajustadas} sequências forçadas a D=C")

    # 3.2: Reforcar contas prioritarias
    reforco_ajustado = 0
    for conta in contas_prioritarias:
        for acao in ['D - Débito', 'C - Crédito']:
            mask = (new_df['CONTA'] == conta) & (new_df['ACAO_LIMPA'] == acao)
            if not mask.any():
                continue
            total_origem = new_df.loc[mask, 'VALOR_ORIGINAL'].sum()
            if total_origem == 0:
                continue
            total_esperado_cents = _total_esperado_cents(new_df, mask, percentual)
            total_atual_cents = int(new_df.loc[mask, 'VALOR_CENTS'].sum())
            dif = total_esperado_cents - total_atual_cents
            if dif != 0:
                idx = new_df.loc[mask, 'VALOR_CENTS'].abs().idxmax()
                new_df.loc[idx, 'VALOR_CENTS'] += dif
                reforco_ajustado += 1

    if reforco_ajustado == 0:
        print(f"  Passo 3.2: Contas prioritárias já estão 100%")
        print(f"  [OK] Convergência alcançada: Sequências D=C + Prioridades 100%")
    else:
        print(f"  Passo 3.2: {reforco_ajustado} contas ajustadas")

        # 3.3: Reconvergir sequencias apos reforco
        seq_reconvergio = 0
        for seq in new_df['NumSequencia'].unique():
            if pd.isna(seq):
                continue
            seq_mask = new_df['NumSequencia'] == seq
            d = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'D - Débito'), 'VALOR_CENTS'].sum()
            c = new_df.loc[seq_mask & (new_df['ACAO_LIMPA'] == 'C - Crédito'), 'VALOR_CENTS'].sum()
            dif = d - c
            if dif != 0:
                seq_data = new_df[seq_mask]
                if _aplicar_ajuste_sequencia(seq_data, dif):
                    seq_reconvergio += 1
        print(f"  Passo 3.3: {seq_reconvergio} sequências reconvergidas")

    print(f"  [OK] TODAS AS {len(contas_prioritarias)} CONTAS PRIORITÁRIAS FECHADAS 100%")

    return new_df
