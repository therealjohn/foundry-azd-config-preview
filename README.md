# Complex Foundry Project (Unified `azure.yaml`)

A realistic multi-agent platform that exercises every section of the new
unified `azure.yaml` shape.

## What this sample demonstrates

* **Two hosted agents in different deploy modes**
  * `support-agent` -- code-deploy via `runtime:` (zip upload, no Dockerfile)
  * `research-agent` -- container mode via `docker:` (Dockerfile in repo)
* **Two prompt-only agents** with no `services:` entry
  * `triage-agent` -- inline `instructions:` string
  * `summarizer-agent` -- references a `foundry.skills` entry
* **Two named toolboxes** sharing tools across agents (the thing the old
  per-agent `agent.manifest.yaml` could not do cleanly)
* **Three connection types**
  * `github-mcp-conn` -- `CustomKeys` auth, secret via `${ENV_VAR}` from
    azd environment
  * `tavily-mcp-conn` -- `ApiKey` auth, also `${ENV_VAR}`
  * `azure-search-conn` -- `ProjectManagedIdentity`, no secret on disk
* **Three model deployments** (chat large, chat mini, embeddings)
* **Two skills** with file-backed prompt instructions in `prompts/`
* **One routine** (`nightly-ticket-summary`) -- scheduled agent invocation
* **A non-Foundry Container Apps frontend** (`webapp`) that calls the agents
  -- shows Foundry resources coexisting with the rest of azd's ecosystem
* **Both templating syntaxes** in one file:
  * `${VAR}` -- azd env expansion, resolved at deploy time on the client
  * `${{...}}` -- Foundry server-side resolution, passed through untouched

## File layout

```
.
├── azure.yaml                <- the only Foundry-aware config file
├── .env.example
├── .gitignore
├── prompts/
│   ├── code-review.md        <- skill instructions (code-review skill)
│   └── triage.md             <- skill instructions (triage skill, used by summarizer-agent)
└── src/
    ├── support-agent/        <- code-deploy mode; no Dockerfile needed
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

## The shape of `azure.yaml` -- by section

### `foundry.deployments`

```yaml
foundry:
  deployments:
    - name: gpt-4.1
      model: { format: OpenAI, name: gpt-4.1, version: "2025-04-14" }
      sku:   { name: GlobalStandard, capacity: 50 }
```

Model deployments on the Foundry project. Created via Foundry APIs during
data-plane apply. Removing here is **not** destructive on the next deploy
(matches Bicep semantics) -- use `azd down` or `az` CLI to destroy.

### `foundry.connections`

```yaml
foundry:
  connections:
    - name: github-mcp-conn
      category: CustomKeys
      target: https://api.githubcopilot.com/mcp
      authType: CustomKeys
      credentials:
        x-api-key: ${GITHUB_MCP_TOKEN}    # azd env expansion (${VAR})
```

Two secret-management modes are shown:

1. **azd-environment-managed** -- `${ENV_VAR}` references. azd reads the
   value from `.azure/<env>/.env` at deploy time and posts it to Foundry.
2. **Foundry-managed identity** -- no secret on disk. The Foundry project's
   managed identity authenticates to the target.

### `foundry.toolboxes`

```yaml
foundry:
  toolboxes:
    research-toolbox:
      tools:
        - { type: web_search }
        - { type: mcp,             connection: github-mcp-conn }
        - { type: mcp,             connection: tavily-mcp-conn }
        - { type: azure_ai_search, connection: azure-search-conn }
```

Named toolboxes. Multiple agents reference the same toolbox by name (see
`support-toolbox` shared by `support-agent`; `research-toolbox` shared by
`research-agent`). Tools that need a connection reference it by name --
Foundry resolves connection IDs at deploy time.

### `foundry.skills`

```yaml
foundry:
  skills:
    code-review:
      description: Reviews code for bugs and style issues
      instructions: ./prompts/code-review.md
      tools: [file_search, code_interpreter]
```

Reusable capability bundles. `instructions:` accepts a string (inline) or a
file path (markdown). File-backed instructions are friendlier to git diffs
and to non-developer prompt authors.

### `foundry.routines`

```yaml
foundry:
  routines:
    nightly-ticket-summary:
      trigger: { type: schedule, cron: "0 8 * * *" }
      agent: summarizer-agent
      input:
        ticket_source: ${TICKET_SOURCE_URL}
