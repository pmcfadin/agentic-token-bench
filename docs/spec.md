# agentic-token-bench

Everything counts in large amounts. 

## Purpose

`agentic-token-bench` is an open benchmark and plugin framework for measuring how external tools reduce token usage in agentic programming workflows **without reducing correctness**.

The project exists to answer a practical question:

**Which tools and routing patterns actually reduce context consumption across real coding tasks, and when should an agent use them?**

This project will benchmark and package tools that reduce token waste across the full agent loop, including:

* **Retrieval minimization** tools (example: QMD)
* **CLI output compression** tools (example: RTK)
* **Mechanical transformation** tools (example: fastmod, ast-grep, comby)
* **Repo discovery / search** tools
* **Validation / diff summarization** plugins

The output of the project is not just benchmark data. It is also a reusable set of:

* **Plugins** that people can wire into their own agent tooling
* **Routing rules** for when to use each plugin
* **Reference benchmark tasks** to compare approaches fairly
* **Published findings** showing where token savings are real vs fake

---

## Vision

Build the reference open project for **token-efficient agentic coding infrastructure**.

The repo should help people answer:

* Where are tokens being wasted?
* Which tool should handle which class of work?
* How much do these tools actually save?
* What are the correctness tradeoffs?
* How should these tools be composed into a real coding-agent stack?

---

## Non-Goals

This project is **not**:

* a benchmark of language models against each other
* a generic coding benchmark with no focus on context efficiency
* a repo of random agent tools with no measurement discipline
* a replacement for semantic reasoning by the model

The goal is to measure and package **context-saving infrastructure**.

---

## Core Principles

### 1. Correctness beats token savings

A tool that saves tokens but causes bad edits, hidden breakage, or repeated repair loops is not actually winning.

### 2. Routing matters more than any single tool

The biggest gains will come from choosing the right mechanism for the right kind of task.

### 3. Measure full-task efficiency, not just prompt size

Token savings must be evaluated across the full loop:

* discovery
* retrieval
* execution
* transformation
* validation
* repair

### 4. Publish reusable artifacts

Every benchmarked technique should ideally produce a reusable plugin, spec, or routing rule others can adopt.

### 5. Prefer real workflows over toy examples

Use controlled tasks, but anchor them in real repositories and realistic coding-agent workflows.

---

## Problem Taxonomy

The benchmark organizes token waste into five categories.

### A. Discovery Waste

The agent opens too many files or reads too much repo structure just to locate the relevant area.

Examples:

* repeated `find`, `ls`, `tree`, `rg`, and file opens
* reading many files to locate one implementation
* scanning too much repo metadata

### B. Retrieval Waste

The agent pulls large docs, notes, markdown, or code chunks into context when only a few passages matter.

Examples:

* long internal docs
* giant README files
* design docs and issue threads
* oversized code excerpts

### C. Execution-Output Waste

The agent consumes large amounts of terminal output that contain mostly noise.

Examples:

* test output
* compiler output
* git diff/status output
* grep matches
* stack traces
* logs

### D. Transformation Waste

The agent manually performs repetitive edits that could be expressed once and executed mechanically.

Examples:

* broad string replacement
* repeated call-site rewrites
* import changes
* config key migrations

### E. Validation Waste

The agent re-reads huge diffs, large logs, or broad test output to determine whether a change worked.

Examples:

* giant diffs when only a few hunks matter
* rerunning full suites unnecessarily
* repeated manual comparison of expected vs actual changes

---

## Project Goals

### Goal 1: Benchmark token-saving tools

Measure the real impact of tools that reduce token consumption in one or more taxonomy categories.

### Goal 2: Publish reusable plugins

Wrap promising tools behind a stable plugin interface so people can use them in their own coding systems.

### Goal 3: Publish routing guidance

Define decision rules for agents and humans so the right mechanism is chosen for the task.

### Goal 4: Produce reproducible benchmark scenarios

Create a task suite with fixed repos, fixed tasks, fixed validation, and repeatable measurement.

### Goal 5: Create an open findings repo

Publish charts, interpretations, caveats, and recommended agent design patterns.

---

## Primary Users

### 1. Builders of coding agents

People creating assistants, shells, plugins, or orchestration layers for software engineering.

### 2. Tooling authors

People building utilities that reduce token usage or context transfer.

### 3. Engineering teams using coding agents

Teams that want to lower cost, improve speed, and reduce agent noise.

### 4. Researchers and evaluators

People comparing agent workflows with measurement discipline.

---

## High-Level Architecture

The project has four major layers:

### 1. Benchmark Layer

Defines repos, tasks, models, runs, metrics, and result collection.

### 2. Plugin Layer

