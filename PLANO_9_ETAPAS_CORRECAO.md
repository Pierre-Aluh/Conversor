# Plano De Correcao Em 9 Etapas

Objetivo: corrigir os 9 pontos severos sem quebrar as regras contabeis e a logica do programa.

Estratégia de seguranca:
- Travar o comportamento atual com testes de caracterizacao antes de refatorar.
- Aplicar mudancas em fatias pequenas com validacao automatizada a cada etapa.
- Manter as assinaturas publicas atuais durante a migracao.

## Etapa 1 - Preservacao Da Versao Atual E Linha De Base
Problema coberto: necessidade de preservar o estado atual antes da correcao.

Status: concluida.

Entregaveis:
- Snapshot local via tag.
- Branch nova de trabalho.
- Registro do hash base para rollback seguro.

Registro validado em 2026-04-28:
- Tag local de snapshot: snapshot-pre-plano-20260428-112848.
- Branch dedicada: versao/plano-correcao-9-etapas.
- Hash base registrado: f2327d323017c3241313e301aa19c06ade31eb83.

Criterio de pronto:
- Existe uma tag local de snapshot.
- Existe branch dedicada para o plano.

## Etapa 2 - Limpeza De Artefatos Versionados
Problema coberto: build, binarios e caches no Git.

Status: concluida.

Entregaveis:
- Remocao de artefatos do controle de versao (mantendo arquivos locais com git rm --cached quando aplicavel).
- Revisao de pastas build, build_pyinstaller, dist, release, installer, __pycache__, entrada e saida.

Registro validado em 2026-04-28:
- Remocao do indice Git executada com git rm --cached nas pastas __pycache__, build, build_pyinstaller, dist, installer, release, entrada e saida.
- Verificacao final: git ls-files "*.exe" "*.pyz" "*.pkg" "*.pyc" "*.xlsx" sem resultados.

Criterio de pronto:
- Nenhum .exe, .pyz, .pkg, .pyc ou planilha operacional permanece versionado.

## Etapa 3 - Higiene De Versionamento Com Gitignore
Problema coberto: ausencia de .gitignore efetivo.

Status: concluida.

Entregaveis:
- Arquivo .gitignore cobrindo Python, PyInstaller, artefatos de distribuicao, dados operacionais e caches.
- Regras de excecao para manter apenas exemplos controlados.

Registro validado em 2026-04-28:
- .gitignore criado cobrindo __pycache__, build, build_pyinstaller, dist, installer, release, entrada e saida.
- Excecoes adicionadas para exemplos controlados em entrada/exemplos e saida/exemplos.
- Verificacao final: git status --short sem reintroduzir pastas operacionais como itens nao rastreados; git check-ignore -v confirmou cobertura para build, dist, entrada, saida e __pycache__.

Criterio de pronto:
- Novos builds nao sujam git status.

## Etapa 4 - Testes Automatizados De Caracterizacao
Problema coberto: teste manual dependente de arquivo local.

Status: concluida.

Entregaveis:
- Migracao do teste atual para pytest.
- Fixtures anonimizadas e pequenas.
- Testes de invariantes:
	- Fechamento D=C por NumSequencia.
	- Respeito as contas prioritarias de configuracao.
	- Tolerancias e arredondamentos esperados.

Registro validado em 2026-04-28:
- Arquivos criados: tests/__init__.py, tests/conftest.py, tests/test_invariantes.py, pytest.ini, requirements-dev.txt.
- 3 classes de teste (9 casos): TestFechamentoDCPorSequencia, TestContasPrioritarias, TestPisoEArredondamento.
- Fixtures anonimizadas: planilha_dois_pares, planilha_arredondamento, planilha_conta_prioritaria (sem dados reais).
- Resultado: 9 passed in 0.95s (python -m pytest tests/ -v).

Criterio de pronto:
- pytest executa local e em CI com resultado reproduzivel.

## Etapa 5 - Desacoplamento Do Nucleo Conversor
Problema coberto: funcao longa e muito acoplada em Conversor.py.

Entregaveis:
- Extracao para modulos internos (entrada, normalizacao, regras, ajuste, saida).
- Manutencao de assinatura publica das funcoes usadas pela UI.
- Refatoracao sem mudanca de regra de negocio.

Criterio de pronto:
- Mesmo input gera output equivalente aos testes golden.

Status: concluida.

Registro validado em 2026-04-28:
- Pacote conversor/ criado com 4 modulos: _entrada.py, _exclusao.py, _ajuste.py, _saida.py.
- Conversor.py reescrito como orquestrador (73 linhas); assinatura publica de gerar_contabilidade_consorciada mantida.
- Bug latente corrigido: sequencias_balanceadas_antes e sequencias_alteradas_por_ajuste inicializados como set() em _ajuste.py.
- Resultado: 9 passed in 0.62s (python -m pytest tests/ -v).

## Etapa 6 - Modularizacao Da Interface Grafica
Problema coberto: app_novo.py monolitico.

Entregaveis:
- Separacao em camadas: UI, servico de aplicacao e persistencia de cadastros.
- Reducao de responsabilidades da classe principal da tela.

Criterio de pronto:
- Fluxos principais da UI continuam funcionando e testes de servico passam sem Tkinter.

Status: concluida.