```

Scheduled or event-driven agent invocations. Reconciled by the
`azure.ai.routines` extension during data-plane apply.

### `foundry.agents`

All agent definitions live here. Hosted and prompt agents share the same
section so the mental model stays uniform: "Foundry agents are defined in
`foundry.agents`. Some of them happen to have code."

Prompt agent (no services entry):

```yaml
foundry:
  agents:
    triage-agent:
      kind: prompt
      description: Routes customer questions to the right specialist agent
      instructions: |
        You are a triage agent...
      env:
        AZURE_AI_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini
```

Hosted agent (links to a services entry):

```yaml
foundry:
  agents:
    research-agent:
      kind: hosted
      description: Deep research agent using web search, MCP, and Azure AI Search
      protocols:
        - { protocol: responses, version: "1.0.0" }
      toolboxes: [research-toolbox]
      env:
        AZURE_AI_MODEL_DEPLOYMENT_NAME: gpt-4.1
        # ${{...}} is Foundry server-side resolution. azd does NOT expand it.
        # Foundry reads the live credential from the named project connection
        # and injects it into the agent process at runtime.
        GITHUB_MCP_TOKEN: ${{connections.github-mcp-conn.credentials.x-api-key}}
        TAVILY_API_KEY:   ${{connections.tavily-mcp-conn.credentials.key}}
```

### `services` (only for code-bearing agents)

Two hosted agents demonstrate both deploy modes:

```yaml
services:
  # Code-deploy mode (runtime: present, no Dockerfile)
  support-agent-code:
    project: src/support-agent
    host: azure.ai.agent
    runtime: { stack: python, version: "3.12" }
    startupCommand: python main.py
    config:
      agent: support-agent              # L2 link
      container:
        resources: { cpu: "0.5", memory: "1Gi" }

  # Container mode (docker: present, Dockerfile in repo)
  research-agent-code:
    project: src/research-agent
    host: azure.ai.agent
    docker: { path: Dockerfile, remoteBuild: true }
    config:
      agent: research-agent             # L2 link
      container:
        resources: { cpu: "1", memory: "2Gi" }
```

Validation rule (from [#7962](https://github.com/Azure/azure-dev/issues/7962)):
`docker:` and `runtime:` are mutually exclusive. Both present, or neither
present, is a validation error.

### A non-Foundry service alongside

```yaml
services:
  webapp:
    host: containerapp
    language: js
    docker: { path: Dockerfile, remoteBuild: true }
    uses: [support-agent-code, research-agent-code]
    env:
      AZURE_AI_PROJECT_ENDPOINT: ${AZURE_AI_PROJECT_ENDPOINT}
      SUPPORT_AGENT_NAME: support-agent
      RESEARCH_AGENT_NAME: research-agent
```

Container Apps frontend, standard azd. `uses:` orders it after the agents so
its env points at real endpoints.

## Lifecycle for this project

1. `azd provision` -- creates the Foundry project (ARM, in-memory Bicep),
   the model deployments, the Container Apps environment, and an Azure
   Container Registry.
2. `azd deploy` --
   * synthesized project-level service-target reconciles `foundry:` state:
     deployments, connections, toolboxes, skills, routines, prompt agents
   * `support-agent-code` builds (zip upload) + extension pushes the agent
     definition for `support-agent`
   * `research-agent-code` builds container (remote build) + extension
     pushes the agent definition for `research-agent`
   * `webapp` builds container + deploys to Container Apps
3. `azd up` -- both, in order, with `uses:` driving service ordering.
4. `azd down` -- destroys the Foundry project and the resource group.

## How this would be authored after init

`azd ai agent init` produces a starter project with one hosted agent. The
rest of the sections shown here would be added incrementally via the
composition commands proposed in
[#8049](https://github.com/Azure/azure-dev/issues/8049):

```bash
azd ai project add model gpt-4.1
azd ai project add connection github-mcp-conn --category CustomKeys ...
azd ai project add toolbox research-toolbox --tools web_search,mcp:github-mcp-conn
azd ai project add agent triage-agent --kind prompt
azd ai project add skill code-review --instructions ./prompts/code-review.md
```

Each command edits `azure.yaml` in place, externalizes credentials to the
azd environment, and prints what code or follow-up steps are needed.

## See also

* [`simple`](../../tree/simple) branch -- minimum viable Foundry project
* [`main`](../../tree/main) branch -- repo overview and decision rationale
* [#7962](https://github.com/Azure/azure-dev/issues/7962) -- the unified-config proposal
* [#8049](https://github.com/Azure/azure-dev/issues/8049) -- composition commands
