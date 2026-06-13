# Proposed schemas: `host: microsoft.foundry`

Per-resource JSON Schema files the `azure.ai.agents` extension would
publish to validate `host: microsoft.foundry` service entries in
`azure.yaml`. Proposed as a split-out replacement for today's monolithic
`cli/azd/extensions/azure.ai.agents/schemas/azure.ai.agent.json`, modeled
on the multi-file pattern used by
[microsoft/AgentSchema](https://github.com/microsoft/AgentSchema/tree/main/schemas/v1.0).

These are **mockup files**. Nothing here is wired into azd or any
extension; the chain below describes how they would compose once the
proposal lands.

## Layout

```
schemas/
├── README.md                    -- this file
├── microsoft.foundry.json       -- composes the per-resource schemas (the entry the azd core conditional $refs)
├── Deployment.json              -- model deployments
├── Connection.json              -- project connections
├── Toolbox.json                 -- toolboxes
├── Skill.json                   -- skills
├── Routine.json                 -- routines (scheduled / event-driven agent invocations)
├── Agent.json                   -- agents (hosted + prompt variants)
├── Evaluator.json               -- evaluators (builtin + custom)
├── Dataset.json                 -- datasets (local + remote)
├── EvaluationSuite.json         -- evaluation suites (dataset + evaluators + options)
└── FileRef.json                 -- the {$ref: ...} alternate shape for external file imports
```

This folder is **extension-side only**. The top-level `azure.yaml` schema
is owned by azd core
([`Azure/azure-dev/schemas/v1.0/azure.yaml.json`](https://github.com/Azure/azure-dev/blob/main/schemas/v1.0/azure.yaml.json)).
The proposal here is what the agents extension would publish; the only
change azd core needs is one new `if`/`then` block in its existing
`azure.yaml.json` that conditionally `$ref`s
[`microsoft.foundry.json`](./microsoft.foundry.json) when
`services.<>.host == "microsoft.foundry"`.

## Composition pattern

Each per-resource schema accepts either an inline definition or a `$ref`
to an external file. The schema declares this with `oneOf`:

```jsonc
{
  "oneOf": [
    { "$ref": "#/definitions/Inline" },
    { "$ref": "FileRef.json" }
  ]
}
```

Editors get autocomplete and validation for both forms. **Runtime
resolution of data-side `$ref:`** -- actually loading the referenced
file at deploy time -- is a separate extension feature (azd's YAML
parser does not import files today; see the discussion in
[`../README.md`](../README.md#required-azd-core-changes)).

## How the chain composes for an editor

1. The user's `azure.yaml` declares
   `# yaml-language-server: $schema=https://raw.githubusercontent.com/Azure/azure-dev/refs/heads/main/schemas/v1.0/azure.yaml.json`
   (azd core's existing schema).
2. The editor (VS Code with the Red Hat YAML extension, or any other
   JSON-Schema-aware YAML editor) fetches azd core's `azure.yaml.json`
   and validates the file's structure.
3. When `services.<>.host: microsoft.foundry`, the conditional in
   `azure.yaml.json` (added by the proposed PR to azd core) `$ref`s
   `microsoft.foundry.json` -- the file in **this folder**.
4. `microsoft.foundry.json` `$ref`s each per-resource sub-schema
   (`Deployment.json`, `Connection.json`, `Toolbox.json`, `Skill.json`,
   `Routine.json`, `Agent.json`) for its array items.
5. Each item schema offers `oneOf: [Inline, FileRef]`, so the user can
   write either form.

All of this is pure JSON Schema -- no runtime code. The chain works in
any editor with JSON Schema support.

## How this maps to a real PR

In `Azure/azure-dev`:

1. Add a `host: microsoft.foundry` conditional to
   [`schemas/v1.0/azure.yaml.json`](https://github.com/Azure/azure-dev/blob/main/schemas/v1.0/azure.yaml.json)
   alongside the existing `azure.ai.agent` block. The conditional
   `$ref`s the extension-published `microsoft.foundry.json`.
2. Move the per-resource sub-schemas into
   `cli/azd/extensions/azure.ai.agents/schemas/` and publish them at
   stable raw URLs (same pattern today's `azure.ai.agent.json` already
   uses).
3. Update the extension's config-load path to recognize
   `host: microsoft.foundry` and -- when the runtime resolver ships --
   to load files referenced by data-side `$ref:`.

## Convention precedent

The split-with-`$ref` pattern is the same one
[microsoft/AgentSchema](https://github.com/microsoft/AgentSchema/tree/main/schemas/v1.0)
already uses for the Foundry agent definition family
(`AgentManifest.yaml` -> `AgentDefinition.yaml`, `PropertySchema.yaml`,
`RecordResource.yaml`, etc.). Adopting it here keeps the Foundry tooling
family stylistically consistent.

## Trying it locally

Open `simple/azure.yaml` or `complex/azure.yaml` in VS Code with the
Red Hat YAML extension installed. Both files point at azd core's
existing `azure.yaml.json` via the `# yaml-language-server:` directive.
Until the `host: microsoft.foundry` conditional is added to azd core's
schema, the editor will validate the top-level structure (name,
services, etc.) but will NOT validate the Foundry-specific
`deployments` / `connections` / `toolboxes` / `agents` blocks. That's
expected -- the conditional is the one new line of azd core work the
proposal asks for, and once it lands the whole chain in this folder
lights up automatically.

The `complex` branch additionally demonstrates **data-side `$ref:`**
imports: several agent, toolbox, and skill definitions live in
sub-folders (`complex/agents/`, `complex/toolboxes/`, `complex/skills/`)
and the main `azure.yaml` references them by relative path. Each
extracted file has its own `# yaml-language-server:` directive pointing
at the matching per-resource schema in this folder, so editors validate
the standalone files directly.
