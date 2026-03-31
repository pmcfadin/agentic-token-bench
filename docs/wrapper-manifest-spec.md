# Wrapper Manifest Specification

Every tool wrapper ships a `manifest.yaml` file that sits alongside its `wrapper.py`.
The manifest is the single source of truth for a tool's identity and capabilities.
It is loaded at runtime by `tools.base.load_manifest` and returned as a `ToolManifest`
dataclass instance.

---

## File location

```
tools/<tool-id>/manifest.yaml
```

---

## Required fields

| Field         | Type   | Description                                                 |
|---------------|--------|-------------------------------------------------------------|
| `id`          | string | Stable, lowercase identifier used in traces and reports.    |
| `name`        | string | Human-readable display name.                                |
| `version`     | string | Semantic version of this wrapper (not the underlying tool). |
| `category`    | string | Functional category. See [Allowed values](#category).       |
| `description` | string | One-sentence description of what the tool does.             |

All five fields must be present and non-empty. A missing required field causes
`load_manifest` to raise `KeyError`.

---

## Optional fields

| Field                 | Type           | Default | Description                                                |
|-----------------------|----------------|---------|------------------------------------------------------------|
| `supported_languages` | list of string | `[]`    | Language identifiers, or `[any]` if language-agnostic.     |
| `waste_classes`       | list of string | `[]`    | Token-waste categories this tool targets.                  |
| `dependencies`        | list of string | `[]`    | System binaries or packages the wrapper shells out to.     |
| `risk_level`          | string         | `"low"` | Estimated risk of incorrect edits. See [Allowed values](#risk_level). |

---

## Allowed values

### `category`

Exactly one of:

| Value                | Meaning                                                                 |
|----------------------|-------------------------------------------------------------------------|
| `discovery`          | Locating files or symbols (e.g. search, indexing).                      |
| `retrieval`          | Fetching and returning document content.                                |
| `output_compression` | Reducing the volume of tool output delivered to the agent.              |
| `transformation`     | Rewriting or patching source code.                                      |
| `validation`         | Checking correctness of code or configuration without modifying it.     |

### `waste_classes`

Zero or more of:

| Value                    | Meaning                                                          |
|--------------------------|------------------------------------------------------------------|
| `discovery_waste`        | Unnecessary tokens spent exploring the codebase.                |
| `retrieval_waste`        | Unnecessary tokens spent reading file content.                  |
| `execution_output_waste` | Unnecessary tokens in command output piped back to the agent.   |
| `transformation_waste`   | Unnecessary tokens spent on redundant code rewrites.            |
| `validation_waste`       | Unnecessary tokens spent re-running or re-reading test output.  |

### `risk_level`

Exactly one of:

| Value    | Meaning                                                                    |
|----------|----------------------------------------------------------------------------|
| `low`    | Read-only or append-only; cannot corrupt existing source.                  |
| `medium` | Modifies files but changes are narrow and easily reviewed.                 |
| `high`   | Broad structural rewrites; requires human review before merging.           |

---

## Example manifest (annotated)

```yaml
# tools/example/manifest.yaml

# --- Required fields ---

# Stable identifier used in JSONL traces and benchmark reports.
# Use lowercase letters, digits, and hyphens only.
id: example-tool

# Human-readable name shown in the dashboard.
name: Example Tool

# Semantic version of this wrapper (not the upstream binary).
# Increment the patch when wrapper behaviour changes.
version: "0.1.0"

# Functional category — must be one of the five allowed values.
category: transformation

# One-sentence plain-English description.
description: Demonstrates every manifest field with realistic values.

# --- Optional fields ---

# Language tags this tool can handle. Use [any] if language-agnostic.
supported_languages: [java, python, typescript]

# Token-waste categories this tool is designed to reduce.
waste_classes: [transformation_waste]

# System binaries or pip packages that must be available at runtime.
dependencies: [example-tool]

# Estimated blast radius if the tool misidentifies a match.
# low | medium | high
risk_level: medium
```

---

## Validation

`load_manifest(path: Path) -> ToolManifest` in `tools/base.py` is the canonical
loader. It performs YAML parsing and field extraction but does not enforce the
allowed-value lists at load time — that is the responsibility of callers (e.g.
the test suite and the harness qualification step).

The test suite in `tests/test_tool_manifest.py` asserts allowed values for all
six shipped manifests and serves as the living validation reference.
