"""
Testes de caracterizacao - Etapa 4 do Plano de Correcao em 9 Etapas.

Invariantes verificados:
  I1 - Fechamento D=C por NumSequencia (tolerancia: exata em centavos)
  I2 - Contas prioritarias respeitam TOLERANCIA_CONTAS_PRIORITARIAS (= 0)
  I3 - Tolerancias e arredondamentos: nenhum VALOR abaixo do piso 0,01

Fixtures anonimizadas definidas em tests/conftest.py.
Nenhum arquivo de dominio real e referenciado neste modulo.
"""
import pytest

from motor_conversao_contabil import gerar_contabilidade_consorciada
from config import CONTAS_PRIORITARIAS, TOLERANCIA_CONTAS_PRIORITARIAS
from tests.conftest import (
    CONTA_ARREDONDAMENTO,
    CONTA_PRIORITARIA,
    COD_EMPRESA,
    COD_OBRA,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _converter(arquivo, percentual=0.5):
    return gerar_contabilidade_consorciada(
        arquivo,
        percentual,
        COD_EMPRESA,
        COD_OBRA,
        conta_arredondamento=CONTA_ARREDONDAMENTO,
    )


def _cents(valor_reais: float) -> int:
    """Converte reais para centavos inteiros sem acumular erro de ponto flutuante."""
    return round(valor_reais * 100)


# ---------------------------------------------------------------------------
# I1 - Fechamento D=C por NumSequencia
# ---------------------------------------------------------------------------

class TestFechamentoDCPorSequencia:
    """
    Para toda NumSequencia no output: soma(VALOR onde ACAO='D') deve ser
    igual a soma(VALOR onde ACAO='C'), em centavos inteiros.
    """

    def test_pares_simples_fecham_em_50_pct(self, planilha_dois_pares):
        df = _converter(planilha_dois_pares, percentual=0.5)
        for seq, grupo in df.groupby("NumSequencia"):
            d = _cents(grupo.loc[grupo["ACAO"] == "D", "VALOR"].sum())
            c = _cents(grupo.loc[grupo["ACAO"] == "C", "VALOR"].sum())
            assert d == c, f"Seq {seq}: D={d} centavos != C={c} centavos"

    def test_arredondamento_um_terco_fecha(self, planilha_arredondamento):
        """Percentual 1/3 gera fracao; o algoritmo deve reconvergir D=C."""
        df = _converter(planilha_arredondamento, percentual=1 / 3)
        for seq, grupo in df.groupby("NumSequencia"):
            d = _cents(grupo.loc[grupo["ACAO"] == "D", "VALOR"].sum())
            c = _cents(grupo.loc[grupo["ACAO"] == "C", "VALOR"].sum())
            assert d == c, f"Seq {seq} (percentual 1/3): D={d} != C={c}"

    def test_conta_prioritaria_seq_fecha(self, planilha_conta_prioritaria):
        df = _converter(planilha_conta_prioritaria, percentual=0.5)
        for seq, grupo in df.groupby("NumSequencia"):
            d = _cents(grupo.loc[grupo["ACAO"] == "D", "VALOR"].sum())
            c = _cents(grupo.loc[grupo["ACAO"] == "C", "VALOR"].sum())
            assert d == c, f"Seq {seq} (conta prioritaria): D={d} != C={c}"


# ---------------------------------------------------------------------------
# I2 - Contas prioritarias respeitam tolerancia de configuracao
# ---------------------------------------------------------------------------

class TestContasPrioritarias:
    """
    Para cada conta sagrada presente no output, a soma dos valores deve
    diferir do esperado (valor_original * percentual) em no maximo
    TOLERANCIA_CONTAS_PRIORITARIAS centavos (configurado como 0).
    """

    def test_conta_prioritaria_exatamente_500(self, planilha_conta_prioritaria):
        """1000.00 * 50% = 500.00 exatos, tolerancia 0."""
        percentual = 0.5
        df = _converter(planilha_conta_prioritaria, percentual=percentual)

        conta_d = df[(df["CONTA"] == CONTA_PRIORITARIA) & (df["ACAO"] == "D")]
        assert not conta_d.empty, f"Conta prioritaria {CONTA_PRIORITARIA} nao encontrada no output"

        total_cents = _cents(conta_d["VALOR"].sum())
        esperado_cents = _cents(1000.00 * percentual)
        diferenca = abs(total_cents - esperado_cents)

        assert diferenca <= TOLERANCIA_CONTAS_PRIORITARIAS, (
            f"{CONTA_PRIORITARIA} (D): diferenca {diferenca} centavos "
            f"> tolerancia {TOLERANCIA_CONTAS_PRIORITARIAS}"
        )

    def test_nenhuma_conta_prioritaria_violada(self, planilha_conta_prioritaria):
        """Nenhuma conta sagrada presente no output pode violar a tolerancia zero."""
        percentual = 0.5
        valor_original = 1000.00
        df = _converter(planilha_conta_prioritaria, percentual=percentual)

        for conta in CONTAS_PRIORITARIAS:
            for acao_label in ("D", "C"):
                grupo = df[(df["CONTA"] == conta) & (df["ACAO"] == acao_label)]
                if grupo.empty:
                    continue
                total_cents = _cents(grupo["VALOR"].sum())
                esperado_cents = _cents(valor_original * percentual)
                diferenca = abs(total_cents - esperado_cents)
                assert diferenca <= TOLERANCIA_CONTAS_PRIORITARIAS, (
                    f"{conta} ({acao_label}): diferenca {diferenca} centavos"
                )


# ---------------------------------------------------------------------------
# I3 - Tolerancias e arredondamentos: piso 0,01 e multiplo exato de centavo
# ---------------------------------------------------------------------------

class TestPisoEArredondamento:
    """
    I3a - Nenhum VALOR pode ser 0.00 (piso de 0,01 obrigatorio).
    I3b - Nenhum VALOR pode ser negativo.
    I3c - Todo VALOR deve ser multiplo exato de 0,01 (2 casas decimais).
    """

    def test_sem_valores_zero(self, planilha_dois_pares):
        df = _converter(planilha_dois_pares)
        zeros = (df["VALOR"] == 0).sum()
        assert zeros == 0, f"Encontrados {zeros} valores 0.00 na saida"

    def test_sem_valores_negativos(self, planilha_dois_pares):
        df = _converter(planilha_dois_pares)
        negativos = (df["VALOR"] < 0).sum()
        assert negativos == 0, f"Encontrados {negativos} valores negativos na saida"

    def test_piso_com_percentual_fracionado(self, planilha_arredondamento):
        """Percentual 1/3 sobre 1.00 gera 0.33; nenhum valor pode ser < 0.01."""
        df = _converter(planilha_arredondamento, percentual=1 / 3)
        abaixo_piso = (df["VALOR"] < 0.01).sum()
        assert abaixo_piso == 0, f"Encontrados {abaixo_piso} valores abaixo de 0,01"

    def test_valores_multiplos_de_centavo(self, planilha_dois_pares):
        """Cada VALOR deve ser multiplo exato de 0,01 (sem sub-centavos)."""
        df = _converter(planilha_dois_pares)
        for val in df["VALOR"]:
            residuo = abs(val - round(val * 100) / 100)
            assert residuo < 1e-9, f"VALOR {val} nao e multiplo exato de 0,01"
