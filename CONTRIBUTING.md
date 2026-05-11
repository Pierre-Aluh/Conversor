# Contribuindo com o Conversor Contabil

## Fluxo de Branch

- Base principal: master
- Prefixos recomendados:
  - feat/: novas funcionalidades
  - fix/: correcoes
  - chore/: manutencao sem impacto funcional
  - docs/: documentacao
  - test/: testes

Exemplo:

```text
fix/etapa-8-ci-lint
```

## Padrao de Commit

Use commits pequenos e objetivos no formato:

```text
tipo(escopo): descricao curta
```

Exemplos:

```text
fix(servico): tratar configuracao invalida com ConfiguracaoErro
docs(readme): adicionar setup e troubleshooting
test(observabilidade): validar sanitizacao de caminho em logs
```

## Pull Request

Checklist minimo para abrir PR:

- Branch atualizada com a base master
- Lint passando localmente (`ruff check .`)
- Testes passando localmente (`python -m pytest tests/ -v`)
- Descricao clara do problema e da solucao
- Evidencia de validacao (saida de teste/lint)
- Sem artefatos de build versionados

## Convencoes de Codigo

- Preserve assinaturas publicas existentes quando possivel.
- Evite alterar regra contabil sem teste cobrindo o comportamento.
- Prefira mudancas pequenas e validaveis em etapas.

## Report de Bugs

Ao abrir issue, inclua:

- Passos para reproduzir
- Comportamento esperado
- Comportamento observado
- Trecho de log/erro relevante
- Versao do Python
