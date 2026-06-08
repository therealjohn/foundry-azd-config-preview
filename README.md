# foundry-azd-config-preview

A file-shape reference for the **unified `azure.yaml`** proposal that
consolidates Foundry agent project configuration. Pairs with the open RFCs:

* [Azure/azure-dev#7962](https://github.com/Azure/azure-dev/issues/7962) -- Unify Foundry agent configuration in `azure.yaml`
* [Azure/azure-dev#8049](https://github.com/Azure/azure-dev/issues/8049) -- Composition commands (`azd ai project add ...`)

The CLI changes that produce these files have not shipped. The Python in the
sample branches is illustrative -- it would compile and run against a real
Foundry endpoint, but most logic is stubbed.

## Branches

| Branch | Demonstrates |
|---|---|
| [`simple`](../../tree/simple) | One hosted agent + one model deployment. ~35-line `azure.yaml`. The minimum a Foundry project can be. |
| [`complex`](../../tree/complex) | Multi-agent platform: hosted + prompt agents, both `runtime:`/`docker:` deploy modes, toolboxes with web search / code interpreter / MCP / Azure AI Search, three connection types (incl. `${{...}}` server-side resolution), 3 model deployments, 2 file-backed skills, a scheduled routine, and a non-Foundry Container Apps frontend that consumes the agents. |

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
* Multiple agents that need to share a toolbox cannot: toolboxes live nested
  under a single agent's `config:` today.

The deeper structural mismatch: `azure.yaml` was designed for Azure services
modeled as ARM/Bicep resources. Foundry's project-scoped state (toolboxes,
connections, model deployments, skills, agents) is **data-plane** -- created
and reconciled via Foundry APIs, not ARM. Stretching `services:` to fit this
(e.g. #7962's earlier `host: azure.ai.project` "service without code"
proposal) works but conflates two different things.

## Architectural decisions (from plan-mode discussion)

| Decision | Choice | Why |
|---|---|---|
| Scope | Foundry-specific changes to azd core, not a generic data-plane primitive | Smaller blast radius. Foundry team owns the new section's schema. Re-evaluate generalization later if other extensions need it. |
| Where Foundry state lives in `azure.yaml` | New top-level `foundry:` section | Acknowledges data-plane state is structurally different from `services:`. Avoids the "service without code" pretense. |
| Where agent definitions live | All in `foundry.agents.<name>` (hosted and prompt) | One uniform mental model. Both go through the same `createAgentVersion` API contract. |
| Where code/build/deploy lives | Existing `services:`, only when an agent has code | `services:` already does this well. Don't reinvent. Prompt agents have no entry. |
| Link between agent definition and backing service | **L2**: service-first. `services.<>.host: azure.ai.agent` + `services.<>.config.agent: <foundry-agent-name>` | Smallest azd core delta. Matches how `host:` already works. `agent:` field lives inside the extension-owned `config:` map -- no new top-level `ServiceConfig` field. |
| Lifecycle | **D**: extension synthesizes a project-level service-target internally from the `foundry:` block | Reuses existing service-target plumbing (ordering, telemetry, hooks). User never writes `host: azure.ai.project`. No new user-facing verb. |
| Templating | `${VAR}` keeps existing semantics; `${{...}}` is preserved verbatim through azd expansion (Foundry server-side resolution) | Two distinct resolvers (azd client-side vs Foundry server-side) need to coexist without stepping on each other. |
| Bicep on disk | Opt-in, not default | Extension carries built-in Bicep internally (the `azd compose` pattern) for Foundry project provisioning. `azd infra gen` ejects to disk when explicit IaC is required. |

## Required AZD core changes

### 1. Recognize `foundry:` at the top level of `azure.yaml`

* **Problem.** The new `foundry:` section needs schema authority (for editor
  IntelliSense and validation) and a defined location in the project model.
* **Proposal.** Add `foundry:` to `schemas/v1.0/azure.yaml.json` as a section
  whose value is `$ref`ed to the extension-published schema URL. Matches the
  existing pattern for `host: azure.ai.agent` `config:` block at
  [`schemas/v1.0/azure.yaml.json:380-384`](https://github.com/Azure/azure-dev/blob/main/schemas/v1.0/azure.yaml.json#L380-L384).
* **Current state.** `ProjectConfig.AdditionalProperties` (`pkg/project/project_config.go:43-44`,
  yaml `inline`) already captures unknown top-level keys, so **parsing
  `foundry:` works today with zero core change**. The gap is purely the
  published JSON Schema entry for IntelliSense/validation.
* **Risk / alternative.** None significant. Add the entry now even if other
  pieces lag.

### 2. Extension capability: synthesize a project-level service-target from a top-level section

* **Problem.** Lifecycle D needs the `azure.ai.agents` extension to register
  a "virtual" service-target -- one not declared in `services:` -- so the
  `foundry:` block gets reconciled during `azd deploy` using the existing
  service-target plumbing (ordering, telemetry, hooks, failure semantics).
* **Proposal.** New extension capability declaration in `extension.yaml`:
  ```yaml
  providers:
    - name: azure.ai.project          # synthesized; NOT user-declared
      type: project-service-target    # new type
      sourceSection: foundry          # top-level azure.yaml key this drives
  ```
  When azd loads the project, it constructs a synthetic `ServiceConfig` for
  each extension that declared a `project-service-target` whose
  `sourceSection` is present in `ProjectConfig.AdditionalProperties`. That
  synthetic service participates in deploy ordering normally (deploys before
  any `services:` entry that `uses:` it, or before all if implicit project
  scope). The extension implements
  `Initialize`/`Package`/`Publish`/`Deploy`/`Endpoints`/`GetTargetResource`
  with Package and Publish as no-ops (no source code, no artifact).
* **Current state.** Extensions register service-targets via
  `extensionHost.WithServiceTarget("azure.ai.agent", ...)` at
  `cli/azd/extensions/azure.ai.agents/internal/cmd/listen.go:40-42`, but
  every service-target today must be invoked via a user-declared
  `services.<name>` entry. No mechanism exists to synthesize one from a
  non-`services:` top-level section. The gRPC contract (`ServiceTargetProvider`)
  is fine as-is; the gap is the **registration + invocation glue** in azd
  core.
* **Risk / alternative.** A simpler fallback is **Lifecycle A**: extension
  does data-plane work in its existing `postprovision` hook (already wired
  at `listen.go:46-48`). Zero core change but timing is implicit, partial
  failure semantics are murky, and the section is invisible to azd's
  ordering/telemetry. Recommend D for the long-term contract, A as the
  shippable bridge if D slips.

### 3. Preserve `${{...}}` through azd's `${VAR}` expansion

* **Problem.** Foundry uses `${{connections.x.credentials.key}}` for
  server-side resolution. azd's existing envsubst path
  (`pkg/osutil/expandable_string.go:29-30`, backed by
  `github.com/drone/envsubst`) treats `$` as a sigil and may consume or
  corrupt the `${{...}}` pattern before it reaches the Foundry API.
* **Proposal.** Either (a) pre-process `${{...}}` to a sentinel before
  envsubst and restore after, or (b) introduce a `PreserveSyntax` option on
  `ExpandableString.Envsubst` that skips `${{...}}`. Apply only to
  extension-owned blobs (the `foundry:` section); existing call sites
  unchanged. Add tests against drone/envsubst's actual behavior.
* **Current state.** `ServiceConfig.Config` (`pkg/project/service_config.go:62-63`,
  `map[string]any`) is **not** expanded by azd core today -- extensions
  handle it. So this is only a concern for the `foundry:` top-level if azd
  core touches its contents. If extensions own all expansion of the
  `foundry:` block via the existing `drone/envsubst` package, they need to
  apply the same preservation rule. Either way, the extension(s) need a
  shared helper.
* **Risk / alternative.** If we keep all `foundry:` expansion inside the
  Foundry extension (azd core never touches the bytes), the gap collapses
  to "extension exposes a helper or the team agrees on a pre/post-process
  convention." Worth aligning before two extensions write divergent
  expanders.

### 4. (Open) Project-scoped extension `uses:` semantics

* **Problem.** Today `services.<>.uses:` orders one service before another
  and injects the dependency's outputs as env vars. The synthetic
  `azure.ai.project` service-target needs to deploy before any
  `azure.ai.agent` service that depends on the `foundry:` state. Two
  approaches:
  * **Implicit.** Any `host: azure.ai.agent` service implicitly depends on
    the synthesized project-level target.
  * **Explicit.** User adds `uses: [<synthetic-name>]` -- but the synthetic
    name is not in their `azure.yaml`, so they cannot.
* **Proposal.** Implicit. The extension knows which host kinds belong to it
  and declares the implicit dependency at registration time. This keeps the
  `foundry:` block invisible-but-correct.
* **Current state.** Implicit cross-service ordering doesn't exist;
  `uses:` is the only mechanism. Need a hook for extensions to inject
  ordering edges programmatically during project load.
* **Risk / alternative.** Punt and require the user to write `uses:
  [project]` against a reserved name. Less clean but works without core
  change.

## Required extension changes (`azure.ai.agents`)

### 1. Publish `foundry.json` schema

Owns: `deployments`, `connections`, `toolboxes`, `skills`, `routines`,
`agents`. Lives at
`cli/azd/extensions/azure.ai.agents/schemas/foundry.json`.
`additionalProperties: true` at the top level so new Foundry data-plane
resources (eval datasets, vector indexes, knowledge sources) can be added
without azd-side schema breaks. Referenced by `azure.yaml.json` from the
core repo.

### 2. Slim `azure.ai.agent.json` schema

Today's [`cli/azd/extensions/azure.ai.agents/schemas/azure.ai.agent.json`](https://github.com/Azure/azure-dev/blob/main/cli/azd/extensions/azure.ai.agents/schemas/azure.ai.agent.json)
carries `deployments`, `resources`, `toolConnections`, `toolboxes`,
`connections`. **All move to `foundry.json`.** What stays on the per-agent
service `config:` block:

* `agent: <name>` -- new L2 link field
* `container.resources` -- runtime container cpu/memory
* `startupCommand` -- (existing)
* `env` -- (existing, runtime container env)

Removed from `config:` (move to `foundry.agents.<name>`): `kind`, `protocols`,
`metadata`, `description`, `env` (the *agent-level* env -- container-level
env stays on `config:`), `toolboxes` (now references by name to
`foundry.toolboxes`).

### 3. Implement the project-level service-target

Wire a second `WithServiceTarget` in
[`listen.go:40-42`](https://github.com/Azure/azure-dev/blob/main/cli/azd/extensions/azure.ai.agents/internal/cmd/listen.go#L40)
(or whichever mechanism the new capability uses):

```go
host.
  WithServiceTarget("azure.ai.agent", ...).            // existing
  WithProjectServiceTarget("azure.ai.project", ...)    // new
```

`Deploy` reconciles `foundry:` state via Foundry APIs:

* Model deployments (currently env-var-serialized to Bicep)
* Connections (currently `preprovision`/`postprovision` hook handlers)
* Toolboxes (currently `provisionToolboxes()` in `postprovision`)
* Skills (new -- depends on schema; see open question)
* Routines (new -- depends on schema)
* Prompt agents (new -- no existing path)

Logic for the first three lifts out of the existing hook handlers
(`postprovisionHandler` and friends in `listen.go:46-57`) into the new
service-target. `Initialize` validates the schema. `Package`/`Publish` are
no-ops.

### 4. Update per-agent service-target to use the L2 link

`project.NewAgentServiceTargetProvider` (`cli/azd/extensions/azure.ai.agents/internal/project/service_target_agent.go`)
currently reads its definition from `ServiceConfig.Config`. After the
change it reads `config.agent: <name>` and looks up the definition from
the parsed `foundry.agents.<name>` entry on `ProjectConfig.AdditionalProperties`.

### 5. Update `azd ai agent init`

Generate the consolidated `azure.yaml` with `foundry:` + per-agent services
entries. Stop emitting `agent.yaml` and `agent.manifest.yaml`. The ~200
lines in `internal/cmd/init.go` (`extractToolboxAndConnectionConfigs` line
3329, `extractConnectionConfigs` line 3531) collapse into "write directly
to the `foundry:` block."

### 6. Deprecation fallback for old files

One deprecation window: detect `agent.yaml` / `agent.manifest.yaml` next
to `azure.yaml`, print a warning via `output.WithWarningFormat`, continue
to read them, emit telemetry to track migration decay. After the window,
remove. Rename or repurpose `exterrors.CodeInvalidAgentManifest` if it
becomes meaningless.

### 7. Built-in Bicep for Foundry project provisioning

`azd provision` should not require an `infra/` directory or Bicep on disk
for a Foundry-only project. Carry templates inside the extension binary,
generate in-memory at provision time. Modeled after the `azd compose`
pattern. Developers who want IaC on disk run `azd infra gen` (or
equivalent) -- separate RFC for the generation mechanism.

## Sibling extension impact

The existing per-resource extensions
(`azure.ai.toolboxes`, `azure.ai.connections`, `azure.ai.projects`,
`azure.ai.skills`, `azure.ai.routines`, bundled by `microsoft.foundry`)
own data-plane CLIs (`azd ai toolbox`, `azd ai connection`, ...). Today
none of them participate in `azure.yaml`.

In the proposed model, the `foundry:` section spans concepts each of those
extensions arguably owns. Three options for schema/reconciliation ownership:

| Option | Description | Trade-off |
|---|---|---|
| **A** | `azure.ai.agents` owns the full `foundry.json` schema in v1; siblings keep their data-plane CLIs only | Simplest, fastest to ship. One extension reconciles everything. Tight coupling between agents and project-scoped concerns. |
| **B** | `azure.ai.projects` (thematic home for project-scoped state) takes ownership; logic moves out of `azure.ai.agents` | Cleaner alignment with extension names. More cross-extension migration. `azure.ai.projects` is currently endpoint-context-only -- needs more capability. |
| **C** | Each sibling contributes its slice (`azure.ai.toolboxes` owns `foundry.toolboxes`, etc.); a new aggregator extension or core mechanism composes them | Most modular, most coordination. Composition mechanism for a single top-level section across many extensions is itself a new core feature. |

**Recommendation: A for v1**, then re-evaluate B/C after the new shape is
in users' hands and we see how often the seams matter.

## Missing functionality (concrete gaps to build)

| Area | What is missing | Where |
|---|---|---|
| azd core | JSON Schema entry for top-level `foundry:` block | `schemas/v1.0/azure.yaml.json` |
| azd core | `project-service-target` registration mechanism for synthesizing services from top-level sections | `pkg/project/*`, `cli/azd/pkg/azdext/*` (gRPC contract addition) |
| azd core | Implicit ordering: extension-declared dependency from its service-targets to its project-service-target | service ordering / DAG construction |
| azd core | `${{...}}` preservation in `ExpandableString.Envsubst` (or convention if extension owns expansion) | `pkg/osutil/expandable_string.go:29-30` |
| `azure.ai.agents` | `foundry.json` schema (new) | `cli/azd/extensions/azure.ai.agents/schemas/foundry.json` |
| `azure.ai.agents` | Slimmed `azure.ai.agent.json` schema | existing file |
| `azure.ai.agents` | Project-level service-target implementation | `internal/project/*` |
| `azure.ai.agents` | Per-agent service-target reads `config.agent:` link from `foundry.agents` | `internal/project/service_target_agent.go` |
| `azure.ai.agents` | Consolidated `init` flow; remove `agent.yaml` / `agent.manifest.yaml` emission | `internal/cmd/init.go` (especially lines 3329, 3531) |
| `azure.ai.agents` | Built-in Bicep for Foundry project (azd compose pattern) | new |
| `azure.ai.agents` | Skills schema + reconciliation | new (depends on skills schema decision below) |
| `azure.ai.agents` (or sibling) | Routines schema + reconciliation | new |
| `azure.ai.agents` | Deprecation fallback path for old files + telemetry | `internal/cmd/init.go`, telemetry call sites |
| Tooling | Foundry Toolkit for VS Code parser switch from `agent.yaml` to `azure.yaml` | Toolkit team, not in this repo |
| Composition (#8049) | `azd ai project add connection|model|toolbox|skill|agent` command family | new commands, shared YAML-edit engine |

## Open questions (decisions the team needs to make)

1. **Top-level section name.** `foundry:` (used here, shortest, matches how
   the team talks about it) vs `foundryProject:` vs `aiFoundry:` vs
   `ai.foundry:` (closer to how other host kinds are namespaced). Locks in
   muscle memory once shipped.
2. **Schema ownership (Options A/B/C above).** Recommend A for v1.
3. **Skill `instructions:` format.** Inline string only, file path only, or
   both? File paths are git-diff friendly; inline strings are simpler for
   single-prompt skills. The complex branch uses both forms to illustrate.
4. **Routines.** Does the new schema live in `azure.ai.routines` or
   `azure.ai.agents`? What does the trigger schema look like beyond
   `type: schedule, cron: ...`? Event triggers? Webhook triggers?
   This sample uses a minimal cron-only shape -- needs validation against
   the existing `azure.ai.routines` extension's model and the Foundry
   product spec.
5. **L2 link discoverability.** Should `config.agent:` be promoted to a
   top-level `ServiceConfig` field (`services.<>.agent: <name>`) for
   discoverability and editor support, even though it costs a core schema
   change? Current proposal keeps it inside `config:` to minimize core
   delta. Probably worth promoting if other extensions ever need a similar
   "link to project-scoped declaration" pattern.
6. **"Mix of code" semantics.** Concretely: multiple services backing one
   agent? Code + prompts hybrid? A future kind we don't have a name for?
   The architecture allows multiple services to set `config.agent: <same-name>`
   today, but we have not specified what that *means* at deploy time.
   Surface a concrete use case before adding validation rules.
7. **Idempotency / state management.** When `azd deploy` runs repeatedly,
   does the project-level target diff `foundry:` against live Foundry state
   and apply incremental changes, or recreate? When a user removes an entry
   from `foundry:`, does the next deploy delete it from Foundry? **Plan
   recommends Bicep-like semantics: "drop from config = stop using, not
   destroy"** (consistent with #8049). Destructive operations route through
   `azd down` or per-resource `az` CLI commands. Needs explicit doc and
   tests.
8. **Partial-failure recovery.** Project-level deploy creates 4 toolboxes,
   then a connection fails. Per-agent deploys are blocked downstream. What
   does re-running `azd deploy` do? Plan recommends idempotent upsert -- but
   confirm with the Foundry API surface (some create calls may not be
   idempotent).
9. **Foundry Toolkit cutover timing.** Toolkit currently reads
   `agent.yaml`. When does it switch to `azure.yaml`? Affects deprecation
   window length and whether v1 must ship with a working fallback.
10. **`azd up` ordering with mixed services.** Synthesized project-level
    target deploys first (no source). Per-agent services after, in `uses:`
    order. Non-Foundry services keep their existing slot. Confirm this is
    what we want -- a Container Apps frontend that `uses:` the agents will
    correctly deploy last. The complex branch's `webapp` exercises this.

## Phasing

| Phase | Scope | Blockers |
|---|---|---|
| 1 -- Consolidation | New `foundry:` section, slim `azure.ai.agent.json`, project-level service-target, consolidated init, deprecation fallback, built-in Bicep | none -- can start once core change 1+2 is agreed |
| 2 -- Composition (#8049) | `azd ai project add` command family with shared YAML-edit engine | Phase 1 lands |
| 3 -- Cleanup | Remove `agent.yaml` / `agent.manifest.yaml` parser support; Toolkit cutover; rename `CodeInvalidAgentManifest` | Phase 1+2 live in users' hands; telemetry shows decay; Toolkit ships its parser switch |

## Related links

* [#7962 -- Unify Foundry agent configuration in azure.yaml](https://github.com/Azure/azure-dev/issues/7962)
* [#8049 -- Add connections, models, tools, and skills to Foundry Agent projects after init](https://github.com/Azure/azure-dev/issues/8049)
* [`azure.ai.agents` extension](https://github.com/Azure/azure-dev/tree/main/cli/azd/extensions/azure.ai.agents)
* [`azure.ai.projects` extension](https://github.com/Azure/azure-dev/tree/main/cli/azd/extensions/azure.ai.projects)
* [Reference Foundry samples (today's shape)](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/agent-framework/responses)
* [`azure.yaml` JSON Schema](https://github.com/Azure/azure-dev/blob/main/schemas/v1.0/azure.yaml.json)
