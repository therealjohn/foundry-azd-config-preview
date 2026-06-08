# `azure.yaml` reference -- Foundry scenarios

Copy-pasteable snippets for the unified `azure.yaml` shape. Each example
is the minimum YAML that expresses one scenario -- omit anything you don't
need; the extension will fill in sensible defaults.

All examples assume:

```yaml
name: my-foundry-app
metadata:
  template: azd-init@1.21.0

services:
  my-project:
    host: microsoft.foundry
    # ... snippet content here
```

Replace `my-project` with whatever name fits your project.

---

## Contents

* [Project basics](#project-basics)
  * [Single hosted agent (minimum viable)](#single-hosted-agent-minimum-viable)
  * [Multiple agents](#multiple-agents)
  * [Prompt-only agent](#prompt-only-agent)
  * [Mixed: hosted + prompt agents](#mixed-hosted--prompt-agents)
* [Foundry project resource](#foundry-project-resource)
  * [New Foundry project (default)](#new-foundry-project-default)
  * [Reference an existing Foundry project](#reference-an-existing-foundry-project)
* [Model deployments](#model-deployments)
  * [New model deployment](#new-model-deployment)
  * [Reference an existing model deployment](#reference-an-existing-model-deployment)
  * [Multiple deployments](#multiple-deployments)
* [Connections](#connections)
  * [New connection (CustomKeys -- MCP)](#new-connection-customkeys--mcp)
  * [New connection (ApiKey)](#new-connection-apikey)
  * [New connection (ProjectManagedIdentity -- no secret on disk)](#new-connection-projectmanagedidentity--no-secret-on-disk)
  * [Reference an existing connection](#reference-an-existing-connection)
* [Toolboxes](#toolboxes)
  * [New toolbox with built-in tools](#new-toolbox-with-built-in-tools)
  * [Toolbox with connection-backed tools](#toolbox-with-connection-backed-tools)
  * [Reference an existing toolbox](#reference-an-existing-toolbox)
  * [Toolbox shared across multiple agents](#toolbox-shared-across-multiple-agents)
* [Tools on agents](#tools-on-agents)
  * [Tools via toolbox](#tools-via-toolbox)
  * [Tools directly on an agent (no toolbox)](#tools-directly-on-an-agent-no-toolbox)
  * [Mixed: toolbox + direct tools on one agent](#mixed-toolbox--direct-tools-on-one-agent)
* [Skills](#skills)
  * [New skill (inline instructions)](#new-skill-inline-instructions)
  * [New skill (file-backed instructions)](#new-skill-file-backed-instructions)
  * [Reference an existing skill](#reference-an-existing-skill)
  * [Agent using a skill](#agent-using-a-skill)
* [Routines](#routines)
  * [Scheduled routine](#scheduled-routine)
  * [Event-driven routine](#event-driven-routine)
* [Agent code -- container mode (`docker:`)](#agent-code--container-mode-docker)
  * [Local Docker build](#local-docker-build)
  * [Remote build (ACR)](#remote-build-acr)
  * [Pre-built image (no Dockerfile)](#pre-built-image-no-dockerfile)
* [Agent code -- code-deploy mode (`runtime:`)](#agent-code--code-deploy-mode-runtime)
  * [Python -- local zip](#python--local-zip)
  * [Python -- remote build](#python--remote-build)
  * [.NET](#net)
  * [Node.js](#nodejs)
* [Templating & secrets](#templating--secrets)
  * [azd env vars (`${VAR}`)](#azd-env-vars-var)
  * [Foundry server-side resolution (`${{...}}`)](#foundry-server-side-resolution-)
  * [Foundry-managed secrets (no on-disk secret)](#foundry-managed-secrets-no-on-disk-secret)
* [Coexistence with non-Foundry services](#coexistence-with-non-foundry-services)

---

## Project basics

### Single hosted agent (minimum viable)

```yaml
services:
  my-project:
    host: microsoft.foundry
    deployments:
      - name: gpt-4.1-mini
        model: { format: OpenAI, name: gpt-4.1-mini, version: "2025-04-14" }
        sku:   { name: GlobalStandard, capacity: 10 }
    agents:
      my-agent:
        kind: hosted
        project: src/my-agent
        docker: { path: Dockerfile, remoteBuild: true }
        protocols: [{ protocol: responses, version: "1.0.0" }]
        env:
          FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini
```

### Multiple agents

```yaml
services:
  my-project:
    host: microsoft.foundry
    deployments:
      - name: gpt-4.1-mini
        model: { format: OpenAI, name: gpt-4.1-mini, version: "2025-04-14" }
        sku:   { name: GlobalStandard, capacity: 20 }
    agents:
      support-agent:
        kind: hosted
        project: src/support-agent
        runtime: { stack: python, version: "3.12" }
        protocols: [{ protocol: responses, version: "1.0.0" }]
        env: { FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini }
      research-agent:
        kind: hosted
        project: src/research-agent
        docker: { path: Dockerfile, remoteBuild: true }
        protocols: [{ protocol: responses, version: "1.0.0" }]
        env: { FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini }
```

### Prompt-only agent

No `project:`, no `runtime:`, no `docker:`. Pure configuration; the
`microsoft.foundry` target reconciles it as data-plane state.

```yaml
services:
  my-project:
    host: microsoft.foundry
    deployments:
      - name: gpt-4.1-mini
        model: { format: OpenAI, name: gpt-4.1-mini, version: "2025-04-14" }
        sku:   { name: GlobalStandard, capacity: 10 }
    agents:
      triage-agent:
        kind: prompt
        description: Routes customer questions to a specialist
        instructions: |
          You are a triage agent. Route the user's question to one of:
          support-agent, research-agent. Respond with JSON:
          {"route": "<agent-name>", "reason": "..."}
        env:
          FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini
```

### Mixed: hosted + prompt agents

```yaml
services:
  my-project:
    host: microsoft.foundry
    deployments:
      - name: gpt-4.1
        model: { format: OpenAI, name: gpt-4.1, version: "2025-04-14" }
        sku:   { name: GlobalStandard, capacity: 50 }
      - name: gpt-4.1-mini
        model: { format: OpenAI, name: gpt-4.1-mini, version: "2025-04-14" }
        sku:   { name: GlobalStandard, capacity: 20 }
    agents:
      triage-agent:                # prompt, no code
        kind: prompt
        instructions: |
          You are a triage agent...
        env: { FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini }
      support-agent:               # hosted, has code
        kind: hosted
        project: src/support-agent
        runtime: { stack: python, version: "3.12" }
        protocols: [{ protocol: responses, version: "1.0.0" }]
        env: { FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1 }
```

---

## Foundry project resource

### New Foundry project (default)

No `endpoint:` field -- `azd provision` creates a new Foundry project
(via in-memory Bicep, the `azd compose` pattern). Account, resource group,
and project name come from the azd environment.

```yaml
services:
  my-project:
    host: microsoft.foundry
    # ... deployments, agents, etc.
```

### Reference an existing Foundry project

Set `endpoint:` -- its **presence** is the signal that the project
already exists. `azd provision` skips ARM provisioning and connects to
the existing endpoint; `azd deploy` only reconciles data-plane state and
pushes agents.

```yaml
services:
  my-project:
    host: microsoft.foundry
    endpoint: ${FOUNDRY_PROJECT_ENDPOINT}    # set in .azure/<env>/.env
    # ... deployments, agents, etc.
```

---

## Model deployments

### New model deployment

```yaml
deployments:
  - name: gpt-4.1
    model: { format: OpenAI, name: gpt-4.1, version: "2025-04-14" }
    sku:   { name: GlobalStandard, capacity: 50 }
```

### Reference an existing model deployment

The deployment already exists on the Foundry project (created via Portal,
`az`, or another tool). **Don't declare it in `azure.yaml`.** Just
reference it by name where it's used -- the extension verifies presence
at deploy time. Nothing for azd to manage.

```yaml
# No deployments: entry needed.
agents:
  my-agent:
    kind: hosted
    env:
      FOUNDRY_MODEL_DEPLOYMENT_NAME: existing-shared-model
```

### Multiple deployments

Declare every deployment azd should create or upsert. Anything not
declared but referenced by name is treated as existing.

```yaml
deployments:
  - name: gpt-4.1
    model: { format: OpenAI, name: gpt-4.1, version: "2025-04-14" }
    sku:   { name: GlobalStandard, capacity: 50 }
  - name: gpt-4.1-mini
    model: { format: OpenAI, name: gpt-4.1-mini, version: "2025-04-14" }
    sku:   { name: GlobalStandard, capacity: 20 }
  - name: text-embedding-3-small
    model: { format: OpenAI, name: text-embedding-3-small, version: "1" }
    sku:   { name: Standard, capacity: 10 }
# `shared-batch-model` exists on the project (provisioned by another team)
# and is just referenced by name from any agent that needs it -- not declared here.
```

---

## Connections

### New connection (CustomKeys -- MCP)

Useful for arbitrary MCP servers that take a custom header name.

```yaml
connections:
  - name: github-mcp-conn
    category: CustomKeys
    target: https://api.githubcopilot.com/mcp
    authType: CustomKeys
    credentials:
      x-api-key: ${GITHUB_MCP_TOKEN}          # azd env expansion
    metadata:
      type: custom_MCP
```

### New connection (ApiKey)

Simple `Authorization: Bearer <key>` style auth.

```yaml
connections:
  - name: tavily-mcp-conn
    category: ApiKey
    target: https://mcp.tavily.com/mcp
    authType: ApiKey
    credentials:
      key: ${TAVILY_API_KEY}
    metadata:
      type: custom_MCP
```

### New connection (ProjectManagedIdentity -- no secret on disk)

No credentials in `azure.yaml`, no secret in `.env`. The Foundry
project's managed identity authenticates to the target. Best practice
for Azure-to-Azure connections.

```yaml
connections:
  - name: azure-search-conn
    category: CognitiveSearch
    target: https://my-search-svc.search.windows.net
    authType: ProjectManagedIdentity
```

### Reference an existing connection

Connection was created externally (Portal, `az cognitiveservices account
project connection create`, Foundry Toolkit). **Don't declare it in
`azure.yaml`.** Just reference by name from toolboxes or agents -- the
extension verifies presence at deploy.

```yaml
# No connections: entry needed.
toolboxes:
  research-toolbox:
    tools:
      - { type: mcp, connection: shared-mcp-conn }   # references existing connection
```

---

## Toolboxes

### New toolbox with built-in tools

```yaml
toolboxes:
  basic-toolbox:
    tools:
      - { type: web_search }
      - { type: code_interpreter }
      - { type: file_search }
```

### Toolbox with connection-backed tools

```yaml
connections:
  - name: github-mcp-conn
    category: CustomKeys
    target: https://api.githubcopilot.com/mcp
    authType: CustomKeys
    credentials: { x-api-key: ${GITHUB_MCP_TOKEN} }
    metadata: { type: custom_MCP }

toolboxes:
  research-toolbox:
    tools:
      - { type: web_search }
      - { type: mcp,             connection: github-mcp-conn }
      - { type: azure_ai_search, connection: azure-search-conn }
```

### Reference an existing toolbox

Toolbox already exists on the Foundry project (e.g., created via
`azd ai toolbox create` or the Portal). **Don't declare it in
`azure.yaml`.** Reference by name from any agent.

```yaml
# No toolboxes: entry needed.
agents:
  my-agent:
    kind: hosted
    project: src/my-agent
    docker: { path: Dockerfile, remoteBuild: true }
    toolboxes: [shared-toolbox]                  # references existing toolbox
```

### Toolbox shared across multiple agents

One toolbox, multiple consumers -- the problem the old per-agent
`agent.manifest.yaml` could not solve cleanly.

```yaml
toolboxes:
  shared-tools:
    tools:
      - { type: web_search }
      - { type: code_interpreter }

agents:
  support-agent:
    kind: hosted
    project: src/support-agent
    runtime: { stack: python, version: "3.12" }
    toolboxes: [shared-tools]
  research-agent:
    kind: hosted
    project: src/research-agent
    docker: { path: Dockerfile, remoteBuild: true }
    toolboxes: [shared-tools]
```

---

## Tools on agents

### Tools via toolbox

The standard pattern -- declare a named toolbox, then reference it by
name from one or more agents.

```yaml
toolboxes:
  my-toolbox:
    tools:
      - { type: web_search }
      - { type: code_interpreter }
agents:
  my-agent:
    kind: hosted
    project: src/my-agent
    runtime: { stack: python, version: "3.12" }
    toolboxes: [my-toolbox]
```

### Tools directly on an agent (no toolbox)

For one-off, agent-specific tools where a reusable toolbox is overkill.
The agent's `tools:` list takes the same tool entries a toolbox would.

```yaml
agents:
  my-agent:
    kind: hosted
    project: src/my-agent
    runtime: { stack: python, version: "3.12" }
    tools:
      - { type: web_search }
      - { type: mcp, connection: github-mcp-conn }
```

The connection still has to be declared in the parent service's
`connections:` list (or referenced as existing).

### Mixed: toolbox + direct tools on one agent

```yaml
toolboxes:
  shared-tools:
    tools:
      - { type: web_search }
      - { type: code_interpreter }
agents:
  my-agent:
    kind: hosted
    project: src/my-agent
    runtime: { stack: python, version: "3.12" }
    toolboxes: [shared-tools]                    # reusable bundle
    tools:                                       # agent-specific extras
      - { type: file_search }
      - { type: mcp, connection: github-mcp-conn }
```

---

## Skills

### New skill (inline instructions)

Best for short prompts (a paragraph or two).

```yaml
skills:
  classifier:
    description: Classifies user intent into one of 5 categories
    instructions: |
      Read the user message and respond with a single JSON object:
      {"intent": "<one of: billing, technical, sales, feedback, other>"}
```

### New skill (file-backed instructions)

Best for longer prompts. Path is relative to `azure.yaml`. Friendlier to
git diffs and to non-developer prompt authors.

```yaml
skills:
  code-review:
    description: Reviews code for bugs and style issues
    instructions: ./prompts/code-review.md
    tools: [file_search, code_interpreter]
```

### Reference an existing skill

**Don't declare it in `azure.yaml`.** Reference by name from any agent.

```yaml
# No skills: entry needed.
agents:
  my-agent:
    kind: prompt
    skill: shared-skill                          # references existing skill
```

### Agent using a skill

```yaml
skills:
  triage:
    description: Routes questions to specialists
    instructions: ./prompts/triage.md
agents:
  triage-agent:
    kind: prompt
    skill: triage                                # reference by name
    env: { FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini }
```

---

## Routines

### Scheduled routine

Cron-based triggering. The named agent runs on the schedule with the
supplied input.

```yaml
routines:
  nightly-summary:
    description: Summarize overnight tickets at 8am UTC
    trigger:
      type: schedule
      cron: "0 8 * * *"
    agent: summarizer-agent
    input:
      ticket_source: ${TICKET_SOURCE_URL}
```

### Event-driven routine

Webhook-style trigger (shape depends on the Foundry routines spec; this
shape is illustrative).

```yaml
routines:
  on-ticket-created:
    description: Triage every new support ticket as it arrives
    trigger:
      type: webhook
      filter:
        eventType: ticket.created
    agent: triage-agent
    input:
      ticket: ${{event.body}}                  # event payload, Foundry-resolved
```

---

## Agent code -- container mode (`docker:`)

Set when the agent has a `Dockerfile`. Mutually exclusive with `runtime:`.

### Local Docker build

Build happens on the developer's machine via the local Docker daemon.
Fastest for iteration when you have Docker installed.

```yaml
agents:
  my-agent:
    kind: hosted
    project: src/my-agent
    docker:
      path: Dockerfile
      remoteBuild: false                       # default if omitted
    protocols: [{ protocol: responses, version: "1.0.0" }]
```

### Remote build (ACR)

Source is uploaded to Azure Container Registry; ACR builds the image
server-side. Best for CI environments without Docker.

```yaml
agents:
  my-agent:
    kind: hosted
    project: src/my-agent
    docker:
      path: Dockerfile
      remoteBuild: true
    protocols: [{ protocol: responses, version: "1.0.0" }]
```

### Pre-built image (no Dockerfile)

Skip the build entirely; deploy an image already in a registry. No
`docker:` block, no `project:`, no `runtime:` -- just `image:`.

```yaml
agents:
  my-agent:
    kind: hosted
    image: myregistry.azurecr.io/my-agent:v1.2.3
    protocols: [{ protocol: responses, version: "1.0.0" }]
```

---

## Agent code -- code-deploy mode (`runtime:`)

Set when there is no Dockerfile -- Foundry schedules the code on a
managed runtime base image. Mutually exclusive with `docker:`.

### Python -- local zip

azd zips the project directory locally and uploads to Foundry.

```yaml
agents:
  my-agent:
    kind: hosted
    project: src/my-agent
    runtime:
      stack: python
      version: "3.12"
    startupCommand: python main.py
    protocols: [{ protocol: responses, version: "1.0.0" }]
```

### Python -- remote build

Source uploaded; dependencies installed server-side. Useful when local
Python isn't available or wheels differ across platforms.

```yaml
agents:
  my-agent:
    kind: hosted
    project: src/my-agent
    runtime:
      stack: python
      version: "3.12"
      remoteBuild: true
    startupCommand: python main.py
    protocols: [{ protocol: responses, version: "1.0.0" }]
```

### .NET

```yaml
agents:
  my-agent:
    kind: hosted
    project: src/my-agent
    runtime:
      stack: dotnet
      version: "8.0"
    startupCommand: dotnet MyAgent.dll
    protocols: [{ protocol: responses, version: "1.0.0" }]
```

### Node.js

```yaml
agents:
  my-agent:
    kind: hosted
    project: src/my-agent
    runtime:
      stack: node
      version: "20"
    startupCommand: node server.js
    protocols: [{ protocol: responses, version: "1.0.0" }]
```

---

## Templating & secrets

### azd env vars (`${VAR}`)

Resolved by azd at deploy time from `.azure/<env>/.env`. Use for any
value that varies by environment.

```yaml
connections:
  - name: my-conn
    category: ApiKey
    target: ${MY_SERVICE_ENDPOINT}            # endpoint from azd env
    authType: ApiKey
    credentials:
      key: ${MY_SERVICE_API_KEY}              # secret from azd env
```

### Foundry server-side resolution (`${{...}}`)

azd does **not** expand `${{...}}`. The string is passed verbatim to
Foundry, which resolves it server-side at runtime. Use for values that
should be injected into the running agent process without ever touching
the developer's disk -- e.g., a credential stored in a connection.

```yaml
agents:
  my-agent:
    kind: hosted
    project: src/my-agent
    runtime: { stack: python, version: "3.12" }
    env:
      # Foundry reads the live credential from the named connection at
      # runtime and injects it as GITHUB_MCP_TOKEN inside the agent process.
      GITHUB_MCP_TOKEN: ${{connections.github-mcp-conn.credentials.x-api-key}}
```

### Foundry-managed secrets (no on-disk secret)

When the connection was created externally (e.g., via `az` CLI or the
Portal), **don't declare it in `azure.yaml`** -- just reference it from
the consuming agent's env via `${{...}}`. Foundry resolves the credential
server-side at runtime. The developer never sees or stores the secret.

```yaml
# No connections: entry needed -- github-mcp-conn exists on the Foundry project.
agents:
  my-agent:
    kind: hosted
    project: src/my-agent
    runtime: { stack: python, version: "3.12" }
    env:
      GITHUB_MCP_TOKEN: ${{connections.github-mcp-conn.credentials.x-api-key}}
```

---

## Coexistence with non-Foundry services

Foundry projects sit alongside any other azd service kind in the same
`services:`. Use `uses:` to order non-Foundry consumers after the Foundry
project so their env vars point at real endpoints.

```yaml
services:
  my-project:
    host: microsoft.foundry
    deployments: [ ... ]
    agents:
      api-agent:
        kind: hosted
        project: src/api-agent
        docker: { path: Dockerfile, remoteBuild: true }
        protocols: [{ protocol: responses, version: "1.0.0" }]

  webapp:
    project: src/webapp
    host: containerapp
    language: js
    docker: { path: Dockerfile, remoteBuild: true }
    uses: [my-project]                         # deploy after Foundry project
    env:
      FOUNDRY_PROJECT_ENDPOINT: ${FOUNDRY_PROJECT_ENDPOINT}
      AGENT_NAME: api-agent
```
