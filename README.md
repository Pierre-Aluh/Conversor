# Conversor Contabil

Aplicacao desktop (Tkinter) para conversao de lancamentos contabeis de consorcios para empresas consorciadas, com regras de fechamento e arredondamento validadas por testes automatizados.

## Requisitos

- Python 3.12+
- Windows (suporte principal atual)

## Setup Rapido

1. Instale dependencias de execucao:

```powershell
python -m pip install -r requirements.txt
```

2. (Opcional) Instale dependencias de desenvolvimento:

```powershell
python -m pip install -r requirements-dev.txt
```

3. Configure cadastros locais (recomendado):

```powershell
Copy-Item cadastros.exemplo.json cadastros.local.json
```

Edite `cadastros.local.json` com seus dados internos. Esse arquivo e ignorado pelo Git.

Opcionalmente, use um caminho customizado:

```powershell
$env:CONVERSOR_CADASTROS_FILE = "C:\\caminho\\seguro\\cadastros.local.json"
```

## Execucao

### Interface grafica

```powershell
python app_novo.py
```

### Conversao por script

```powershell
python Conversor.py
```

## Testes e Qualidade

### Rodar testes

```powershell
python -m pytest tests/ -v
```

### Rodar lint

```powershell
python -m ruff check .
```

## Estrutura de Diretórios

```
Conversor/
├── app_novo.py              # Interface gráfica (Tkinter)
├── Conversor.py             # Orquestrador do fluxo de conversão
├── config.py                # Configurações centrais (contas prioritárias)
├── erros.py                 # Exceções de domínio
├── observabilidade.py       # Logging estruturado
│
├── conversor/               # Módulos de lógica contábil
│   ├── _entrada.py          # Validação e normalização de entrada
│   ├── _exclusao.py         # Aplicação de regras de exclusão
│   ├── _ajuste.py           # Passos de ajuste contábil
│   └── _saida.py            # Validação e formatação de saída
│
├── camadas/                 # Camadas de aplicação
│   ├── servico.py           # Serviço de domínio
│   └── persistencia.py      # Repositório de cadastros
│
├── tests/                   # Testes automatizados
│   ├── test_invariantes.py  # Validação de regras contábeis
│   ├── test_observabilidade.py
│   └── test_servico_interface.py
│
├── docs/                    # Documentação técnica
│   └── REFERENCIA_TECNICA.md  # Especificação completa da conversão
│
├── requirements.txt         # Dependências de execução
├── requirements-dev.txt     # Dependências de desenvolvimento
├── README.md                # Este arquivo
├── LICENSE                  # Licença MIT
├── CONTRIBUTING.md          # Guia de contribuição
└── PLANO_9_ETAPAS_CORRECAO.md  # Plano de correção e evidências
```

## Documentação Técnica

Para detalhes profundos sobre o algoritmo de conversão contábil, regras de arredondamento e estrutura de dados, consulte [docs/REFERENCIA_TECNICA.md](docs/REFERENCIA_TECNICA.md).

## Troubleshooting

- Erro de arquivo nao encontrado:
  - Verifique se o arquivo de entrada existe e se o caminho esta correto.
- Erro de permissao ao salvar:
  - Feche a planilha de saida no Excel e tente novamente.
- Falha por dependencia ausente:
  - Reinstale dependencias com `python -m pip install -r requirements.txt`.
- Cadastros locais nao carregados:
  - Confirme se `cadastros.local.json` existe na pasta do app ou se `CONVERSOR_CADASTROS_FILE` aponta para um JSON valido.
- Testes falhando localmente:
  - Garanta Python 3.12+ e execute `python -m pytest tests/ -v` para ver o detalhe da falha.

## Contribuicao

Veja CONTRIBUTING.md para padroes de branch, commit e pull request.
