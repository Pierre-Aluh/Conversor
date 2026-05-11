from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from erros import CadastroNaoEncontradoErro, PersistenciaErro
from observabilidade import get_logger, log_event


class CadastrosRepository:
    def __init__(self, cadastros_file: Path):
        self.cadastros_file = Path(cadastros_file)
        self.logger = get_logger(__name__)

    def ensure_file_exists(self, bundled_file: Path | None = None) -> None:
        if self.cadastros_file.exists():
            return
        if bundled_file and bundled_file.exists() and bundled_file != self.cadastros_file:
            self.cadastros_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled_file, self.cadastros_file)
            return
        self.write_data(self.default_data())

    def read_data(self) -> dict[str, Any]:
        try:
            with open(self.cadastros_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError as exc:
            log_event(self.logger, 40, "persistencia_arquivo_nao_encontrado", arquivo=self.cadastros_file)
            raise PersistenciaErro("Arquivo de cadastros não encontrado") from exc
        except json.JSONDecodeError as exc:
            log_event(self.logger, 40, "persistencia_json_invalido", arquivo=self.cadastros_file)
            raise PersistenciaErro("Arquivo de cadastros inválido") from exc
        except OSError as exc:
            log_event(self.logger, 40, "persistencia_falha_leitura", arquivo=self.cadastros_file)
            raise PersistenciaErro("Falha ao ler arquivo de cadastros") from exc

    def write_data(self, data: dict[str, Any]) -> None:
        try:
            self.cadastros_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cadastros_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            log_event(self.logger, 40, "persistencia_falha_escrita", arquivo=self.cadastros_file)
            raise PersistenciaErro("Falha ao gravar arquivo de cadastros") from exc

    def list_names(self) -> list[str]:
        data = self.read_data()
        return [c.get("nome", "") for c in data.get("consorciadas", []) if c.get("nome")]

    def find_by_name(self, nome: str) -> dict[str, Any] | None:
        data = self.read_data()
        for cadastro in data.get("consorciadas", []):
            if cadastro.get("nome") == nome:
                return cadastro
        return None

    def add_cadastro(self, cadastro: dict[str, Any]) -> None:
        data = self.read_data()
        consorciadas = data.setdefault("consorciadas", [])
        if any(c.get("nome") == cadastro.get("nome") for c in consorciadas):
            raise ValueError(f"Cadastro '{cadastro.get('nome')}' já existe")
        consorciadas.append(cadastro)
        self.write_data(data)

    def update_cadastro(self, nome: str, updates: dict[str, Any]) -> None:
        data = self.read_data()
        consorciadas = data.setdefault("consorciadas", [])
        for cadastro in consorciadas:
            if cadastro.get("nome") == nome:
                cadastro.update(updates)
                self.write_data(data)
                return
        raise CadastroNaoEncontradoErro(f"Cadastro '{nome}' não encontrado")

    def delete_cadastro(self, nome: str) -> bool:
        data = self.read_data()
        consorciadas = data.setdefault("consorciadas", [])
        antes = len(consorciadas)
        data["consorciadas"] = [c for c in consorciadas if c.get("nome") != nome]
        self.write_data(data)
        return len(data["consorciadas"]) < antes

    @staticmethod
    def default_data() -> dict[str, Any]:
        return {
            "descricao": "Arquivo de cadastros de consorciadas",
            "consorciadas": [
                {
                    "nome": "Exemplo 1 - 50%",
                    "nome_consortio": "Consórcio Exemplo 1",
                    "codigo_consortio": "consorcio_001",
                    "codigo_obra_consortio": "obra_001",
                    "percentual": 50.0,
                    "codigo_empresa": 97,
                    "codigo_obra": 972,
                    "conta_arredondamento": "1.1.01.01.000099",
                    "memorizar_conta": False,
                },
                {
                    "nome": "Exemplo 2 - 52.5%",
                    "nome_consortio": "Consórcio Exemplo 1",
                    "codigo_consortio": "consorcio_001",
                    "codigo_obra_consortio": "obra_001",
                    "percentual": 52.5,
                    "codigo_empresa": 98,
                    "codigo_obra": 973,
                    "conta_arredondamento": "1.1.01.01.000099",
                    "memorizar_conta": False,
                },
            ],
        }
