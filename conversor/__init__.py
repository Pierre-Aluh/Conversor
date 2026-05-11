# -*- coding: utf-8 -*-
"""Pacote interno do Conversor Contabil.

Modulos:
    _entrada   - validacao de parametros, leitura e normalizacao do DataFrame
    _exclusao  - exclusao de grupo de contas e reclassificacao de repasses
    _ajuste    - passos 1-3: percentual, sincronizacao D/C, ajuste e fechamento
    _saida     - passos 4-4.5: validacao, piso 0,01, formatacao e reordenacao
"""