Provides standard wrappers around token-saving tools.

### 3. Routing Layer

Contains rules and strategies that decide when a plugin should be used.

### 4. Reporting Layer

Generates charts, summaries, docs, and publishable findings.

---

## Functional Requirements

## 1. Benchmark Harness

The system must:

* define benchmark tasks in a structured format
* run the same task across multiple strategies
* capture token and non-token metrics consistently
* record artifacts from every run
* support repeated runs for comparison
* allow controlled repo setup from fixed commits
* support pluggable execution backends later

### Required benchmark inputs

Each benchmark task must define:

* task id
* task title
* repo source
* pinned commit
* category
* task description
* expected transformation type
* allowed tools / strategies
* success criteria
* validation commands
* optional human review notes

### Required benchmark outputs

Each run must emit:

* run id
* task id
* strategy id
* model / agent configuration
* plugin configuration
* start and end timestamps
* token metrics
* file read metrics
* file change metrics
* validation results
* pass/fail state
* repair iteration count
* artifact paths

---

## 2. Plugin Framework

The project must provide a plugin interface so external tools can be evaluated consistently.

A plugin represents a token-minimizing tool or layer that can be used by an agent workflow.

### Plugin categories

* retrieval plugins
* output compression plugins
* transformation plugins
* discovery plugins
* validation plugins

### Required plugin capabilities

Every plugin should declare:

* plugin id
* plugin category
* supported languages or formats
* token-waste class addressed
* required dependencies
* invocation contract
* expected inputs
* expected outputs
* failure modes
* validation notes

### Example plugins in scope for v1

* `qmd` retrieval plugin
* `rtk` shell-output compression plugin
* `fastmod` transformation plugin
* `ast-grep` transformation plugin
* `comby` transformation plugin
* `ripgrep` discovery plugin

---

## 3. Routing Engine

The routing layer decides which plugin or strategy should be used for a given task shape.

### Routing responsibilities

* classify task subtype
* recommend plugin usage
* avoid using mechanical tools on semantic tasks
* choose validation depth based on task risk
* prefer low-context mechanisms when appropriate

### Example routing decisions

* text-only repeated replacement -> `fastmod`
* syntax-shaped multi-file rewrite -> `ast-grep`
* doc lookup -> `qmd`
* noisy command output -> `rtk`
* high-risk semantic refactor -> agent reasoning first, plugins only as helpers

The routing engine should be configurable and publishable as logic users can adopt in their own tooling.

---

## 4. Reporting

The system must generate both machine-readable and human-readable output.

### Machine-readable outputs

* JSON run records
* CSV metric exports
* task manifests
* plugin manifests

### Human-readable outputs

* benchmark summaries
* markdown reports
* comparison tables
* charts
* routing recommendations
* failure analysis notes

---

## Benchmark Scenarios

## Scenario 1: Retrieval Minimization

Measure whether indexed retrieval reduces tokens required to answer coding or repo questions.

### Example comparison

* baseline: raw file reads and grep
* variant: `qmd`

### Metrics of interest

* total tokens
* files opened
* retrieved chunk size
* answer correctness
* time to correct answer

---

## Scenario 2: CLI Output Compression

Measure whether compressing terminal output lowers token cost without hiding critical information.

### Example comparison

* baseline: raw shell output
* variant: `rtk`

### Metrics of interest

* shell-output tokens delivered to model
* correctness of resulting decisions
* missed critical errors
* time to resolution

---

## Scenario 3: Mechanical Transformations

Measure whether transformation tools reduce token use on repetitive code changes.

### Example comparison

* baseline: direct agent editing
* variants: `fastmod`, `ast-grep`, `comby`

### Metrics of interest

* files opened
* total tokens
* changed files
* correctness of final diff
* validation pass rate
* repair loop count

---

## Scenario 4: End-to-End Tasks

Measure full-task efficiency when multiple plugins are combined.

### Example comparison

* baseline: plain agent
* variant: agent + routing + plugins

### Metrics of interest

* total tokens per successful task
* total wall-clock time
* first-pass success rate
* validation failures
* total repair cost

---

## Repositories for Benchmarking

The benchmark should support multiple real repos, ideally from different ecosystems.

### v1 suggested repos

* Apache Cassandra (Java)
* a TypeScript/React repo
* a Python repo
* an optional Rust repo

### Repo requirements

* real-world size
* active codebase shape
* clear validation commands
* suitable task opportunities
* permissive enough for benchmark use

---

## Metrics

## Primary metrics

* total input tokens
* total output tokens
* total tokens
* files opened
* lines read
* raw bytes read
* files changed
* diff size
* elapsed time
* validation pass/fail
* first-pass success
* repair iteration count

