from pathlib import Path

import pandas as pd
import pytest

from camadas.persistencia import CadastrosRepository
from camadas.servico import ConversorAppService
from erros import ConfiguracaoErro


def _criar_repo_tmp(tmp_path: Path) -> CadastrosRepository:
    arquivo = tmp_path / "cadastros.json"
    repo = CadastrosRepository(arquivo)
    repo.write_data(repo.default_data())
    return repo


class TestPersistenciaCadastros:
    def test_repo_lista_nomes(self, tmp_path):
        repo = _criar_repo_tmp(tmp_path)

        nomes = repo.list_names()

        assert "Exemplo 1 - 50%" in nomes
        assert "Exemplo 2 - 52.5%" in nomes

    def test_repo_add_update_delete(self, tmp_path):
        repo = _criar_repo_tmp(tmp_path)

        repo.add_cadastro(
            {
                "nome": "Novo Cadastro",
                "nome_consortio": "Consórcio Teste",
                "codigo_consortio": "123",
                "codigo_obra_consortio": "1231",
                "percentual": 10.0,
                "codigo_empresa": 1,
                "codigo_obra": 2,
                "conta_repasse_ativo": "",
                "conta_repasse_passivo": "",
                "grupo_excluido": "",
                "conta_arredondamento": "1.1.01.01.000001",
                "memorizar_conta": False,
            }
        )
        repo.update_cadastro("Novo Cadastro", {"percentual": 25.0})
        removido = repo.delete_cadastro("Novo Cadastro")

        assert removido is True
        assert repo.find_by_name("Novo Cadastro") is None


class TestServicoInterface:
    def test_parse_config_valida(self, tmp_path):
        repo = _criar_repo_tmp(tmp_path)
        service = ConversorAppService(repo)

        percentual, empresa, obra, conta = service.parse_config("52.5", "97", "972", "1.1.01.01.000001")

        assert percentual == pytest.approx(0.525)
        assert empresa == 97
        assert obra == 972
        assert conta == "1.1.01.01.000001"

    def test_parse_config_percentual_invalido(self, tmp_path):
        repo = _criar_repo_tmp(tmp_path)
        service = ConversorAppService(repo)

        with pytest.raises(ConfiguracaoErro, match="Percentual inválido"):
            service.parse_config("abc", "97", "972", "1.1.01.01.000001")

    def test_criar_e_memorizar_cadastro(self, tmp_path):
        repo = _criar_repo_tmp(tmp_path)
        service = ConversorAppService(repo)

        service.criar_cadastro(
            {
                "nome": "Cadastro Service",
                "nome_consortio": "Consórcio Service",
                "codigo_consortio": "77",
                "codigo_obra_consortio": "771",
                "percentual": "50",
                "codigo_empresa": "8",
                "codigo_obra": "81",
                "conta_repasse_ativo": "",
                "conta_repasse_passivo": "",
                "grupo_excluido": "",
                "conta_arredondamento": "1.1.01.01.000009",
                "memorizar_conta": False,
            }
        )

        ok = service.memorizar_conta("Cadastro Service", "1.1.01.01.000010", True)
        cadastro = service.obter_cadastro("Cadastro Service")

        assert ok is True
        assert cadastro["conta_arredondamento"] == "1.1.01.01.000010"
        assert cadastro["memorizar_conta"] is True

    def test_executar_conversao_sem_tkinter(self, tmp_path):
        repo = _criar_repo_tmp(tmp_path)

        def fake_conversao(*args, **kwargs):
            print("Grupo para exclusão não encontrado")
            return pd.DataFrame([{"VALOR": 1.23}])

        service = ConversorAppService(repo, conversao_fn=fake_conversao)

        arquivo = tmp_path / "entrada.xlsx"
        arquivo.write_text("dummy", encoding="utf-8")

        resultado = service.executar_conversao(
            str(arquivo),
            0.5,
            97,
            972,
            "1.1.01.01.000001",
            "",
            "",
            "",
        )

        assert len(resultado["resultado"]) == 1
        assert resultado["tem_aviso_grupo"] is True
        assert "Grupo para exclusão não encontrado" in resultado["log_capturado"]
