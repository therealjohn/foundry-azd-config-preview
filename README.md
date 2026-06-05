# Basic Hosted Agent (Unified `azure.yaml`)

The minimum a Foundry agent project can be after the unified-config changes
in [Azure/azure-dev#7962](https://github.com/Azure/azure-dev/issues/7962):
**one agent, one model, one `azure.yaml`**.

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
* No three places to update the agent name

## The `azure.yaml` -- annotated

See [`azure.yaml`](./azure.yaml). The whole file is ~35 lines:

```yaml
name: basic-foundry-agent

foundry:
  deployments:
    - name: gpt-4.1-mini
      model: { format: OpenAI, name: gpt-4.1-mini, version: "2025-04-14" }
      sku:   { name: GlobalStandard, capacity: 10 }

  agents:
    basic-agent:
      kind: hosted
      description: A basic Agent Framework agent hosted by Foundry.
      protocols:
        - { protocol: responses, version: "1.0.0" }
      env:
        AZURE_AI_MODEL_DEPLOYMENT_NAME: gpt-4.1-mini

services:
  basic-agent-code:
    project: src/basic-agent
    host: azure.ai.agent
    runtime: { stack: python, version: "3.12" }
    docker:  { path: Dockerfile, remoteBuild: true }
    config:
      agent: basic-agent
      container:
        resources: { cpu: "0.25", memory: "0.5Gi" }
```

### What `foundry:` owns

* `deployments` -- Foundry model deployments. Created via Foundry APIs during
  the data-plane reconcile phase.
* `agents.basic-agent` -- the agent definition that maps to Foundry's
  `createAgentVersion` API. For prompt agents this would also carry
  `instructions:`; for hosted agents (as here) the runtime image *is* the
  instructions, so we just declare the protocols and env injection.

### What `services:` owns

* `project`, `runtime`, `docker` -- the standard azd service primitives. No
  Foundry-specific stretching of the services model.
* `config.agent: basic-agent` -- the **L2 link**. Tells the extension which
  `foundry.agents` entry this service backs.
* `config.container.resources` -- the runtime container's CPU/memory.

`host: azure.ai.agent` is the existing dispatch discriminator for the
extension. It does not change in this proposal.

## Lifecycle

* `azd provision` -- creates the Foundry project (ARM, in-memory Bicep) and
  the model deployments.
* `azd deploy` -- the extension's synthesized project-level service-target
  reconciles `foundry:` state (data-plane), then `basic-agent-code` builds +
  pushes its container and posts the agent definition to Foundry.
* `azd up` -- both.
* `azd down` -- deletes the Foundry project (takes deployments with it).

## See also

* The [`complex`](../../tree/complex) branch shows the same shape scaled to
  multiple agents (hosted + prompt), shared toolboxes, MCP connections,
  skills, routines, and a non-Foundry Container Apps frontend.
* The repo [`main`](../../tree/main) README has the decision rationale.
