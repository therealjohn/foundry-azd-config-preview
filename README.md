# Complex Foundry Project (Unified `azure.yaml`)

A realistic multi-agent platform under the **collapsed shape**: one
`host: microsoft.foundry` service entry holds the entire Foundry project,
with all Foundry-scoped state as direct properties of the service. Plus a
separate non-Foundry Container Apps frontend.

## What this sample demonstrates

* **One service entry per Foundry project.** All Foundry-scoped state --
  deployments, connections, toolboxes, skills, routines, agents -- are
  direct properties of `services.support-platform`. No `config:`
  indirection. The service IS the Foundry project.
* **Field shapes match the existing `azure.ai.agent.json` schema** for
  deployments / connections / toolboxes / container.resources -- so this
  is a shape change to where things live, not to the things themselves.
* **Validated against the proposed schemas on `main`.** The
  `# yaml-language-server: $schema=` directive points at
  [`schemas/azure.yaml.json`](../../tree/main/schemas) -- a per-resource
  JSON Schema split modeled on the
  [microsoft/AgentSchema](https://github.com/microsoft/AgentSchema/tree/main/schemas/v1.0)
  pattern.
* **Data-side `$ref:` imports for the larger definitions:**
  * `agents/support-agent.yaml` and `agents/research-agent.yaml` --
    hosted agents (runtime + container settings + protocols) live in
    their own files
  * `toolboxes/research-toolbox.yaml` -- the connection-backed toolbox
  * `skills/code-review.yaml` -- skill with instructions + tools list
  * Smaller things (prompt agents, the simpler toolbox, inline skill,
    routines, deployments, connections) stay inline for contrast
* **Two hosted agents in different deploy modes**:
  * `support-agent` -- code-deploy via `runtime:` (zip upload)
  * `research-agent` -- container mode via `docker:` (Dockerfile in repo)
* **Two prompt agents** -- pure config, no source dir, no docker/runtime:
  * `triage-agent` -- inline `instructions:` string
  * `summarizer-agent` -- references the `triage` skill
* **Two named toolboxes** shared across agents
* **Three connection types** (CustomKeys + ApiKey + ProjectManagedIdentity)
* **Three model deployments** (chat large, chat mini, embeddings)
* **Two skills** with file-backed prompt instructions in `prompts/`
* **One routine** (`nightly-ticket-summary`) -- scheduled agent invocation
* **A non-Foundry Container Apps frontend** (`webapp`) consuming the agents
  -- demonstrates Foundry + non-Foundry services coexisting via `uses:`
* **Both templating syntaxes** in one file:
  * `${VAR}` -- azd env expansion, resolved client-side at deploy
  * `${{...}}` -- Foundry server-side resolution, passed through untouched

## File layout

```
.
├── azure.yaml                <- main config; references files below via $ref
├── .env.example
├── .gitignore
├── agents/                   <- extracted hosted agent definitions
│   ├── support-agent.yaml
│   └── research-agent.yaml
├── toolboxes/                <- extracted toolbox definitions
│   └── research-toolbox.yaml
├── skills/                   <- extracted skill definitions
│   └── code-review.yaml
├── prompts/
│   ├── code-review.md        <- code-review skill instructions
│   └── triage.md             <- triage skill instructions (inline skill, but file-backed prompt)
└── src/
    ├── support-agent/        <- code-deploy mode; no Dockerfile
    │   ├── main.py
    │   ├── requirements.txt
    │   └── .azdignore
    ├── research-agent/       <- container mode; has Dockerfile
    │   ├── main.py
    │   ├── requirements.txt
    │   ├── Dockerfile
    │   ├── .azdignore
    │   └── .dockerignore
    └── webapp/               <- non-Foundry containerapp frontend
        ├── server.js
        ├── package.json
        ├── Dockerfile
        ├── public/
        │   └── index.html
        └── .dockerignore
```

## The `azure.yaml` -- by section

### Top-level: two service entries

```yaml
services:
  support-platform:           # Foundry project
    host: microsoft.foundry
    deployments: [...]        # everything Foundry-scoped is a direct service property
    agents:      [...]
  webapp:                     # non-Foundry frontend
    host: containerapp
    uses: [support-platform]  # deploy after the Foundry project
```

### `deployments`

```yaml
services:
  support-platform:
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

Project-scoped model deployments. Same shape as today's `azure.ai.agent.json`
schema. Reconciled via Foundry APIs. Drop-from-config is non-destructive.

### `connections`

```yaml
services:
  support-platform:
    connections:
      - name: github-mcp-conn
        category: CustomKeys
        target: https://api.githubcopilot.com/mcp
        authType: CustomKeys
        credentials:
          x-api-key: ${GITHUB_MCP_TOKEN}        # ${VAR} = azd env expansion
```

Two secret modes shown:

1. **azd-environment-managed** -- `${ENV_VAR}` resolved client-side
2. **Foundry-managed identity** -- `authType: ProjectManagedIdentity`, no secret on disk

### `toolboxes`

```yaml
services:
  support-platform:
    toolboxes:
      - name: research-toolbox
        tools:
          - type: web_search
          - type: mcp
            connection: github-mcp-conn
          - type: mcp
            connection: tavily-mcp-conn
          - type: azure_ai_search
            connection: azure-search-conn
```

Named toolboxes; agents reference by name in `agents[].toolboxes`.

### `skills`

```yaml
services:
  support-platform:
    skills:
      - name: code-review
        description: Reviews code for bugs and style issues
        instructions: ./prompts/code-review.md
        tools: [file_search, code_interpreter]
```

`instructions:` accepts a string (inline) or a file path. File-backed is
git-diff friendly.

### `routines`

```yaml
services:
  support-platform:
    routines:
      - name: nightly-ticket-summary
        trigger:
          type: schedule
          cron: "0 8 * * *"
        agent: summarizer-agent
        input:
          ticket_source: ${TICKET_SOURCE_URL}
```

Scheduled or event-driven agent invocations.

### `agents`

Each agent carries both its Foundry definition and (for hosted agents) its
code/build settings in **one entry**. No separate services: per-agent, no
link field.

Prompt agent:

```yaml
agents:
  - name: triage-agent
    kind: prompt
    description: Routes customer questions to the right specialist agent
    instructions: |
      You are a triage agent...
    env:
      FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini
```

Hosted agent (code-deploy mode):

```yaml
agents:
  - name: support-agent
    kind: hosted
    description: Handles general customer support questions
    project: src/support-agent
    runtime:
      stack: python
      version: "3.12"
    startupCommand: python main.py
    protocols:
      - protocol: responses
        version: "1.0.0"
    toolboxes: [support-toolbox]
    env:
      FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1
    container:
      resources:
        cpu: "0.5"
        memory: 1Gi
```

Hosted agent (container mode):

```yaml
agents:
  - name: research-agent
    kind: hosted
    project: src/research-agent
    docker:
      path: Dockerfile
      remoteBuild: true
    protocols:
      - protocol: responses
        version: "1.0.0"
    toolboxes: [research-toolbox]
    env:
      FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1
      # ${{...}} is Foundry server-side resolution. azd does NOT expand it.
      GITHUB_MCP_TOKEN: ${{connections.github-mcp-conn.credentials.x-api-key}}
      TAVILY_API_KEY: ${{connections.tavily-mcp-conn.credentials.key}}
    container:
      resources:
        cpu: "1"
        memory: 2Gi
```

Per-agent fields:

| Field | Belongs to |
|---|---|
| `kind`, `description`, `protocols`, `env`, `container`, `toolboxes`, `skill` | Foundry agent definition (sent to `createAgentVersion`) |
| `project`, `runtime` OR `docker`, `startupCommand`, `image` | Code/build (standard azd primitives, scoped per-agent) |
| `instructions` (prompt agents) | Inline prompt OR `./path.md` file ref |

`docker:` and `runtime:` are mutually exclusive per agent. Both / neither
is a validation error.

## Lifecycle

The `microsoft.foundry` service-target fans out internally across nested
agents:

1. `azd provision`
   * Creates the Foundry project (ARM, in-memory Bicep) and Container Apps
     environment + ACR for the webapp.
2. `azd deploy`
   * **support-platform** (Foundry project service):
     * reconciles `deployments`, `connections`, `toolboxes`, `skills`,
       `routines` via Foundry APIs
     * builds + uploads zip for `support-agent` (runtime: mode)
     * builds + pushes container for `research-agent` (docker: mode)
     * posts `createAgentVersion` for every agent (4 total: 2 prompt + 2 hosted)
   * **webapp**: builds container + deploys to Container Apps
3. `azd up` -- both, in `uses:` order
4. `azd down` -- destroys the Foundry project and the resource group

Per-agent ops route through the extension CLI:

```bash
azd ai agent deploy support-agent       # update just one agent
azd ai agent run research-agent         # local dev for one agent
azd ai agent invoke support-agent "Hi"  # invoke a deployed agent
```

The standard `azd deploy support-platform` addresses the whole Foundry
project as a single unit.

## How this would be authored after init

`azd ai agent init` produces a starter project with one hosted agent. The
rest of the sections shown here would be added via the composition commands
in [#8049](https://github.com/Azure/azure-dev/issues/8049):

```bash
azd ai project add model gpt-4.1
azd ai project add connection github-mcp-conn --category CustomKeys ...
azd ai project add toolbox research-toolbox --tools web_search,mcp:github-mcp-conn
azd ai project add agent triage-agent --kind prompt
azd ai project add skill code-review --instructions ./prompts/code-review.md
```

Each command appends to the corresponding array on the Foundry service in
`azure.yaml`, externalizes credentials to the azd environment, and prints
what code or follow-up steps remain.

## See also

* [`simple`](../../tree/simple) -- minimum viable Foundry project
* [`main`](../../tree/main) -- repo overview, decision rationale, and
  engineering brief; also `REFERENCE.md` with copy-pasteable snippets
* [#7962](https://github.com/Azure/azure-dev/issues/7962) -- unified-config proposal
* [#8049](https://github.com/Azure/azure-dev/issues/8049) -- composition commands
