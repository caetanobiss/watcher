# 🛡️ Watcher - Analisador de Impacto Cruzado Multi-Engine

**Watcher** é uma ferramenta de análise estática e verificação de impactos cruzados desenvolvida para monorepos Rails contendo dezenas de motores (*engines*) e aplicações *frontend*.

Ela resolve um dos maiores problemas de arquiteturas distribuídas/monorepos em Rails: **descobrir e prever todos os efeitos colaterais que alterações realizadas em um módulo (ex: `stock`) provocam em outros módulos do sistema (ex: `fiscal`, `financial`, `acquisition`, `industry`), antes mesmo de rodar os testes ou abrir o Pull Request.**

---

## 🎯 O Problema Resolvido

Em ecossistemas Rails compostos por múltiplas engines (ex: 46 módulos), alterações em um model, serviço ou builder de um módulo (como a model `Stock::Batch` ou o builder `Stock::ItemBuilder` no módulo **Stock**) frequentemente causam **quebras silenciosas em outros módulos** (como ao emitir uma nota fiscal no módulo **Fiscal**, ou ao gerar uma ordem no **Industry**).

O **Watcher**:
1. Lê o `git diff` atual do módulo selecionado (ou compara branches).
2. Identifica automaticamente todas as entidades afetadas (Models, Services, Builders, Queries, Concerns, Métodos, Associações ActiveRecord, Campos DB/Foreign Keys, Tipos e Fragments GraphQL).
3. Executa uma varredura de altíssima velocidade por todo o monorepo (sub-segundo para 46 módulos).
4. Relata exatamente quais arquivos, linhas e métodos de **outros módulos** serão impactados, classificando o nível de risco.

---

## 🏗️ Arquitetura e Como Funciona

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │                        Auriga Watcher Architecture                      │
 └────────────────────────────────────────────────────────────────────────┘
                                     │
        ┌────────────────────────────┴───────────────────────────┐
        ▼                                                        ▼
 ┌───────────────────────────────┐              ┌───────────────────────────────┐
 │     Web Dashboard (UI)        │              │       Interface CLI           │
 │  (Dark Mode / Glassmorphism)  │              │  (python watcher.py analyze)  │
 └──────────────┬────────────────┘              └──────────────┬────────────────┘
                │                                              │
                └──────────────────────┬───────────────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │    Fast API / Web Server      │
                       │      (Python Stdlib HTTP)     │
                       └──────────────┬────────────────┘
                                      │
        ┌─────────────────────────────┴─────────────────────────────┐
        ▼                                                           ▼
 ┌───────────────────────────────┐                 ┌───────────────────────────────┐
 │    1. Git Diff Extractor      │                 │     2. Entity AST Parser      │
 │ Extrai linhas alteradas, diff │                 │ Identifica Models, Services,  │
 │  working/staged/branch/commit │                 │ Builders, Queries, GraphQL... │
 └──────────────┬────────────────┘                 └──────────────┬────────────────┘
                │                                                 │
                └──────────────────────┬──────────────────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │    3. Cross-Module Impact     │
                       │         Tracer Engine         │
                       │    (Ripgrep + Pattern Match)  │
                       └──────────────┬────────────────┘
                                      │
                                      ▼
                       ┌───────────────────────────────┐
                       │    4. Risk & Severity Engine  │
                       │ (High / Medium / Low Severity)│
                       └───────────────────────────────┘
```

---

## 💻 Requisitos do Sistema

- **Python**: 3.10 ou superior (*Zero dependências pip externas necessárias! Usa apenas a biblioteca padrão do Python*).
- **Ripgrep (`rg`)**: Recomendado para buscas regex de ultra-alta performance (*possuindo fallback nativo em Python*).
- **Git**: Repositórios git inicializados nos módulos.

---

## 🛠️ Instalação Automática

O Watcher inclui um assistente interativo em Bash para verificar e instalar todas as dependências do sistema e criar o atalho global `watcher`:

```bash
./install.sh
```

*(Você também pode passar `-y` para confirmar automaticamente todas as etapas: `./install.sh -y`)*

---

## 🚀 Como Usar

A ferramenta oferece duas formas de uso: **Interface Web (Dashboard)** e **Interface CLI (Linha de Comando)**.

---

### 🌐 1. Interface Web Dashboard

Inicie o servidor web na pasta do `watcher`:

```bash
python3 watcher.py server --port 3019
```

Abra o navegador no endereço: **`http://localhost:3019`**

