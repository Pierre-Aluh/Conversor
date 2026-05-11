# -*- coding: utf-8 -*-
"""Excecoes de dominio do conversor."""


class ConversorErro(Exception):
    """Classe base para erros do sistema de conversao."""


class PersistenciaErro(ConversorErro):
    """Erro de leitura/escrita de dados persistidos."""


class CadastroErro(ConversorErro):
    """Erro relacionado a cadastros de consorciadas."""


class CadastroNaoEncontradoErro(CadastroErro):
    """Cadastro solicitado nao existe."""


class ConversaoErro(ConversorErro):
    """Erro durante a conversao contabil."""


class ConfiguracaoErro(ConversorErro):
    """Erro de configuracao/entrada invalida para execucao."""
