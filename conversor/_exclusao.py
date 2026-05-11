# -*- coding: utf-8 -*-
"""Exclusao de grupo de contas e reclassificacao de repasses."""

import pandas as pd


def aplicar_exclusao_grupo(new_df, repasse_ativo, repasse_passivo, grupo_excluido):
    """
    Remove do new_df as linhas do grupo_excluido e suas contrapartidas,
    reclassificando o repasse_passivo para repasse_ativo onde aplicavel.

    Se repasse_ativo, repasse_passivo ou grupo_excluido nao estiverem
    definidos, retorna new_df sem alteracao.
    """
    if not (repasse_ativo and repasse_passivo and grupo_excluido):
        return new_df

    print(f"\n[PASSO EXCLUSÃO INICIAL] Removendo grupo {grupo_excluido}...")

    def _norm_conta(valor):
        return str(valor).strip().rstrip('.')

    def _conta_no_grupo(conta_norm, grupo_norm):
        return conta_norm == grupo_norm or conta_norm.startswith(grupo_norm + '.')

    def _indices_contrapartida(lancamento_df, idx):
        """Retorna indices da contrapartida da linha, priorizando par inverso exato."""
        linha = lancamento_df.loc[idx]
        conta = linha['_CONTA_NORM']
        contra = linha['_CONTRA_NORM']
        acao = linha['ACAO_LIMPA']

        if not contra:
            return []

        mask_exata = (
            (lancamento_df['_CONTA_NORM'] == contra)
            & (lancamento_df['_CONTRA_NORM'] == conta)
            & (lancamento_df['ACAO_LIMPA'] != acao)
        )
        idxs = lancamento_df[mask_exata].index.tolist()
        if idxs:
            return idxs

        mask_fallback = (
            (lancamento_df['_CONTA_NORM'] == contra)
            & (lancamento_df['ACAO_LIMPA'] != acao)
        )
        return lancamento_df[mask_fallback].index.tolist()

    grupo_excluido_norm = _norm_conta(grupo_excluido)
    repasse_passivo_norm = _norm_conta(repasse_passivo)
    repasse_ativo_norm = _norm_conta(repasse_ativo)

    linhas_antes_exclusao = len(new_df)

    if 'Data' in new_df.columns and not new_df['Data'].isna().all():
        data_str = pd.to_datetime(new_df['Data'], errors='coerce').dt.strftime('%Y%m%d').fillna('00000000')
    else:
        data_str = '00000000'

    new_df['_lance_id_temp'] = (
        data_str + '_'
        + new_df['NumSequencia'].astype(str)
        + '_'
        + new_df['VALOR_ORIGINAL'].astype(str)
    )
    new_df['_CONTA_NORM'] = new_df['CONTA'].astype(str).str.strip().str.rstrip('.')
    new_df['_CONTRA_NORM'] = new_df['ContaContraPartida'].astype(str).str.strip().str.rstrip('.')

    contas_no_grupo = sorted({
        conta for conta in new_df['_CONTA_NORM'].unique().tolist()
        if _conta_no_grupo(conta, grupo_excluido_norm)
    })

    if not contas_no_grupo:
        print("\n" + "!" * 70)
        print("⚠️  AVISO: Grupo para exclusão não encontrado no arquivo")
        print("!" * 70)
        print(f"Grupo configurado: {grupo_excluido_norm}")
        print("O filtro de exclusão não será aplicado.")
        print("A conversão continuará normalmente com todos os lançamentos.")
        print("!" * 70 + "\n")
        new_df = new_df.drop(columns=['_lance_id_temp', '_CONTA_NORM', '_CONTRA_NORM'])
        return new_df

    if repasse_passivo_norm not in contas_no_grupo:
        contas_exemplo = ', '.join(contas_no_grupo[:8])
        sufixo_repasse = (
            repasse_passivo_norm.split('.')[-1]
            if '.' in repasse_passivo_norm
            else repasse_passivo_norm
        )
        contas_todas = sorted(
            set(new_df['_CONTA_NORM'].unique().tolist() + new_df['_CONTRA_NORM'].unique().tolist())
        )
        contas_mesmo_sufixo = [c for c in contas_todas if c.endswith('.' + sufixo_repasse)]
        dica_conta = (
            f"\n  Dica: contas com final {sufixo_repasse} no arquivo: {', '.join(contas_mesmo_sufixo[:6])}"
            if contas_mesmo_sufixo
            else ''
        )
        raise ValueError(
            "❌ ERRO DE CONFIGURAÇÃO: Conta Repasse Passivo não encontrada no grupo informado.\n"
            f"  Grupo: {grupo_excluido_norm}\n"
            f"  Repasse passivo informado: {repasse_passivo_norm}\n"
            f"  Contas encontradas no grupo: {contas_exemplo}"
            f"{dica_conta}"
        )

    linhas_para_excluir = set()
    linhas_para_reclassificar = set()

    for lance_id in new_df['_lance_id_temp'].unique():
        lancamento_mask = new_df['_lance_id_temp'] == lance_id
        lancamento = new_df[lancamento_mask]

        if lancamento.empty:
            continue

        idxs_grupo = [
            idx for idx in lancamento.index
            if _conta_no_grupo(new_df.loc[idx, '_CONTA_NORM'], grupo_excluido_norm)
        ]
        if not idxs_grupo:
            continue

        idxs_preservar = set()
        idxs_repasse = lancamento[
            (lancamento['_CONTA_NORM'] == repasse_passivo_norm)
            | (lancamento['_CONTRA_NORM'] == repasse_passivo_norm)
        ].index.tolist()

        for idx_rep in idxs_repasse:
            idxs_preservar.add(idx_rep)
            for idx_cp in _indices_contrapartida(lancamento, idx_rep):
                idxs_preservar.add(idx_cp)

        for idx in idxs_preservar:
            new_df.loc[idx, '_preservar_100'] = True

        for idx in idxs_grupo:
            if idx in idxs_preservar:
                continue
            linhas_para_excluir.add(idx)
            for idx_cp in _indices_contrapartida(lancamento, idx):
                if idx_cp not in idxs_preservar:
                    linhas_para_excluir.add(idx_cp)

        for idx in idxs_preservar:
            if new_df.loc[idx, '_CONTA_NORM'] == repasse_passivo_norm:
                linhas_para_reclassificar.add(idx)

    reclassificados = 0
    if linhas_para_reclassificar:
        idxs_reclassificar = list(linhas_para_reclassificar)
        new_df.loc[idxs_reclassificar, 'CONTA'] = repasse_ativo_norm
        new_df.loc[idxs_reclassificar, '_CONTA_NORM'] = repasse_ativo_norm
        reclassificados = len(idxs_reclassificar)

    if linhas_para_excluir:
        new_df = new_df.drop(list(linhas_para_excluir)).reset_index(drop=True)
        excluidos = linhas_antes_exclusao - len(new_df)
    else:
        excluidos = 0

    linhas_preservadas = int(new_df['_preservar_100'].sum())

    new_df = new_df.drop(columns=['_lance_id_temp', '_CONTA_NORM', '_CONTRA_NORM'])

    print(f"  Grupo: {grupo_excluido_norm}")
    print(f"  [OK] {excluidos} linhas removidas (grupo + contrapartidas)")
    print(f"  [OK] {reclassificados} linhas reclassificadas {repasse_passivo_norm} -> {repasse_ativo_norm}")
    print(f"  [*] {linhas_preservadas} linhas preservadas com valor 100%")

    return new_df
