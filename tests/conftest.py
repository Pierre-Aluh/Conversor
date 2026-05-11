"""
Fixtures anonimizadas para testes de caracterizacao do Conversor Contabil.

Nenhum dado real de dominio e usado. Os valores sao pequenos e representativos
apenas para exercitar os invariantes contabeis sem depender de arquivo local.
"""
import pytest
import pandas as pd

# ---------------------------------------------------------------------------
# Constantes compartilhadas com os testes
# ---------------------------------------------------------------------------
CONTA_ARREDONDAMENTO = "9.9.99.99.000001"
CONTA_PRIORITARIA = "1.1.02.01.000004"  # primeira conta sagrada em config.py
CONTA_A = "2.1.01.01.000001"
CONTA_B = "2.1.01.01.000002"
CONTA_C = "2.1.01.01.000003"
COD_EMPRESA = 1
COD_OBRA = 1


def _xlsx(df: pd.DataFrame, tmp_path, nome: str):
    """Salva DataFrame em xlsx anonimizado na pasta temporaria de teste."""
    path = tmp_path / nome
    df.to_excel(path, index=False)
    return path


@pytest.fixture
def planilha_dois_pares(tmp_path):
    """
    Dois pares D/C sem contas prioritarias, valores 100.00 e 200.00.
    Exercita o caminho basico de conversao proporcional.
    """
    rows = [
        {"Sequência": 1, "Ação": "D - Débito",  "Conta": CONTA_A, "Valor": 100.00, "Contra part.": CONTA_B},
        {"Sequência": 1, "Ação": "C - Crédito", "Conta": CONTA_B, "Valor": 100.00, "Contra part.": CONTA_A},
        {"Sequência": 2, "Ação": "D - Débito",  "Conta": CONTA_C, "Valor": 200.00, "Contra part.": CONTA_B},
        {"Sequência": 2, "Ação": "C - Crédito", "Conta": CONTA_B, "Valor": 200.00, "Contra part.": CONTA_C},
    ]
    return _xlsx(pd.DataFrame(rows), tmp_path, "dois_pares.xlsx")


@pytest.fixture
def planilha_arredondamento(tmp_path):
    """
    Par D/C com valor 1.00. Ao aplicar percentual 1/3, gera centavo fracionado.
    Exercita o piso de 0,01 e a reconvergencia de sequencia apos arredondamento.
    """
    rows = [
        {"Sequência": 3, "Ação": "D - Débito",  "Conta": CONTA_A, "Valor": 1.00, "Contra part.": CONTA_B},
        {"Sequência": 3, "Ação": "C - Crédito", "Conta": CONTA_B, "Valor": 1.00, "Contra part.": CONTA_A},
    ]
    return _xlsx(pd.DataFrame(rows), tmp_path, "arredondamento.xlsx")


@pytest.fixture
def planilha_conta_prioritaria(tmp_path):
    """
    Par D/C com conta sagrada no debito, valor 1000.00 e percentual 50%.
    Divisao exata: 500.00. Exercita tolerancia zero para contas prioritarias.
    """
    rows = [
        {"Sequência": 4, "Ação": "D - Débito",  "Conta": CONTA_PRIORITARIA, "Valor": 1000.00, "Contra part.": CONTA_A},
        {"Sequência": 4, "Ação": "C - Crédito", "Conta": CONTA_A,           "Valor": 1000.00, "Contra part.": CONTA_PRIORITARIA},
    ]
    return _xlsx(pd.DataFrame(rows), tmp_path, "prioritaria.xlsx")
