# `azure.yaml` reference -- Foundry scenarios

Copy-pasteable snippets for the unified `azure.yaml` shape. Each example
is the minimum YAML that expresses one scenario -- omit anything you don't
need; the extension will fill in sensible defaults.

Field shapes (`deployments`, `connections`, `toolboxes`, `container.resources`,
etc.) match the existing
[`azure.ai.agent.json`](https://github.com/Azure/azure-dev/blob/main/cli/azd/extensions/azure.ai.agents/schemas/azure.ai.agent.json)
schema the agents extension already publishes. Collections are arrays of
objects with a `name:` field. Nested objects use multi-line YAML, not
inline `{}` form.

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

* [Complete example: single agent, all new resources](#complete-example-single-agent-all-new-resources)
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
* [External file references (`$ref`)](#external-file-references-ref)
  * [Agent from a YAML file](#agent-from-a-yaml-file)
  * [Toolbox from a JSON file](#toolbox-from-a-json-file)
  * [Other resource types](#other-resource-types)
  * [Absolute vs. relative paths](#absolute-vs-relative-paths)
  * [Mixing inline fields with `$ref`](#mixing-inline-fields-with-ref)
* [Coexistence with non-Foundry services](#coexistence-with-non-foundry-services)

---

## Complete example: single agent, all new resources

A full `azure.yaml` for a one-agent project where azd manages everything --
new Foundry project (no `endpoint:`), new model deployment, new project
connection, new toolbox, new skill, one hosted agent. Drop it into a repo
as a starting point; trim any section you don't need.

This branch splits the project across **one service per extension** instead of
bundling everything under a single `host: microsoft.foundry` entry. The project
and its model deployments live in an `azure.ai.projects` service; connections,
toolboxes, and skills each get their own service (`azure.ai.connections`,
`azure.ai.toolboxes`, `azure.ai.skills`); and **each agent is its own
`azure.ai.agents` service** -- one per agent, the way per-agent services work
today. Services are wired with `uses:` for ordering, and resources still
reference each other by name across service boundaries. The rest of this
document uses the bundled `host: microsoft.foundry` shape; this example is the
per-extension alternative.

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/Azure/azure-dev/refs/heads/main/schemas/v1.0/azure.yaml.json

name: my-foundry-agent
metadata:
  template: azd-init@1.21.0

services:
  # The Foundry project itself + its model deployments.
  # No `endpoint:` -- azd provisions a new Foundry project.
  project:
    host: azure.ai.projects
    deployments:
      - model:
          format: OpenAI
          name: gpt-4.1-mini
          version: "2025-04-14"
        name: gpt-4.1-mini
        sku:
          capacity: 10
          name: GlobalStandard

  # Project connections.
  connections:
    host: azure.ai.connections
    uses:
      - project
    connections:
      - name: github-mcp-conn
        category: CustomKeys
        target: https://api.githubcopilot.com/mcp
        authType: CustomKeys
        credentials:
          x-api-key: ${GITHUB_MCP_TOKEN}     # azd resolves from .azure/<env>/.env
        metadata:
          type: custom_MCP

  # Toolboxes (the mcp tool binds to github-mcp-conn by name).
  toolboxes:
    host: azure.ai.toolboxes
    uses:
      - project
      - connections
    toolboxes:
      - name: my-toolbox
        tools:
          - type: web_search
          - type: code_interpreter
          - type: mcp
            connection: github-mcp-conn

  # Skills.
  skills:
    host: azure.ai.skills
    uses:
      - project
    skills:
      - name: code-review
        description: Reviews code for bugs and style issues
        instructions: ./prompts/code-review.md
        tools: [file_search, code_interpreter]

  # One service per agent (host: azure.ai.agents). Add another such
  # service per additional agent -- agents are never bundled into one entry.
  my-agent:
    host: azure.ai.agents
    uses:
      - project
      - connections
      - toolboxes
      - skills
    kind: hosted
    description: General-purpose assistant with web, code, and GitHub MCP tools.
    project: src/my-agent              # source path -- not the "project" service above
    docker:
      path: Dockerfile
      remoteBuild: true
    protocols:
      - protocol: responses
        version: "1.0.0"
    startupCommand: python main.py
    toolboxes: [my-toolbox]
    skill: code-review
    env:
      FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini
    container:
      resources:
        cpu: "0.5"
        memory: 1Gi
```

The accompanying file layout `azd ai agent init` would produce:

```
.
├── azure.yaml
├── .env.example                # placeholders for GITHUB_MCP_TOKEN, FOUNDRY_PROJECT_ENDPOINT, etc.
├── .gitignore
├── prompts/
│   └── code-review.md          # backs the code-review skill
└── src/
    └── my-agent/
        ├── main.py
        ├── requirements.txt
        ├── Dockerfile
        ├── .azdignore
        └── .dockerignore
```

End-to-end lifecycle (azd walks the services in `uses:` order:
`project` -> `connections` -> `toolboxes` / `skills` -> `my-agent`):

| Command | Effect |
|---|---|
| `azd provision` | The `project` service creates the Foundry project (ARM via in-memory Bicep) and the `gpt-4.1-mini` model deployment. |
| `azd deploy`    | Runs each service target in `uses:` order: the `connections`, `toolboxes`, and `skills` services reconcile `github-mcp-conn`, `my-toolbox`, and `code-review` via Foundry APIs; then the `my-agent` service builds + pushes its container via ACR and posts `createAgentVersion`. |
| `azd up`        | Both, in order. |
| `azd down`      | Destroys the Foundry project (takes the deployment, connection, toolbox, skill, and agent definition with it). |

The rest of this document covers the same primitives in isolation, plus
variations (multiple agents, prompt-only agents, reference-existing
patterns, other deploy modes, language stacks, etc.).

---

## Project basics

### Single hosted agent (minimum viable)

```yaml
services:
  my-project:
    host: microsoft.foundry
    deployments:
      - model:
          format: OpenAI
          name: gpt-4.1-mini
          version: "2025-04-14"
        name: gpt-4.1-mini
        sku:
          capacity: 10
          name: GlobalStandard
    agents:
      - name: my-agent
        kind: hosted
        project: src/my-agent
        docker:
          path: Dockerfile
          remoteBuild: true
        protocols:
          - protocol: responses
            version: "1.0.0"
        env:
          FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini
```

### Multiple agents

```yaml
services:
  my-project:
    host: microsoft.foundry
    deployments:
      - model:
          format: OpenAI
          name: gpt-4.1-mini
          version: "2025-04-14"
        name: gpt-4.1-mini
        sku:
          capacity: 20
          name: GlobalStandard
    agents:
      - name: support-agent
        kind: hosted
        project: src/support-agent
        runtime:
          stack: python
          version: "3.12"
        protocols:
          - protocol: responses
            version: "1.0.0"
        env:
          FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini
      - name: research-agent
        kind: hosted
        project: src/research-agent
        docker:
          path: Dockerfile
          remoteBuild: true
        protocols:
          - protocol: responses
            version: "1.0.0"
        env:
          FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini
```

### Prompt-only agent

No `project:`, no `runtime:`, no `docker:`. Pure configuration; the
`microsoft.foundry` target reconciles it as data-plane state.

```yaml
services:
  my-project:
    host: microsoft.foundry
    deployments:
      - model:
          format: OpenAI
          name: gpt-4.1-mini
          version: "2025-04-14"
        name: gpt-4.1-mini
        sku:
          capacity: 10
          name: GlobalStandard
    agents:
      - name: triage-agent
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
      - model:
          format: OpenAI
          name: gpt-4.1
          version: "2025-04-14"
        name: gpt-4.1
        sku:
          capacity: 50
          name: GlobalStandard
      - model:
          format: OpenAI
          name: gpt-4.1-mini
          version: "2025-04-14"
        name: gpt-4.1-mini
        sku:
          capacity: 20
          name: GlobalStandard
    agents:
      - name: triage-agent                # prompt, no code
        kind: prompt
        instructions: |
          You are a triage agent...
        env:
          FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini
      - name: support-agent               # hosted, has code
        kind: hosted
        project: src/support-agent
        runtime:
          stack: python
          version: "3.12"
        protocols:
          - protocol: responses
            version: "1.0.0"
        env:
          FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1
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
  - model:
      format: OpenAI
      name: gpt-4.1
      version: "2025-04-14"
    name: gpt-4.1
    sku:
      capacity: 50
      name: GlobalStandard
```

### Reference an existing model deployment

The deployment already exists on the Foundry project (created via Portal,
`az`, or another tool). **Don't declare it in `azure.yaml`.** Just
reference it by name where it's used -- the extension verifies presence
at deploy time. Nothing for azd to manage.

```yaml
# No deployments: entry needed.
agents:
  - name: my-agent
    kind: hosted
    env:
      FOUNDRY_MODEL_DEPLOYMENT_NAME: existing-shared-model
```

### Multiple deployments

Declare every deployment azd should create or upsert. Anything not
declared but referenced by name is treated as existing.

```yaml
deployments:
  - model:
      format: OpenAI
      name: gpt-4.1
      version: "2025-04-14"
    name: gpt-4.1
    sku:
      capacity: 50
      name: GlobalStandard
  - model:
      format: OpenAI
      name: gpt-4.1-mini
      version: "2025-04-14"
    name: gpt-4.1-mini
    sku:
      capacity: 20
      name: GlobalStandard
  - model:
      format: OpenAI
      name: text-embedding-3-small
      version: "1"
    name: text-embedding-3-small
    sku:
      capacity: 10
      name: Standard
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
  - name: research-toolbox
    tools:
      - type: mcp
        connection: shared-mcp-conn   # references existing connection
```

---

## Toolboxes

### New toolbox with built-in tools

```yaml
toolboxes:
  - name: basic-toolbox
    tools:
      - type: web_search
      - type: code_interpreter
      - type: file_search
```

### Toolbox with connection-backed tools

```yaml
connections:
  - name: github-mcp-conn
    category: CustomKeys
    target: https://api.githubcopilot.com/mcp
    authType: CustomKeys
    credentials:
      x-api-key: ${GITHUB_MCP_TOKEN}
    metadata:
      type: custom_MCP

toolboxes:
  - name: research-toolbox
    tools:
      - type: web_search
      - type: mcp
        connection: github-mcp-conn
      - type: azure_ai_search
        connection: azure-search-conn
```

### Reference an existing toolbox

Toolbox already exists on the Foundry project (e.g., created via
`azd ai toolbox create` or the Portal). **Don't declare it in
`azure.yaml`.** Reference by name from any agent.

```yaml
# No toolboxes: entry needed.
agents:
  - name: my-agent
    kind: hosted
    project: src/my-agent
    docker:
      path: Dockerfile
      remoteBuild: true
    toolboxes: [shared-toolbox]                  # references existing toolbox
```

### Toolbox shared across multiple agents

One toolbox, multiple consumers -- the problem the old per-agent
`agent.manifest.yaml` could not solve cleanly.

```yaml
toolboxes:
  - name: shared-tools
    tools:
      - type: web_search
      - type: code_interpreter

agents:
  - name: support-agent
    kind: hosted
    project: src/support-agent
    runtime:
      stack: python
      version: "3.12"
    toolboxes: [shared-tools]
  - name: research-agent
    kind: hosted
    project: src/research-agent
    docker:
      path: Dockerfile
      remoteBuild: true
    toolboxes: [shared-tools]
```

---

## Tools on agents

### Tools via toolbox

The standard pattern -- declare a named toolbox, then reference it by
name from one or more agents.

```yaml
toolboxes:
  - name: my-toolbox
    tools:
      - type: web_search
      - type: code_interpreter
agents:
  - name: my-agent
    kind: hosted
    project: src/my-agent
    runtime:
      stack: python
      version: "3.12"
    toolboxes: [my-toolbox]
```

### Tools directly on an agent (no toolbox)

For one-off, agent-specific tools where a reusable toolbox is overkill.
The agent's `tools:` list takes the same tool entries a toolbox would.

```yaml
agents:
  - name: my-agent
    kind: hosted
    project: src/my-agent
    runtime:
      stack: python
      version: "3.12"
    tools:
      - type: web_search
      - type: mcp
        connection: github-mcp-conn
```

The connection still has to be declared in the parent service's
`connections:` list (or referenced as existing).

### Mixed: toolbox + direct tools on one agent

```yaml
toolboxes:
  - name: shared-tools
    tools:
      - type: web_search
      - type: code_interpreter
agents:
  - name: my-agent
    kind: hosted
    project: src/my-agent
    runtime:
      stack: python
      version: "3.12"
    toolboxes: [shared-tools]                    # reusable bundle
    tools:                                       # agent-specific extras
      - type: file_search
      - type: mcp
        connection: github-mcp-conn
```

---

## Skills

### New skill (inline instructions)

Best for short prompts (a paragraph or two).

```yaml
skills:
  - name: classifier
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
  - name: code-review
    description: Reviews code for bugs and style issues
    instructions: ./prompts/code-review.md
    tools: [file_search, code_interpreter]
```

### Reference an existing skill

**Don't declare it in `azure.yaml`.** Reference by name from any agent.

```yaml
# No skills: entry needed.
agents:
  - name: my-agent
    kind: prompt
    skill: shared-skill                          # references existing skill
```

### Agent using a skill

```yaml
skills:
  - name: triage
    description: Routes questions to specialists
    instructions: ./prompts/triage.md
agents:
  - name: triage-agent
    kind: prompt
    skill: triage                                # reference by name
    env:
      FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini
```

---

## Routines

### Scheduled routine

Cron-based triggering. The named agent runs on the schedule with the
supplied input.

```yaml
routines:
  - name: nightly-summary
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
  - name: on-ticket-created
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
  - name: my-agent
    kind: hosted
    project: src/my-agent
    docker:
      path: Dockerfile
      remoteBuild: false                       # default if omitted
    protocols:
      - protocol: responses
        version: "1.0.0"
```

### Remote build (ACR)

Source is uploaded to Azure Container Registry; ACR builds the image
server-side. Best for CI environments without Docker.

```yaml
agents:
  - name: my-agent
    kind: hosted
    project: src/my-agent
    docker:
      path: Dockerfile
      remoteBuild: true
    protocols:
      - protocol: responses
        version: "1.0.0"
```

### Pre-built image (no Dockerfile)

Skip the build entirely; deploy an image already in a registry. No
`docker:` block, no `project:`, no `runtime:` -- just `image:`.

```yaml
agents:
  - name: my-agent
    kind: hosted
    image: myregistry.azurecr.io/my-agent:v1.2.3
    protocols:
      - protocol: responses
        version: "1.0.0"
```

---

## Agent code -- code-deploy mode (`runtime:`)

Set when there is no Dockerfile -- Foundry schedules the code on a
managed runtime base image. Mutually exclusive with `docker:`.

### Python -- local zip

azd zips the project directory locally and uploads to Foundry.

```yaml
agents:
  - name: my-agent
    kind: hosted
    project: src/my-agent
    runtime:
      stack: python
      version: "3.12"
    startupCommand: python main.py
    protocols:
      - protocol: responses
        version: "1.0.0"
```

### Python -- remote build

Source uploaded; dependencies installed server-side. Useful when local
Python isn't available or wheels differ across platforms.

```yaml
agents:
  - name: my-agent
    kind: hosted
    project: src/my-agent
    runtime:
      stack: python
      version: "3.12"
      remoteBuild: true
    startupCommand: python main.py
    protocols:
      - protocol: responses
        version: "1.0.0"
```

### .NET

```yaml
agents:
  - name: my-agent
    kind: hosted
    project: src/my-agent
    runtime:
      stack: dotnet
      version: "8.0"
    startupCommand: dotnet MyAgent.dll
    protocols:
      - protocol: responses
        version: "1.0.0"
```

### Node.js

```yaml
agents:
  - name: my-agent
    kind: hosted
    project: src/my-agent
    runtime:
      stack: node
      version: "20"
    startupCommand: node server.js
    protocols:
      - protocol: responses
        version: "1.0.0"
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
  - name: my-agent
    kind: hosted
    project: src/my-agent
    runtime:
      stack: python
      version: "3.12"
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
  - name: my-agent
    kind: hosted
    project: src/my-agent
    runtime:
      stack: python
      version: "3.12"
    env:
      GITHUB_MCP_TOKEN: ${{connections.github-mcp-conn.credentials.x-api-key}}
```

---

## External file references (`$ref`)

Anywhere `azure.yaml` expects a complex object (an agent, toolbox,
connection, skill, deployment), you can replace the inline definition
with a `$ref:` to an external YAML or JSON file. Useful when an agent or
toolbox grows large, when prompt authors and infra authors live in
different files, or when you want to share a definition across projects.

The extension reads the file, deserializes it as the same shape it would
expect inline, and substitutes it during config load. The file's
extension (`.yaml`, `.yml`, `.json`) determines the parser.

### Agent from a YAML file

In `azure.yaml`:

```yaml
services:
  my-project:
    host: microsoft.foundry
    deployments:
      - model:
          format: OpenAI
          name: gpt-4.1-mini
          version: "2025-04-14"
        name: gpt-4.1-mini
        sku:
          capacity: 10
          name: GlobalStandard
    agents:
      - $ref: ./agents/research-agent.yaml
```

In `./agents/research-agent.yaml` (the agent definition -- includes
`name:` like any inline agent entry):

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/Azure/azure-dev/refs/heads/main/cli/azd/extensions/azure.ai.agents/schemas/agent.json

name: research-agent
kind: hosted
description: Deep research agent.
project: ../src/research-agent
docker:
  path: Dockerfile
  remoteBuild: true
protocols:
  - protocol: responses
    version: "1.0.0"
startupCommand: python main.py
toolboxes: [research-toolbox]
env:
  FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini
container:
  resources:
    cpu: "1"
    memory: 2Gi
```

Relative paths inside the referenced file (like `project: ../src/...`)
resolve relative to **the referenced file's location**, not `azure.yaml`.
Adjust accordingly when you move definitions around.

### Toolbox from a JSON file

JSON works the same way -- useful when a toolbox is generated by tooling
or shared with non-azd consumers (the Foundry Toolkit, for example).

In `azure.yaml`:

```yaml
services:
  my-project:
    host: microsoft.foundry
    toolboxes:
      - $ref: ./toolboxes/research-toolbox.json
```

In `./toolboxes/research-toolbox.json`:

```json
{
  "name": "research-toolbox",
  "tools": [
    { "type": "web_search" },
    { "type": "code_interpreter" },
    { "type": "mcp",             "connection": "github-mcp-conn" },
    { "type": "azure_ai_search", "connection": "azure-search-conn" }
  ]
}
```

### Other resource types

The same pattern works for skills, connections, and deployments:

```yaml
services:
  my-project:
    host: microsoft.foundry

    deployments:
      - $ref: ./resources/gpt-4.1-mini.yaml

    connections:
      - $ref: ./resources/github-mcp-conn.yaml
      - $ref: ./resources/tavily-mcp-conn.json

    toolboxes:
      - $ref: ./toolboxes/shared-tools.yaml

    skills:
      - $ref: ./skills/code-review.yaml

    agents:
      - $ref: ./agents/research-agent.yaml
      - $ref: ./agents/triage-agent.yaml
```

### Absolute vs. relative paths

Both work. Relative paths resolve from the file that contains the `$ref:`
(`azure.yaml`, or another `$ref`-ed file -- transitive refs are allowed).
Absolute paths are useful in monorepos with a shared definition folder
referenced from multiple sub-projects.

```yaml
agents:
  - $ref: /Users/me/work/shared-foundry-defs/agents/customer-support.yaml
  - $ref: C:\work\shared-foundry-defs\agents\customer-support.yaml
```

Prefer relative paths in committed code -- absolute paths break for other
developers and in CI.

### Mixing inline fields with `$ref`

`$ref:` with sibling properties means "load the file, then overlay these
fields on top." Useful for per-environment tweaks while sharing a base
definition:

```yaml
agents:
  - $ref: ./agents/research-agent.yaml
    # Overrides applied on top of the loaded file:
    env:
      FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1     # base file used gpt-4.1-mini
      LOG_LEVEL: debug
    container:
      resources:
        cpu: "2"
        memory: 4Gi                              # bigger box for this overlay
```

Override semantics: scalar fields replace; map fields shallow-merge by
top-level key; array fields replace entirely (no item-level merging).
Match how `azd env`'s per-environment overrides work elsewhere.

---

## Coexistence with non-Foundry services

Foundry projects sit alongside any other azd service kind in the same
`services:`. Use `uses:` to order non-Foundry consumers after the Foundry
project so their env vars point at real endpoints.

```yaml
services:
  my-project:
    host: microsoft.foundry
    deployments:
      - model:
          format: OpenAI
          name: gpt-4.1-mini
          version: "2025-04-14"
        name: gpt-4.1-mini
        sku:
          capacity: 10
          name: GlobalStandard
    agents:
      - name: api-agent
        kind: hosted
        project: src/api-agent
        docker:
          path: Dockerfile
          remoteBuild: true
        protocols:
          - protocol: responses
            version: "1.0.0"

  webapp:
    project: src/webapp
    host: containerapp
    language: js
    docker:
      path: Dockerfile
      remoteBuild: true
    uses: [my-project]                         # deploy after Foundry project
    env:
      FOUNDRY_PROJECT_ENDPOINT: ${FOUNDRY_PROJECT_ENDPOINT}
      AGENT_NAME: api-agent
```
