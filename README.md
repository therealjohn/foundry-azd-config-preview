# Basic Hosted Agent (Unified `azure.yaml`)

The minimum a Foundry agent project can be after the unified-config
changes: **one agent, one model, one `azure.yaml`, one service entry**.

## What `azd ai agent init` produced

```
.
├── azure.yaml         <- the only Foundry-aware config file
├── .env.example
├── .gitignore
└── src/
    └── basic-agent/
        ├── main.py
        ├── requirements.txt
        ├── Dockerfile
        ├── .azdignore
        └── .dockerignore
```

What is **not** here vs. today's shape:

* No `agent.yaml`
* No `agent.manifest.yaml`
* No `infra/` directory and no Bicep on disk (the extension carries built-in
  Bicep internally, generated in-memory during `azd provision`; the azd
  compose pattern)
* No three places to update the agent name -- the agent definition lives in
  exactly one place

## The `azure.yaml` -- annotated

See [`azure.yaml`](./azure.yaml). The whole file is ~40 lines:

```yaml
name: basic-foundry-agent

services:
  agent-project:
    host: microsoft.foundry            # new host kind: Foundry project is the service

    deployments:                       # project-scoped model deployments (existing agents schema)
      - model:
          format: OpenAI
          name: gpt-4.1-mini
          version: "2025-04-14"
        name: gpt-4.1-mini
        sku:
          capacity: 10
          name: GlobalStandard

    agents:                            # ALL agent definitions nest here
      - name: basic-agent
        kind: hosted
        project: src/basic-agent       # per-agent source dir (NOT the service's)
        docker:
          path: Dockerfile
          remoteBuild: true
        protocols:
          - protocol: responses
            version: "1.0.0"
        startupCommand: python main.py
        env:
          FOUNDRY_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini
        container:
          resources:
            cpu: "0.25"
            memory: 0.5Gi
```

### Why one service entry for the whole Foundry project

The service IS the Foundry project. The Foundry project owns model
deployments, connections, toolboxes, agents -- they are not separate
services in azd's sense. They are state inside one project. So one azd
service maps to one Foundry project, and everything Foundry-scoped is a
direct property of that service entry -- no `config:` indirection.

This is the same pattern existing host kinds use today for their first-class
fields. `host: microsoft.foundry` is just another host kind with its own
schema published by the `azure.ai.agents` extension. The Foundry schema
slice is composed at the service-entry level (no `config:` indirection),
the same way `host: containerapp` exposes container-app-shaped fields
directly on the service.

### Per-agent fields

Each entry under `config.agents.<name>` carries both the agent's Foundry
definition AND its code/build settings:

| Field | Belongs to |
|---|---|
| `kind`, `description`, `protocols`, `env`, `container` | Foundry agent definition (sent to `createAgentVersion`) |
| `project`, `runtime` OR `docker`, `startupCommand` | Code/build settings (standard azd primitives, scoped per-agent) |

Deploy mode discrimination is identical to other azd hosts:

* `docker:` present -> container mode (Dockerfile in source dir)
* `runtime:` present -> code-deploy mode (zip upload, no Dockerfile)
* Both / neither -> validation error

## Lifecycle

The `microsoft.foundry` service-target fans out internally across the
agents nested in the service entry:

* `azd provision` -- creates the Foundry project (ARM, in-memory Bicep) and
  the model deployments.
* `azd deploy agent-project` --
  * reconciles project-level data-plane state (deployments, connections,
    toolboxes, etc. -- just deployments in this sample)  * for each agent with code (`basic-agent` here), builds + pushes the
    artifact, then posts the agent definition to Foundry's
    `createAgentVersion` API
* `azd up` -- both.
* `azd down` -- deletes the Foundry project (takes deployments with it).
* Per-agent operations (`azd ai agent deploy basic-agent`) route through
  the extension CLI -- the standard `azd deploy <service>` addresses the
  whole Foundry project, not individual agents.

## See also

* The [`complex`](../../tree/complex) branch shows the same shape scaled to
  multiple agents (hosted + prompt), shared toolboxes, MCP connections,
  skills, routines, and a non-Foundry Container Apps frontend.
* The [`main`](../../tree/main) branch README has decision rationale and
  the engineering brief for the `azure.ai.agents` team.
