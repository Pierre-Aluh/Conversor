# -*- coding: utf-8 -*-
"""Configuracoes centrais do conversor contabil."""

# 13 contas prioritarias (sagradas) que devem fechar com exatidao.
CONTAS_PRIORITARIAS = {
    '1.1.02.01.000004',
    '1.1.02.01.000005',
    '1.1.02.01.000006',
    '1.1.02.01.000007',
    '3.2.05.03.000001',
    '3.2.05.03.000002',
    '3.7.01.01.000014',
    '3.8.01.01.000001',
    '3.8.01.01.000009',
    '3.8.01.01.000010',
    '3.8.01.02.000003',
    '3.8.01.03.000001',
    '3.8.02.03.000001',
}

# Tolerancias em centavos.
TOLERANCIA_CONTAS_PRIORITARIAS = 0
TOLERANCIA_OUTRAS_CONTAS = 1
TOLERANCIA_GLOBAL = 0