## Derived metrics

* tokens per successful task
* tokens per changed file
* tokens per validated success
* files read per changed file
* repair-cost ratio
* compression ratio for shell output
* retrieval reduction ratio

## Quality metrics

* correctness score
* human review score
* false-positive rate
* missed-error rate
* rollback requirement rate

---

## Success Criteria

The project is successful if it can show, with reproducible evidence:

1. which tool classes reduce token consumption in which task classes
2. where token savings do not hold up due to correctness failures
3. how routing improves end-to-end agent efficiency
4. how people can adopt the plugins independently of the benchmark

---

## Plugin API Spec (v1)

The plugin system should be simple and practical.

### Plugin manifest

Each plugin must provide a manifest with:

* `id`
* `name`
* `version`
* `category`
* `description`
* `inputs`
* `outputs`
* `dependencies`
* `supported_languages`
* `waste_classes`
* `risk_level`

### Plugin execution contract

Each plugin invocation should accept:

* task context
* target paths or resources
* plugin-specific parameters
* optional dry-run flag
* optional validation flag

Each plugin invocation should return:

* status
* summary
* structured outputs
* metrics
* warnings
* artifact paths

### Plugin design rules

Plugins should:

* be composable
* support dry-run where applicable
* emit structured metrics
* preserve enough detail for validation
* fail clearly
* avoid hiding critical information

---

## Skills vs Plugins

The project should explicitly separate **skills** from **plugins**.

### Skills

Skills are decision and workflow patterns.
They describe:

* when to use a tool
* when not to use it
* how to validate
* how to recover from failure

### Plugins

Plugins are executable integrations.
They perform:

* retrieval
* compression
* transformation
* summarization
* validation helpers

### Principle

Skills tell the system **what to do**.
Plugins do the work.

This project prioritizes plugins, with skills layered on top.

---

## Proposed Repository Structure

```text
agentic-token-bench/
  README.md
  LICENSE
  docs/
    vision.md
    methodology.md
    taxonomy.md
    routing-guide.md
    findings.md
  benchmarks/
    tasks/
    repos/
    scenarios/
    harness/
    results/
  plugins/
    qmd/
    rtk/
    fastmod/
    ast-grep/
    comby/
    ripgrep/
  skills/
    retrieval-routing/
    shell-output-routing/
    mechanical-transform-routing/
    end-to-end-routing/
  schemas/
    task.schema.json
    run.schema.json
    plugin.schema.json
  scripts/
  charts/
  examples/
```

---

## v1 Scope

Version 1 should stay tight.

### In scope

* taxonomy and methodology docs
* benchmark harness skeleton
* plugin interface spec
* 3 to 6 initial plugins
* 8 to 12 benchmark tasks
* 2 to 4 benchmark repos
* initial charts and findings
* routing rules for common cases

### Out of scope for v1

* broad model-vs-model comparisons
* production-grade UI
* full autonomous orchestration
* dozens of plugins
* fully automatic semantic correctness grading

---

## v1 Candidate Deliverables

1. Repo initialized with spec and schemas
2. Plugin manifest and execution interface
3. Task manifest format
4. Benchmark runner CLI
5. Initial plugins:

   * `qmd`
   * `rtk`
   * `fastmod`
   * `ast-grep`
6. Initial benchmark tasks
7. Result capture and chart generation
8. First findings report
9. Initial skills/routing docs

---

## Risks

### 1. Token metrics may be hard to compare across agents

Mitigation: pin model, runner, prompt template, and task definitions for core benchmark runs.

### 2. Tools may save tokens but increase hidden failure

Mitigation: emphasize validation, correctness scoring, and repair-cost measurement.

### 3. Repo selection may bias results

Mitigation: use multiple ecosystems and task categories.

### 4. Plugin interface may be too abstract

Mitigation: keep v1 minimal and driven by actual tools.

### 5. The project may sprawl

Mitigation: keep v1 tightly scoped and publishable.

---

## Open Questions

* What execution backend will drive benchmark runs in v1?
* What exact token accounting method will be the source of truth?
* How should human review scoring be normalized?
* Should plugins run through a shared local CLI wrapper?
* How much of the benchmark should be deterministic vs assisted by a live model?

---

## Immediate Next Steps

1. Finalize taxonomy and plugin API
2. Define JSON schemas for tasks, runs, and plugins
3. Pick v1 repos and candidate tasks
4. Build the benchmark runner skeleton
5. Implement first plugin wrappers
6. Run a small pilot benchmark
7. Refine based on pilot results
8. Publish first working results

---

## Proposed Tagline

**Measure, route, and package the tools that make agentic coding cheaper and sharper.**
