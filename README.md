# px-agents

Argos PX: Digital Worker de Governança de Ociosidade da BRQ PX.

Este repositório contém apenas o deployment do **Argos PX sobre Hermes Agent** e os MCPs HTTP read-only para a Sprint 1.

## Objetivo

O Argos PX apoia Delivery Managers (DMs) na rotina semanal de gestão de ociosidade da Operations PX.

O agente deve ajudar a identificar:

- profissionais ociosos;
- profissionais super-alocados;
- inconsistências entre planejamento financeiro e alocação real;
- candidatos a ajuste antes da reunião semanal;
- pendências e riscos que precisam de decisão humana.

Regra central: o agente **sugere**, o humano **decide**, e qualquer execução real precisa de aprovação explícita e log auditável.

## Pré-Requisitos

- Docker
- Docker Compose
- Connection string read-only do `Portal_BAU` staging, caso queira testar os MCPs contra banco real

## Configuração

Crie o arquivo local de ambiente:

```bash
cp .env.example .env
```

Edite `.env` com os valores reais do ambiente local:

```bash
HERMES_UID=10000
HERMES_GID=10000
API_SERVER_KEY=change-me-local-dev
API_SERVER_MODEL_NAME=brqpx-hermes
PORTAL_BAU_STAGING_CONNECTION_STRING=
```

Não commite `.env`. O arquivo está ignorado pelo Git.

Credenciais de modelo do Hermes devem ficar em `hermes/.env`, criado a partir de `hermes/.env.example`.

## Subir Argos PX

```bash
docker compose up -d --build
```

Ver status:

```bash
docker compose ps
```

Ver logs:

```bash
docker compose logs -f gateway
docker compose logs -f mcp-planejamento-financeiro
docker compose logs -f mcp-profissionais
```

Endpoints locais:

```text
Dashboard Hermes:       http://localhost:9119
OpenAI-compatible API:  http://localhost:8642/v1
Teams webhook local:    http://localhost:3978/api/messages
```

## Hermes

O deployment usa a imagem oficial da Nous Research como base:

```text
nousresearch/hermes-agent:latest
```

Arquivos principais:

```text
hermes/SOUL.md       # identidade/persona do Argos PX
hermes/config.yaml   # configuração Hermes + MCP servers
compose.yaml         # gateway Hermes + MCPs
Dockerfile           # imagem Hermes com dependências de Teams
```

## MCPs Do Portal_BAU

O MVP da Sprint 1 usa dois MCPs HTTP, ambos read-only:

```text
mcp-planejamento-financeiro
mcp-profissionais
```

Eles acessam o banco `Portal_BAU` staging via SQL Server, usando `pyodbc` e Microsoft ODBC Driver 18.

Configure a connection string em `.env`:

```bash
PORTAL_BAU_STAGING_CONNECTION_STRING=
```

O Hermes descobre esses MCPs no startup através de `hermes/config.yaml`:

```yaml
mcp_servers:
  planejamento_financeiro:
    url: http://mcp-planejamento-financeiro:8000/mcp
  profissionais:
    url: http://mcp-profissionais:8000/mcp
```

### MCP Planejamento Financeiro

Responsável por versão, bloqueios, planejamento, competências, alocações e horas planejadas.

Ferramentas iniciais:

```text
pf_healthcheck
pf_get_current_context
pf_check_write_allowed
pf_get_project_planning
pf_get_project_competences
pf_get_allocations_by_project
pf_get_allocation_hours_by_month
pf_detect_overallocation
pf_detect_underallocation
pf_prepare_hours_adjustment
```

`pf_prepare_hours_adjustment` apenas prepara payload. Não escreve no banco.

### MCP Profissionais

Responsável por pessoa, rate, site, centro de custo e alocação RH.

Ferramentas iniciais:

```text
people_healthcheck
people_get_professional
people_get_professional_rate
people_get_professional_site
people_get_professional_cost_center
people_get_project_rh_allocations
people_get_professionals_by_project
people_check_professional_eligible_for_pf
```

## Segurança

- `.env`, tokens, auth local do Hermes, caches, bancos locais e logs estão no `.gitignore`.
- O repositório público deve conter apenas placeholders, nunca segredos reais.
- Os MCPs não expõem ferramenta de SQL livre.
- Os MCPs da Sprint 1 são read-only; escrita real no Portal_BAU fica fora deste MVP.
- Connection string de staging deve usar usuário read-only.

## Estrutura

```text
AGENTS.md
Dockerfile
compose.yaml
hermes/
  SOUL.md
  config.yaml
mcp/
  brqpx_mcp/common/
    db.py
    settings.py
  planejamento_financeiro/server.py
  profissionais/server.py
```

## Comandos Úteis

```bash
# Hermes + MCPs
docker compose up -d --build
docker compose ps
docker compose logs -f gateway

# Entrar no container Hermes
docker compose exec gateway bash

# Recarregar Hermes após alterar SOUL/config
docker compose restart gateway
```
