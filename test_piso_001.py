#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
from pathlib import Path
from Conversor import gerar_contabilidade_consorciada

base = Path('.')
entrada = base/'entrada'/'Petra.xlsx'
saida_dir = base/'saida'

with open(base/'cadastros.json', encoding='utf-8') as f:
    data = json.load(f)

alvos = [c for c in data['consorciadas'] if c['nome'] in ['Miranda Campos Loteamento SPE', 'NB Participações Ltda']]

print("[TESTE COM PISO DE 0.01]\n")
for c in alvos:
    print(f"Processando {c['nome']} ({c['percentual']}%)...")
    
    df = gerar_contabilidade_consorciada(
        entrada,
        c['percentual']/100,
        c['codigo_empresa'],
        c['codigo_obra'],
        c['conta_arredondamento'],
        c['conta_repasse_ativo'],
        c['conta_repasse_passivo'],
        c['grupo_excluido']
    )
    
    print(f"  Total linhas: {len(df)}")
    
    # Verificar valores zero
    zeros = (df['VALOR'] == 0).sum()
    valores_min = ((df['VALOR'] > 0) & (df['VALOR'] < 0.02)).sum()
    print(f"  Valores 0.00: {zeros}")
    print(f"  Valores 0.01: {valores_min}")
    
    # Validar sequências problemáticas
    for seq in [177939, 177963]:
        seq_data = df[df['NumSequencia'] == seq]
        if len(seq_data) > 0:
            d = seq_data[seq_data['ACAO'] == 'D']['VALOR'].sum()
            c_val = seq_data[seq_data['ACAO'] == 'C']['VALOR'].sum()
            diff = d - c_val
            status = "OK" if abs(diff) < 0.005 else "ERRO"
            print(f"  Seq {seq} [{status}]: D={d:.2f}, C={c_val:.2f}, diff={diff:.4f}")
    
    # Salvar
    nome_saida = f"Petra - {c['nome']} - Convertido.xlsx"
    arquivo_saida = saida_dir / nome_saida
    df.to_excel(arquivo_saida, index=False)
    print(f"  Arquivo: {nome_saida}\n")

print("="*60)
print("VALIDACAO GLOBAL")
print("="*60)

import pandas as pd
for c in alvos:
    nome_saida = f"Petra - {c['nome']} - Convertido.xlsx"
    arquivo_saida = saida_dir / nome_saida
    df_check = pd.read_excel(arquivo_saida)
    
    # Contar valores zero
    total_zeros = (df_check['VALOR'] == 0).sum()
    
    if total_zeros > 0:
        print(f"[AVISO] {c['nome']}: AINDA CONTEM {total_zeros} VALORES ZERO")
    else:
        print(f"[OK] {c['nome']}: SEM VALORES ZERO")