#### Recursos do Dashboard:
- **Seletor de Engine**: Lista todas as 46 engines com indicador visual de status Git (alterações não commitadas).
- **Modos de Diff Git**:
  - `Uncommitted Changes (Working Tree)`: Alterações atuais na pasta de trabalho.
  - `Staged Changes`: Alterações adicionadas na staging area do Git (`git add`).
  - `Branch vs Master`: Diferenças entre a branch atual e a `master`.
  - `Last Commit`: Alterações do último commit (`HEAD~1`).
- **Grafo Visual de Impacto Cruzado**: Matriz interativa que conecta a engine alterada com todas as engines destino impactadas.
- **Tabela de Impactos**: Filtrável por módulo destino, nível de severidade e palavra-chave, com exibições de snippets de código e linha.
- **Exportar Relatório Markdown**: Gera com 1 clique o relatório formatado para colar em PRs do GitHub/Bitbucket.

---

### 💻 2. Interface CLI (Linha de Comando)

#### Listar todas as engines e status do Git:
```bash
python3 watcher.py engines
```

#### Analisar impactos da engine `stock` (modo Working Tree):
```bash
python3 watcher.py analyze --engine stock
```

#### Analisar impactos com saída em formato Markdown (para CI/CD ou relatórios):
```bash
python3 watcher.py analyze --engine stock --target staged --format markdown
```

#### Analisar impactos com saída em JSON estruturado:
```bash
python3 watcher.py analyze --engine stock --format json
```

---

## 🔴 Classificação de Risco e Severidade

| Nível | Cor | Critério de Classificação |
| :--- | :--- | :--- |
| **HIGH** | 🔴 Red | Entidades deletadas ou renomeadas, métodos alterados/removidos, chamadas diretas a serviços transacionais ou builders (ex: `Fiscal::InvoiceService` chamando builder alterado). |
| **MEDIUM** | 🟡 Yellow | Referências a modelos ActiveRecord, associações (`has_many`, `belongs_to`), tipos e queries GraphQL, componentes frontend afins. |
| **LOW** | 🟢 Green | Arquivos de teste RSpec (`spec/**/*_spec.rb`), documentações, comentários ou utilitários gerais. |

---

## 🔌 API REST (Endpoints)

O servidor do Watcher expõe endpoints HTTP nativos:

### `GET /api/engines`
Retorna a lista de todas as engines/módulos do repositório, tipo de aplicação e estado do Git.

### `GET /api/diff?engine=stock&target=working`
Retorna o diff estruturado e linhas alteradas da engine informada.

### `POST /api/analyze`
Executa o fluxo completo de análise de impacto.
### `POST /api/run-tests`
Executa os testes RSpec em paralelo (multithread) para as engines solicitadas.
- **Body JSON**:
```json
{
  "engines": [
    { "engine": "stock" },
    { "engine": "fiscal" }
  ]
}
```

---

## 📁 Estrutura de Arquivos do Projeto

```
watcher/
├── README.md                 # Documentação completa do sistema
├── watcher.py                # Ponto de entrada CLI e servidor
└── src/
    ├── __init__.py
    ├── engine_scanner.py     # Descoberta de módulos e status Git
    ├── git_diff_extractor.py # Leitor e parser de Git diffs
    ├── entity_parser.py      # Parser de entidades Ruby e GraphQL
    ├── impact_tracer.py      # Motor de busca cruzada com Ripgrep
    ├── risk_evaluator.py     # Motor de cálculo de severidade e risco
    ├── server.py             # Servidor HTTP REST API nativo
    └── ui/
        └── index.html        # Dashboard Web moderno (HTML/CSS/JS)
```

---

## 📝 Exemplo de Relatório Gerado (Markdown)

```markdown
# 🛡️ Auriga Watcher - Impact Analysis Report

- **Source Engine:** `stock`
- **Diff Target:** `working`
- **Overall Risk Rating:** **HIGH**
- **Entities Changed:** 3
- **Total Impacted Files:** 59 across 9 modules

## 📊 Impact Summary by Target Module

| Target Module | Impacted Files | Total Matches | Severity |
| :--- | :--- | :--- | :--- |
| **fiscal** | 59 | 167 | HIGH |
| **acquisition** | 26 | 82 | HIGH |
| **industry** | 21 | 48 | MEDIUM |
| **financial** | 18 | 35 | MEDIUM |

## 🔍 Top High & Medium Risk Impacted Files

### `[fiscal]` app/services/fiscal/invoice_service.rb
- **L45** (HIGH): `Stock::Batch` in `Stock::BatchBuilder.call(params)`
```
