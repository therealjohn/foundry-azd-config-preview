# foundry-azd-config-preview

A file-shape reference for the **unified `azure.yaml`** proposal that
consolidates Foundry agent project configuration. Pairs with the open RFCs:

* [Azure/azure-dev#7962](https://github.com/Azure/azure-dev/issues/7962) -- Unify Foundry agent configuration in `azure.yaml`
* [Azure/azure-dev#8049](https://github.com/Azure/azure-dev/issues/8049) -- Composition commands (`azd ai project add ...`)

The CLI changes that produce these files have not shipped. The Python in
the sample branches is illustrative -- it would compile and run against a
real Foundry endpoint, but most logic is stubbed.

## Branches and folders

| Branch / folder | Demonstrates |
|---|---|
| [`simple`](../../tree/simple) | One hosted agent + one model deployment under a single `host: microsoft.foundry` service entry. ~40-line `azure.yaml`. The minimum a Foundry project can be. |
| [`complex`](../../tree/complex) | Multi-agent platform: 2 hosted + 2 prompt agents (both `runtime:`/`docker:` deploy modes shown), shared toolboxes with web search / code interpreter / MCP / Azure AI Search, three connection types (incl. `${{...}}` server-side resolution), 3 model deployments, 2 file-backed skills, a scheduled routine, all under one Foundry service entry -- plus a separate non-Foundry Container Apps frontend that consumes the agents. Also shows **data-side `$ref:` imports** for agents, toolboxes, and skills (split into `agents/`, `toolboxes/`, `skills/` sub-folders). |
| [`separate-services`](../../tree/separate-services) | The Complete example from [`REFERENCE.md`](./REFERENCE.md) re-expressed as **one service per resource** instead of a single `host: microsoft.foundry` entry. Every resource is its own top-level `services:` entry (siblings, not nested), each with a singular `host: azure.ai.<kind>` matching the extension namespaces / the existing `azure.ai.agent` service target: `azure.ai.project` (the project + its model deployments), and one `azure.ai.connection`, `azure.ai.toolbox`, `azure.ai.skill`, and `azure.ai.agent` service per connection / toolbox / skill / agent. Services are ordered with `uses:`; resources reference each other by name across service boundaries. Demonstrates Option B (per-resource extensions own their slice) from the design brief below. |
| [`schemas/`](./schemas) (this branch) | Proposed JSON Schema files for `host: microsoft.foundry`, split per-resource (`Deployment.json`, `Connection.json`, `Toolbox.json`, `Skill.json`, `Routine.json`, `Agent.json`) and composed via `$ref` -- modeled on the [microsoft/AgentSchema](https://github.com/microsoft/AgentSchema/tree/main/schemas/v1.0) pattern. Each per-resource schema accepts either an inline definition or a `$ref` to an external file via `oneOf`. |

For copy-pasteable snippets covering individual scenarios (single vs.
multi-agent, new vs. existing resource references, Docker local/remote,
code-deploy across Python/.NET/Node, etc.), see [`REFERENCE.md`](./REFERENCE.md).

---

# For the azd engineering team

This is the engineering-grade brief for evaluating whether the proposed
design is correct, complete, and worth building. Read top to bottom; each
section calls out the problem, the proposed change, the current code-side
gap, and the open questions where the team needs to make a call.

## Problem statement

A Foundry agent project today spreads across three files with overlapping data:

| File | Owns | Pain |
|---|---|---|
| `azure.yaml` | `host: azure.ai.agent` service + `config:` block (toolboxes, connections, model deployments) | Mixes per-agent runtime config with project-scoped state |
| `agent.yaml` | AgentDefinition (kind, name, protocols, container resources, env, code config) | Per-agent file; project-scoped sharing impossible |
| `agent.manifest.yaml` | Templated `{{param}}` manifest with `resources[]` (model deployments, connections, toolboxes) | Adds a second templating syntax (`{{...}}` vs `${...}`); manifest layer carries no weight (catalog never shipped) |

* The agent name appears in three places, container resources in two, the
  model deployment name in three.
* `cli/azd/extensions/azure.ai.agents/internal/cmd/init.go` runs ~200 lines
  of reconciliation between these files
  (`extractToolboxAndConnectionConfigs`, `extractConnectionConfigs`).
* Multiple agents that need to share a toolbox cannot: toolboxes live
  nested under a single agent's `config:` today.

The deeper structural mismatch: `azure.yaml` was designed for Azure services
modeled as ARM/Bicep resources. Foundry's project-scoped state (toolboxes,
connections, model deployments, skills, agents) is **data-plane** -- created
and reconciled via Foundry APIs, not ARM. The earlier proposals
(`host: azure.ai.project` "service without code"; a top-level `foundry:`
section that duplicated services semantics) all stretched the model in one
direction or another. The shape here resolves the mismatch by recognizing
that **a Foundry project IS a service** -- just one that owns nested data
plane state and may host multiple sub-agents.

## The shape, in one paragraph

One Foundry project = one entry in `services:` with a new host kind,
`microsoft.foundry`. That entry carries all Foundry-scoped state as
**direct top-level properties** of the service (no `config:` indirection):
model deployments, project connections, toolboxes, skills, routines, and
every agent definition. Each agent nests its own `project:`/`runtime:`/`docker:`/`startupCommand:` when code-bearing; prompt agents skip those
fields and live as pure config. The extension's service target fans out
internally: it builds and pushes each code-bearing agent, then posts every
agent's `createAgentVersion` to Foundry. Non-Foundry services (Container
Apps, App Service, etc.) coexist as additional top-level `services:`
entries and use the standard `uses:` for ordering.

## Architectural decisions

| Decision | Choice | Why |
|---|---|---|
| Scope | Foundry-specific changes to azd core, not a generic data-plane primitive | Smaller blast radius. Foundry team owns the new host kind's schema. Re-evaluate generalization later if other extensions need it. |
| Where Foundry state lives in `azure.yaml` | As direct top-level properties of a single `services:` entry with `host: microsoft.foundry` (no `config:` indirection) | A Foundry project is one logical thing; one service entry models it. Treating Foundry as a first-class host kind (not an extension-escape-via-`config:` pattern) matches how built-in azd hosts expose their first-class fields. |
| Where agent definitions live | Nested under `services.<>.agents.<name>` | Agents belong to a project; nesting captures the relationship. No separate top-level `agents:`. |
| Where agent code/build lives | Nested with the agent definition (`agents.<>.project`, `.runtime`, `.docker`, etc.) | One entry per agent; no dual-entry, no link field. The trade-off: per-agent ops via `azd deploy <name>` are not addressable -- they route through the extension CLI (`azd ai agent deploy <name>`). |
| Lifecycle | `microsoft.foundry` service-target owns the full lifecycle and fans out across nested agents internally | Reuses existing service-target plumbing (ordering, telemetry, hooks). Cost: the extension implements per-agent build orchestration itself; azd core sees one service. |
| Templating | `${VAR}` keeps existing semantics; `${{...}}` is preserved verbatim through expansion (Foundry server-side resolution) | Two distinct resolvers (azd client-side vs Foundry server-side) need to coexist without stepping on each other. |
| Bicep on disk | Opt-in, not default | Extension carries built-in Bicep internally (azd compose pattern) for Foundry project provisioning. `azd infra gen` ejects to disk when explicit IaC is required. |
| Replaces `host: azure.ai.agent`? | Yes (deprecation window) | The old per-agent host kind no longer makes sense -- agents are not top-level services in this model. Keep parsing it during the deprecation window so old projects still build. |

## Required AZD core changes

### 1. Recognize `host: microsoft.foundry` in `azure.yaml`

* **Problem.** The new host kind needs a JSON Schema entry so editor
  IntelliSense + validation work, and so the Foundry properties (which
  live as direct service entry fields, not nested under `config:`) are
  composed in from the extension-published schema.
* **Proposal.** Add a new conditional to `schemas/v1.0/azure.yaml.json`.
  Unlike the existing `host: azure.ai.agent` pattern at
  [`schemas/v1.0/azure.yaml.json:373-388`](https://github.com/Azure/azure-dev/blob/main/schemas/v1.0/azure.yaml.json#L373-L388)
  -- which `$ref`s the extension schema into `config:` -- this composes
  the extension schema at the service level via `allOf`:
  ```json
  {
    "if": { "properties": { "host": { "const": "microsoft.foundry" } } },
    "then": {
      "allOf": [
        { "$ref": "https://raw.githubusercontent.com/Azure/azure-dev/refs/heads/main/cli/azd/extensions/azure.ai.agents/schemas/microsoft.foundry.json" }
      ],
      "properties": {
        "project": false,
        "runtime": false,
        "docker":  false,
        "image":   false,
        "config":  false
      }
    }
  }
  ```
  The service-level `project:`/`runtime:`/`docker:`/`image:` fields are
  rejected because they belong per-agent inside `agents.<>`. The Foundry
  project itself has no source code. `config:` is also rejected -- the
  Foundry schema is composed at the service level instead.
* **Current state.** `ServiceConfig.AdditionalProperties` is `map[string]any`
  with `yaml:",inline"` (`pkg/project/service_config.go:76-77`), so the
  Foundry-specific top-level keys (`deployments`, `connections`,
  `toolboxes`, `agents`, etc.) parse out of the box and are available to
  the extension via the existing gRPC mapper (see
  `pkg/project/mapper_registry.go:140-160`). The gap is purely the JSON
  Schema entry.
* **Risk / alternative.** None significant. If the team prefers the
  `config:` indirection for consistency with other extensions, the
  earlier shape (Foundry properties nested under `config:`) is a
  one-line difference in the JSON Schema -- but loses the
  "first-class host kind" feel and inconsistency with other built-in
  hosts that surface properties directly.

### 2. Register a new service-target kind in the extension

* **Problem.** The `azure.ai.agents` extension needs to claim
  `microsoft.foundry` as a service-target so azd dispatches to its provider
  for Initialize / Package / Publish / Deploy / Endpoints /
  GetTargetResource.
* **Proposal.** Add a second `WithServiceTarget` call alongside the
  existing one at [`listen.go:40-42`](https://github.com/Azure/azure-dev/blob/main/cli/azd/extensions/azure.ai.agents/internal/cmd/listen.go#L40):
  ```go
  host.
    WithServiceTarget("azure.ai.agent",    ...).  // existing, deprecated
    WithServiceTarget("microsoft.foundry", func() azdext.ServiceTargetProvider {
      return project.NewFoundryProjectTargetProvider(azdClient)
    })
  ```
  Plus update `extension.yaml` providers list to declare the new
  service-target.
* **Current state.** The provider plumbing already exists and is exercised
  for `azure.ai.agent`. Adding a second is straight-line extension work,
  no core change.
* **Risk / alternative.** None.

### 3. Per-agent build/publish inside one service-target

* **Problem.** azd's existing service-target contract assumes one source
  dir, one build, one publish per service. The Foundry project service has
  N nested agents, each with its own `project:`/`runtime:`/`docker:` (for
  the hosted, code-bearing ones). The extension has to fan out internally.
* **Proposal.** Two viable paths:
  * **3a (extension does it all).** The Foundry service-target's `Package`
    iterates `config.agents`, finds the code-bearing ones, and runs builds
    itself -- shelling out to `docker build` / zip packaging, or calling
    azd's docker helpers via the gRPC client if exposed. `Publish` pushes
    artifacts (ACR for container mode; Foundry blob upload for code-deploy
    mode). `Deploy` posts the agent definition with the published
    artifact reference. Most contained; no core change.
  * **3b (core support for nested code-bearing units).** azd core gains a
    notion of "sub-services" -- a service that itself contains build/deploy
    units azd can drive. Extensions declare which keys at their service
    level represent sub-services. Cleaner UX (per-agent progress, telemetry,
    failure attribution) but a meaningful new core concept.
* **Recommendation.** **3a for v1** to avoid blocking on core; revisit 3b
  if per-agent observability becomes a real pain point.
* **Current state.** Neither path is implemented. 3a is straightforward
  extension work; 3b is a meaningful new core capability not on any current
  roadmap.
* **Risk.** Under 3a, errors during one agent's build surface as
  "support-platform failed" rather than "support-agent failed." Mitigate
  with extension-side structured error messages naming the agent.

### 4. Preserve `${{...}}` through azd's `${VAR}` expansion

* **Problem.** Foundry uses `${{connections.x.credentials.key}}` for
  server-side resolution. azd's existing envsubst path
  (`pkg/osutil/expandable_string.go:29-30`, backed by
  `github.com/drone/envsubst`) treats `$` as a sigil and may consume or
  corrupt the `${{...}}` pattern before it reaches the Foundry API.
* **Proposal.** Either (a) pre-process `${{...}}` to a sentinel before
  envsubst and restore after, or (b) add a `PreserveSyntax` option on
  `ExpandableString.Envsubst` that skips `${{...}}`. Apply only where
  Foundry data is read.
* **Current state.** `ServiceConfig.Config` is **not** envsubst-expanded
  by azd core today -- extensions handle it. So this is primarily an
  extension-side concern. Either way, the team should agree on a shared
  helper so any future extension that touches Foundry config behaves
  identically.
* **Risk / alternative.** If the extension owns all expansion of the
  Foundry-block fields, no core change needed. Worth aligning on the
  convention before two extensions write divergent expanders.

### 5. Deprecate `host: azure.ai.agent`

* **Problem.** The old per-agent host kind no longer fits -- agents are
  not top-level services in this model.
* **Proposal.** Keep parsing `host: azure.ai.agent` during the deprecation
  window. When detected, emit a structured deprecation warning that points
  at the migration guide. Remove after one window (informed by telemetry).
* **Current state.** Today's service-target at
  `cli/azd/extensions/azure.ai.agents/internal/project/service_target_agent.go`
  handles `host: azure.ai.agent`. Keep it running; mark deprecated.
* **Risk.** Coordinating the cutover with the Foundry Toolkit for VS Code,
  which currently reads `agent.yaml` directly and will need to learn the
  new shape.

## Required extension changes (`azure.ai.agents`)

### 1. Publish `microsoft.foundry.json` schema

Owns the full schema for `host: microsoft.foundry` services -- composed
at the service entry level via `allOf` (see core change #1):

```jsonc
{
  "type": "object",
  "properties": {
    "deployments": { ... },
    "connections": { ... },
    "toolboxes":   { ... },
    "skills":      { ... },
    "routines":    { ... },
    "agents":      { ... }
  },
  "additionalProperties": true
}
```

Lives at `cli/azd/extensions/azure.ai.agents/schemas/microsoft.foundry.json`.
`additionalProperties: true` at the top level so new Foundry data-plane
resources (eval datasets, vector indexes, memories) can be added without
azd-side schema breaks.

Per-agent sub-schema accepts both Foundry definition fields and the azd
build primitives:

* Foundry fields: `kind`, `description`, `protocols`, `env`, `container`,
  `toolboxes`, `skill`, `instructions`, `image`
* Build fields: `project`, `runtime`, `docker`, `startupCommand`
* `runtime:` and `docker:` are mutually exclusive (validation rule). Both
  required for `kind: hosted` unless `image:` (pre-built) is set.

### 2. Slim or remove the old `azure.ai.agent.json` schema

Today's [`cli/azd/extensions/azure.ai.agents/schemas/azure.ai.agent.json`](https://github.com/Azure/azure-dev/blob/main/cli/azd/extensions/azure.ai.agents/schemas/azure.ai.agent.json)
loses everything except whatever fields are still meaningful for the
deprecated `host: azure.ai.agent` shape during the migration window.
Eventually it goes away with the host kind.

### 3. Implement the `microsoft.foundry` service-target

New file: `cli/azd/extensions/azure.ai.agents/internal/project/service_target_foundry.go`.

| Method | Behavior |
|---|---|
| `Initialize` | Validate the full Foundry schema on the service entry; ensure agent kinds, deploy-mode mutual exclusion, named toolbox/skill/connection references resolve. |
| `Package` | For each `config.agents.<>` with code (has `project:`), build per its `runtime:` (zip) or `docker:` (image). Internal fan-out across agents. |
| `Publish` | Push each agent's artifact (Foundry blob upload for zip; ACR push for image). |
| `Deploy` | (a) Reconcile project-level state -- deployments, connections, toolboxes, skills, routines, prompt agents -- via Foundry APIs. (b) For each agent (hosted or prompt), post `createAgentVersion` with the published artifact reference (where applicable). |
| `Endpoints` | Return the Foundry project endpoint URL plus the per-agent endpoints if discoverable. |
| `GetTargetResource` | Resolve the Foundry project's ARM resource. |

Logic for project-state reconciliation lifts out of the existing hook
handlers (`postprovisionHandler` and friends in
[`listen.go:46-57`](https://github.com/Azure/azure-dev/blob/main/cli/azd/extensions/azure.ai.agents/internal/cmd/listen.go#L46)).

### 4. Update `azd ai agent init`

Generate the consolidated `azure.yaml` with one `host: microsoft.foundry`
service entry. Stop emitting `agent.yaml` / `agent.manifest.yaml`. The
~200 lines in `internal/cmd/init.go` (`extractToolboxAndConnectionConfigs`
line 3329, `extractConnectionConfigs` line 3531) collapse into "write
directly to the Foundry service's top-level fields."

### 5. Deprecation fallback

One deprecation window: detect `agent.yaml` / `agent.manifest.yaml` next
to `azure.yaml`, print a warning via `output.WithWarningFormat`, continue
to read them and produce the equivalent in-memory `microsoft.foundry`
service-target, emit telemetry to track migration decay. After the window,
remove. Rename or repurpose `exterrors.CodeInvalidAgentManifest` if it
becomes meaningless.

### 6. Built-in Bicep for Foundry project provisioning

`azd provision` should not require an `infra/` directory or Bicep on disk
for a Foundry-only project. Carry templates inside the extension binary,
generate in-memory at provision time. Modeled after the `azd compose`
pattern. Developers who want IaC on disk run `azd infra gen` (or
equivalent) -- separate RFC for the generation mechanism.

## Sibling extension impact

The existing per-resource extensions
(`azure.ai.toolboxes`, `azure.ai.connections`, `azure.ai.projects`,
`azure.ai.skills`, `azure.ai.routines`, bundled by `microsoft.foundry`)
own data-plane CLIs (`azd ai toolbox`, `azd ai connection`, ...) that act
on a live Foundry project. None of them participate in `azure.yaml` today
and that does not have to change.

Two options for schema/reconciliation ownership of the new
`microsoft.foundry.json` slices:

| Option | Description | Trade-off |
|---|---|---|
| **A** | `azure.ai.agents` owns the full schema in v1; siblings keep their data-plane CLIs only | Simplest, fastest to ship. One extension reconciles everything. |
| **B** | Schema is owned by the `microsoft.foundry` meta-extension; per-resource extensions register slice contributions | Cleaner thematic alignment but a new "extension contributes a slice of another extension's schema" composition mechanism is itself new core work. |

**Recommendation: A for v1**, then re-evaluate B after the new shape is in
users' hands.

## Missing functionality (concrete gaps to build)

| Area | What is missing | Where |
|---|---|---|
| azd core | JSON Schema conditional for `host: microsoft.foundry` composing the extension schema at service level (with project/runtime/docker/image/config disabled) | `schemas/v1.0/azure.yaml.json` |
| azd core | (Optional, 3b only) Sub-service concept for nested code-bearing units inside a service-target | `pkg/project/*` |
| azd core | `${{...}}` preservation in `ExpandableString.Envsubst` (or convention if extension owns expansion) | `pkg/osutil/expandable_string.go:29-30` |
| `azure.ai.agents` | `microsoft.foundry.json` schema (new) | `cli/azd/extensions/azure.ai.agents/schemas/microsoft.foundry.json` |
| `azure.ai.agents` | `microsoft.foundry` service-target with internal per-agent fan-out for Package/Publish/Deploy | `internal/project/service_target_foundry.go` (new) |
| `azure.ai.agents` | Consolidated `init` flow; remove `agent.yaml` / `agent.manifest.yaml` emission | `internal/cmd/init.go` (especially lines 3329, 3531) |
| `azure.ai.agents` | Built-in Bicep for Foundry project (azd compose pattern) | new |
| `azure.ai.agents` | Skills schema + reconciliation | new (depends on skills schema decision) |
| `azure.ai.agents` | Routines schema + reconciliation | new (depends on routines schema decision) |
| `azure.ai.agents` | Deprecation fallback path + telemetry for `host: azure.ai.agent` and old files | `internal/cmd/init.go`, `internal/project/service_target_agent.go`, telemetry call sites |
| Tooling | Foundry Toolkit for VS Code parser switch from `agent.yaml` to `azure.yaml` | Toolkit team, not in this repo |
| Composition (#8049) | `azd ai project add connection\|model\|toolbox\|skill\|agent` command family writing directly to the Foundry service's top-level fields | new commands, shared YAML-edit engine |

## Open questions (decisions the team needs to make)

1. **Host kind name.** `microsoft.foundry` (used here, matches the existing
   meta-extension name) vs `azure.ai.foundry` vs `azure.ai.project` (closer
   to the Foundry product name). Locks in once shipped.
2. **Schema ownership (Options A/B above).** Recommend A for v1.
3. **Per-agent build orchestration (3a vs 3b above).** Recommend 3a for
   v1; revisit 3b if per-agent observability becomes a pain point.
4. **Per-agent CLI addressability.** Standard `azd deploy <name>`
   addresses the whole Foundry project, not individual agents. Is that OK
   as the long-term model with the extension CLI filling the per-agent
   gap (`azd ai agent deploy <name>`), or do we need core to expose
   sub-service deploy targets? Tied to question 3.
5. **Skill `instructions:` format.** Inline string only, file path only,
   or both? File paths are git-diff friendly; inline strings are simpler
   for single-prompt skills. The complex branch uses both forms.
6. **Routines schema.** Does it live in `azure.ai.routines` or
   `azure.ai.agents`? Trigger schema beyond `type: schedule, cron: ...`?
   Event triggers? Webhook triggers? The sample uses a minimal cron-only
   shape -- needs validation against the existing `azure.ai.routines`
   extension and the Foundry product spec.
7. **Idempotency / state management.** When `azd deploy` runs repeatedly,
   does the Foundry service-target diff declared state against live Foundry
   state and apply incremental changes, or recreate? When a user removes
   an entry from the Foundry service, does the next deploy delete it from
   Foundry?
   **Recommendation: Bicep-like semantics: "drop from config = stop using,
   not destroy"** (consistent with #8049). Destructive operations route
   through `azd down` or per-resource `az` CLI commands. Needs explicit
   doc and tests.
8. **Partial-failure recovery.** The Foundry service-target creates 4
   toolboxes, then a connection fails, then one agent's container build
   fails. Per-agent fan-out means partial state. What does re-running
   `azd deploy` do? Idempotent upsert -- confirm with Foundry API
   contracts (some create calls may not be idempotent).
9. **Foundry Toolkit cutover timing.** Toolkit currently reads
   `agent.yaml`. When does it switch to `azure.yaml`? Affects deprecation
   window length and whether v1 must ship a working fallback.
10. **`azd up` ordering with non-Foundry services.** The Foundry service
    deploys before any service that `uses:` it (standard azd ordering --
    no new logic). The complex branch's `webapp` exercises this.

## Phasing

| Phase | Scope | Blockers |
|---|---|---|
| 1 -- Unification | New `host: microsoft.foundry`; `microsoft.foundry.json` schema; new service-target with internal fan-out; consolidated init; deprecation fallback for old `agent.yaml` / `agent.manifest.yaml` AND old `host: azure.ai.agent`; built-in Bicep | none -- can start once core change 1 lands |
| 2 -- Composition (#8049) | `azd ai project add` command family with shared YAML-edit engine | Phase 1 |
| 3 -- Cleanup | Remove `agent.yaml` / `agent.manifest.yaml` parser support; remove `host: azure.ai.agent`; Toolkit cutover; rename `CodeInvalidAgentManifest` | Phase 1+2 live; telemetry shows decay; Toolkit ships parser switch |

## Related links

* [#7962 -- Unify Foundry agent configuration in azure.yaml](https://github.com/Azure/azure-dev/issues/7962)
* [#8049 -- Add connections, models, tools, and skills to Foundry Agent projects after init](https://github.com/Azure/azure-dev/issues/8049)
* [`azure.ai.agents` extension](https://github.com/Azure/azure-dev/tree/main/cli/azd/extensions/azure.ai.agents)
* [`azure.ai.projects` extension](https://github.com/Azure/azure-dev/tree/main/cli/azd/extensions/azure.ai.projects)
* [Reference Foundry samples (today's shape)](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/agent-framework/responses)
* [`azure.yaml` JSON Schema](https://github.com/Azure/azure-dev/blob/main/schemas/v1.0/azure.yaml.json)