Registro validado em 2026-04-28:
- Camadas criadas: camadas/persistencia.py (CadastrosRepository) e camadas/servico.py (ConversorAppService).
- app_novo.py adaptado para consumir servico/repository em carga, selecao, criacao, edicao, delecao e memorizacao de cadastros.
- Conversao unitária e processamento em lote passaram a ser delegados para a camada de servico, mantendo fluxos da UI.
- Testes sem Tkinter adicionados: tests/test_servico_interface.py (6 casos).
- Resultado: 15 passed in 0.77s (python -m pytest tests/ -v).

## Etapa 7 - Tratamento De Erros E Observabilidade
Problema coberto: uso amplo de except Exception.

Status: concluida.

Entregaveis:
- Excecoes especificas por contexto.
- Logs estruturados com contexto minimo (arquivo, conta, sequencia, etapa).
- Mensagens para usuario claras, mantendo simplicidade operacional.

Criterio de pronto:
- Falhas relevantes ficam rastreaveis sem expor dado sensivel.

Registro validado em 2026-04-28:
- Excecoes de dominio consolidadas em erros.py (ConfiguracaoErro, ConversaoErro, CadastroErro, PersistenciaErro e derivadas), removendo captura generica por Exception nos fluxos principais.
- Observabilidade estruturada centralizada em observabilidade.py com log_event e sanitizacao de caminho de arquivo para evitar exposicao de path completo.
- Camadas e UI adaptadas para tratamento contextual (camadas/persistencia.py, camadas/servico.py, app_novo.py, Conversor.py), com mensagens claras ao usuario e rastreio por etapa/evento.
- Testes ajustados e ampliados: correção de expectativa para ConfiguracaoErro em tests/test_servico_interface.py e novo teste tests/test_observabilidade.py cobrindo sanitizacao de arquivo.
- Resultado: 16 passed in 0.64s (python -m pytest tests/ -v).

## Etapa 8 - Governanca Minima Para Colaboracao
Problema coberto: falta de README, licenca, CI e convencoes.

Status: concluida.

Entregaveis:
- README com setup rapido, execucao e troubleshooting.
- LICENSE definida.
- Pipeline CI basico (lint + testes).
- CONTRIBUTING com padrao de branch, commit e PR.

Criterio de pronto:
- Colaborador novo consegue rodar projeto e testes em ambiente limpo.

Registro validado em 2026-04-28:
- README.md criado com setup rapido, execucao (GUI/script), comandos de qualidade e troubleshooting.
- LICENSE adicionada (MIT).
- CONTRIBUTING.md criado com padroes de branch, commit e checklist de PR.
- Pipeline de CI criado em .github/workflows/ci.yml com etapas de install, lint (ruff) e testes (pytest).
- Configuracao inicial de lint adicionada em .ruff.toml e ferramenta incluida em requirements-dev.txt.
- Validacao local sem ambiente virtual:
	- python -m ruff check . -> All checks passed
	- python -m pytest tests/ -v -> 16 passed in 0.61s

## Etapa 9 - Dados Sensiveis E Politica De Dependencias
Problemas cobertos: dados reais no repo e pins agressivos em requirements.

Status: concluida.

Entregaveis:
- Substituicao de dados reais por amostras anonimizadas.
- Arquivo de exemplo para cadastros e orientacao de configuracao local.
- Revisao de requirements com faixas de versao realistas e justificadas.

Criterio de pronto:
- Repositorio sem dados reais de dominio.
- Instalacao reproduzivel em ambiente corporativo comum.

Registro validado em 2026-04-28:
- Dados de cadastro anonimizados em cadastros.json e arquivo de exemplo adicionado em cadastros.exemplo.json.
- Suporte a configuracao local implementado em app_novo.py com prioridade para cadastros.local.json e override por CONVERSOR_CADASTROS_FILE.
- Arquivo local excluido do versionamento em .gitignore (cadastros.local.json).
- Referencias nominais de dominio substituidas por exemplos anonimizados em test_piso_001.py e ENCICLOPEDIA_CONVERSOR_CONTABIL.md.
- Politica de dependencias revisada com faixas realistas:
	- requirements.txt: pandas>=2.2,<3.0; openpyxl>=3.1,<4.0; Pillow>=10.3,<12.0
	- requirements-dev.txt: pytest>=7.4,<9.0; ruff>=0.6,<1.0; pyinstaller>=6.7,<7.0
- Orientacao de configuracao local documentada em README.md.
- Validacao local sem ambiente virtual:
	- python -m ruff check . -> All checks passed
	- python -m pytest tests/ -v -> 16 passed in 0.57s

## Ordem Recomendada De Execucao
1. Etapa 2
2. Etapa 3
3. Etapa 4
4. Etapa 7
5. Etapa 5
6. Etapa 6
7. Etapa 8
8. Etapa 9

Observacao: Etapa 1 ja foi realizada antes do inicio do plano.

## Definicao De Nao Regressao
- Mesmo conjunto de entradas de referencia deve manter:
	- fechamento contabil por sequencia;
	- tolerancias globais e prioritarias;
	- colunas e layout de saida esperados;
	- comportamento de exclusoes por grupo e repasses.

Se qualquer criterio falhar, a mudanca nao sobe para a proxima etapa.
