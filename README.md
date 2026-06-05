# foundry-azd-config-preview

A reference for what a Foundry agent project looks like after the
**unified `azure.yaml`** changes proposed in
[Azure/azure-dev#7962](https://github.com/Azure/azure-dev/issues/7962)
and the composition follow-up in
[Azure/azure-dev#8049](https://github.com/Azure/azure-dev/issues/8049).

This is a preview of file shapes only. The CLI changes that produce these
files have not shipped yet. Code in the sample branches is illustrative; the
behavior is real but it is not wired to a live Foundry endpoint.

## What changes vs. today

Today a Foundry agent project carries three files with overlapping data:

* `azure.yaml` (`host: azure.ai.agent` + `config:` with toolboxes/connections/deployments)
* `agent.yaml` (AgentDefinition)
* `agent.manifest.yaml` (templated manifest with `{{param}}` resources)

Two templating syntaxes overlap (`{{param}}` and `${ENV}`), the agent name
appears in three places, and ~200 lines of init-time wiring reconciles them.

After the changes, a project has **one** file: `azure.yaml`, with two
top-level sections that have clean responsibilities.

## Key decisions baked into these samples

1. **One file**: everything lives in `azure.yaml`. `agent.yaml` and
   `agent.manifest.yaml` are gone.
2. **New top-level `foundry:` section**: owns all project-scoped Foundry
   data-plane state -- model deployments, connections, toolboxes, skills,
   routines, and *all* agent definitions (both hosted and prompt).
3. **`services:` keeps doing what it is good at**: source directory, build
   mode (`docker:` vs `runtime:`), packaging, deploy. A services entry is
   present only when an agent has code.
4. **L2 link**: a code-bearing agent's services entry uses `host:
   azure.ai.agent` and adds `config.agent: <name>` to point at the
   `foundry.agents.<name>` definition. The service backs the agent;
   `foundry.agents` is the source of truth for what the agent IS to Foundry.
5. **Prompt agents have no services entry** -- pure config in
   `foundry.agents`. Future no-code kinds work the same way.
6. **Lifecycle under the hood**: the `azure.ai.agents` extension synthesizes
   a virtual project-level service-target from the `foundry:` block.
   Reconciles data-plane state via Foundry APIs during `azd deploy`. No new
   user-facing verb.
7. **`${{...}}` preserved**: Foundry server-side resolution
   (`${{connections.x.credentials.key}}`) is passed through untouched by
   azd's `${VAR}` expansion.
8. **No Bicep on disk by default**: the extension carries built-in Bicep
   internally (azd compose pattern) for Foundry project provisioning.
   `azd infra gen` ejects to disk when explicit IaC is needed.

## Branches

| Branch | Demonstrates |
|---|---|
| [`simple`](../../tree/simple) | One hosted agent + one model. The minimum a Foundry project can be. ~30-line `azure.yaml`. |
| [`complex`](../../tree/complex) | Multi-agent project: hosted agents, prompt agents, toolboxes with web search / code interpreter / MCP, connections with externalized secrets, skills, routines, and a separate non-Foundry Container Apps frontend that calls the agents. |

Open either branch to see the full file layout, `azure.yaml` shape, and
realistic supporting files (`Dockerfile`, `requirements.txt`, Python sources,
prompt files).

## Related links

* [#7962 -- Unify Foundry agent configuration in azure.yaml](https://github.com/Azure/azure-dev/issues/7962)
* [#8049 -- Add connections, models, tools, and skills to Foundry Agent projects after init](https://github.com/Azure/azure-dev/issues/8049)
* [Azure Developer CLI](https://github.com/Azure/azure-dev)
* [`azure.ai.agents` extension](https://github.com/Azure/azure-dev/tree/main/cli/azd/extensions/azure.ai.agents)
* [Reference Foundry samples (today's shape)](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/agent-framework/responses)
