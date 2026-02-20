# Codraft — v2 Specification

**Version:** 0.2
**Date:** 2026-02-16
**Platform:** Claude Cowork
**Extends:** `codraft_mvp_spec.md` (v0.1)

---

## 1. Overview

v2 adds four capabilities to Codraft:

1. **Conditional logic** — templates can use `{% if %}` / `{% else %}` / `{% endif %}` to include or exclude sections based on variable values. The interview skips questions that aren't relevant.
2. **Loops** — templates can use `{% for item in items %}` / `{% endfor %}` for repeating sections. The interview collects lists with an "add another?" flow.
3. **Skill separation** — the monolithic SKILL.md is split into three focused skills: Orchestrator, Analyzer, and Renderer.
4. **Developer configuration** — an optional `config.yaml` file per template provides question overrides, grouping hints, validation rules, defaults, and choice types.

### 1.1 v2 Scope Constraints

These limits keep v2 tractable. They can be relaxed in v3.

- **Single-level nesting only** — no `{% for %}` inside `{% if %}`, or `{% if %}` inside `{% for %}`. Each block is top-level relative to the template body.
- **Two condition forms only**:
  - Truthiness: `{% if variable_name %}` — variable is truthy (boolean true, non-empty)
  - Equality: `{% if variable_name == 'value' %}` — variable equals a specific string
- **`{% else %}` supported, `{% elif %}` deferred** — `{% else %}` covers the common case. Multi-way branching via `{% elif %}` is deferred to v3.
- **No computed fields or expressions** — variables are always collected from the user, never calculated.

---

## 2. Architecture

### 2.1 Skill Separation

v2 splits the single SKILL.md into three skills:

| Skill | Location | Purpose | Triggered by |
|---|---|---|---|
| **Orchestrator** | `.claude/skills/codraft/SKILL.md` | Entry point. Discovery, interview, confirmation, post-render. | User ("prepare an NDA") |
| **Analyzer** | `.claude/skills/codraft-analyzer/SKILL.md` | Template parsing, variable extraction, manifest generation. | Orchestrator |
| **Renderer** | `.claude/skills/codraft-renderer/SKILL.md` | Docx/HTML rendering, output validation. | Orchestrator |

The Orchestrator is the only user-facing skill. It invokes the Analyzer and Renderer via prompt-level instructions (e.g., "Run the codraft-analyzer skill on this template directory").

### 2.2 Skill Interface Contracts

**Analyzer**
- **Input:** Template directory path (e.g., `templates/consulting_agreement/`)
- **Output:** `manifest.yaml` written to the template directory
- **Behaviour:** Checks cache validity first. If `config.yaml` is present, merges overrides into the manifest.

**Renderer**
- **Input:** Template path, format (`docx` or `html`), variable dictionary, output directory path
- **Output:** Rendered document(s) in a job folder under `output/`
- **Behaviour:** Renders, validates output for unfilled placeholders, reports results.

**Orchestrator**
- **Input:** User's natural language request
- **Output:** Completed document(s)
- **Behaviour:** Discovery → Analyze → Interview Plan → Interview Loop → Confirmation → Render → Post-Render

---

## 3. Manifest v2 Schema

The manifest is the single source of truth the Orchestrator reads. The Analyzer produces it. The Orchestrator never reads `config.yaml` directly — config overrides are merged into the manifest by the Analyzer.

### 3.1 Full Schema

```yaml
# ── Metadata ──────────────────────────────────────────────
schema_version: 2
template: "consulting_agreement.docx"
template_path: "templates/consulting_agreement/consulting_agreement.docx"
format: docx                    # "docx" or "html"
analyzed_at: "2026-02-16T10:30:00Z"
variable_count: 12              # total unique variables (all scopes)

# ── From config.yaml (optional, passthrough) ──────────────
meta:                           # present only if config.yaml provides it
  display_name: "Consulting Agreement"
  description: "Standard consulting engagement agreement"

# ── Unconditional variables ───────────────────────────────
# Always collected during interview.
variables:
  - name: client_name
    label: "Client Name"
    type: text
    # Optional fields (from config.yaml merge):
    # question: "What is the client's full legal name?"
    # description: "The legal entity or individual name"
    # default: ""
    # required: true
    # format_hint: "Full legal name as registered"

  - name: payment_method
    label: "Payment Method"
    type: choice               # new type in v2
    choices:                   # required when type is "choice"
      - bank_transfer
      - cheque
      - crypto
    # question: "How will the consultant be paid?"
    # default: "bank_transfer"

  - name: effective_date
    label: "Effective Date"
    type: date

# ── Conditional blocks ────────────────────────────────────
# Variables gated by {% if %} / {% else %} blocks.
# Asked only if the condition evaluates to true/false.
conditionals:
  - condition: "include_ip_assignment"       # truthiness test
    gate_type: boolean                       # "boolean" or "equality"
    if_variables:
      - name: ip_ownership_entity
        label: "IP Ownership Entity"
        type: text
      - name: ip_assignment_date
        label: "IP Assignment Date"
        type: date
    else_variables: []                       # populated if {% else %} block has variables

  - condition: "payment_method == 'bank_transfer'"   # equality test
    gate_type: equality
    gate_variable: payment_method            # which variable to check
    gate_value: "bank_transfer"              # what value triggers the if-branch
    if_variables:
      - name: bank_name
        label: "Bank Name"
        type: text
      - name: account_number
        label: "Account Number"
        type: text
    else_variables: []

# ── Loop blocks ───────────────────────────────────────────
# Variables inside {% for %} blocks. Collected as lists.
loops:
  - loop_var: "milestone"                    # iteration variable name
    collection: "milestones"                 # collection variable name
    label: "Project Milestone"               # human-readable label for the loop
    min_items: 1                             # minimum items required (default: 1)
    variables:                               # sub-variables per item
      - name: description
        label: "Description"
        type: text
      - name: date
        label: "Due Date"
        type: date
      - name: amount
        label: "Amount"
        type: number

# ── Dependencies (pre-computed) ───────────────────────────
# Gate variable → list of dependent variable names.
# Used by the Orchestrator to quickly determine which
# questions to skip without re-parsing conditions.
dependencies:
  include_ip_assignment:
    - ip_ownership_entity
    - ip_assignment_date
  payment_method:
    - bank_name
    - account_number

# ── Interview groups (optional) ───────────────────────────
# If present (from config.yaml), the Orchestrator uses these
# groups instead of auto-grouping. If absent, the Orchestrator
# groups variables by logical affinity as in v1.
groups:
  - name: "Parties"
    variables: [client_name, client_address, consultant_name, consultant_address]

  - name: "Engagement Terms"
    variables: [effective_date, scope_of_work, payment_method]

  - name: "IP Assignment"
    condition: include_ip_assignment         # conditional group
    variables: [ip_ownership_entity, ip_assignment_date]

  - name: "Bank Details"
    condition: "payment_method == 'bank_transfer'"
    variables: [bank_name, account_number]

  - name: "Milestones"
    loop: milestones                         # loop group
    variables: [description, date, amount]

# ── Validation rules (optional, from config.yaml) ────────
validation:
  - rule: "end_date > effective_date"
    message: "The end date must be after the effective date"
```

### 3.2 Schema Notes

**`schema_version`** — Always `2` for v2 manifests. The Analyzer regenerates the manifest if it encounters a v1 manifest (which has no `schema_version` field).

**Backward compatibility** — Templates with no conditionals or loops produce a v2 manifest with empty `conditionals: []` and `loops: []`. The Orchestrator treats this identically to v1 behaviour.

**Variable fields reference:**

| Field | Source | Required | Description |
|---|---|---|---|
| `name` | Analyzer | Yes | Variable name as it appears in the template |
| `label` | Analyzer (auto) or config | Yes | Human-readable label |
| `type` | Analyzer (inferred) or config | Yes | `text`, `date`, `number`, `email`, `phone`, `boolean`, `choice` |
| `question` | config only | No | Custom interview question |
| `description` | config only | No | Context for Claude when asking the question |
| `default` | config only | No | Default value (special: `"today"` for dates) |
| `required` | config only | No | Whether the variable must have a value (default: `true`) |
| `format_hint` | config only | No | Format guidance shown to user (e.g., "DD/MM/YYYY") |
| `choices` | config only | When type=choice | List of valid values |
| `validation` | config only | No | Validation rules (`min`, `max` for numbers) |

**New types in v2:**

| Type | Description | Interview behaviour |
|---|---|---|
| `boolean` | True/false value | Yes/no question |
| `choice` | One of a fixed set of values | Present options, validate against `choices` list |

---

## 4. Developer Configuration (`config.yaml`)

### 4.1 Purpose

An optional YAML file placed alongside the template by the template developer. It overrides the Analyzer's auto-inferred values and controls the interview flow. If absent, the Analyzer and Orchestrator use their default behaviours.

### 4.2 Full Format

```yaml
# ── Template metadata ─────────────────────────────────────
meta:
  display_name: "Consulting Agreement"       # shown to user during discovery
  description: "Standard consulting engagement agreement with optional IP assignment"
  category: "contracts"                      # reserved for v3 categorisation

# ── Variable overrides ────────────────────────────────────
# Keys are variable names from the template.
# Any field here overrides the Analyzer's auto-inferred values.
variables:
  client_name:
    label: "Client's Legal Name"
    question: "What is the client's full legal name as it should appear in the agreement?"
    description: "The legal entity or individual name of the client"
    default: ""
    required: true
    format_hint: "Full legal name as registered"

  effective_date:
    question: "When should this agreement take effect?"
    default: "today"                         # resolves to current date at interview time
    format_hint: "DD/MM/YYYY"

  payment_method:
    type: choice
    choices:
      - bank_transfer
      - cheque
      - crypto
    question: "How will the consultant be paid?"
    default: "bank_transfer"

  include_ip_assignment:
    type: boolean
    question: "Does this engagement involve intellectual property that should be assigned to the client?"
    default: false

  hourly_rate:
    type: number
    validation:
      min: 0
      max: 10000
    format_hint: "Amount in USD, no currency symbol"

# ── Interview groups ──────────────────────────────────────
# Overrides the Orchestrator's auto-grouping.
# Each group defines which variables are asked together.
groups:
  - name: "Parties"
    variables: [client_name, client_address, consultant_name, consultant_address]

  - name: "Engagement Terms"
    variables: [effective_date, scope_of_work, payment_method]

  - name: "IP Assignment"
    condition: include_ip_assignment          # only asked if gate is true
    variables: [ip_ownership_entity, ip_assignment_date]

  - name: "Bank Details"
    condition: "payment_method == 'bank_transfer'"
    variables: [bank_name, account_number]

  - name: "Milestones"
    loop: milestones                          # collected as a list
    variables: [description, date, amount]

# ── Cross-field validation ────────────────────────────────
# Evaluated during the Confirmation phase after all values are collected.
# Rules are simple comparisons the Orchestrator can evaluate.
validation:
  - rule: "end_date > effective_date"
    message: "The end date must be after the effective date"
```

### 4.3 Merge Rules

When `config.yaml` is present, the Analyzer merges it into the manifest as follows:

1. **`meta`** — copied to manifest as-is
2. **`variables`** — for each variable name in config, override matching fields in the manifest. Config values take precedence. Fields not in config retain their auto-inferred values.
3. **`groups`** — copied to manifest as the `groups` section. If absent, the manifest has no `groups` section and the Orchestrator auto-groups.
4. **`validation`** — copied to manifest as-is

The Analyzer does **not** create variables that appear in config but not in the template. Config can only override variables the template actually uses.

---

## 5. Analyzer v2

### 5.1 Extended Extraction

The v1 Analyzer only extracts `{{ variable_name }}` patterns. The v2 Analyzer additionally detects:

| Pattern | Regex | Purpose |
|---|---|---|
| If open | `\{%[-\s]*if\s+(.+?)\s*[-]?%\}` | Start of conditional block |
| Else | `\{%[-\s]*else\s*[-]?%\}` | Else branch |
| Endif | `\{%[-\s]*endif\s*[-]?%\}` | End of conditional block |
| For open | `\{%[-\s]*for\s+(\w+)\s+in\s+(\w+)\s*[-]?%\}` | Start of loop block |
| Endfor | `\{%[-\s]*endfor\s*[-]?%\}` | End of loop block |
| Variable | `\{\{\s*([\w.]+)\s*\}\}` | Variable reference (now supports dotted names for loop sub-vars) |

### 5.2 Two-Pass Analysis

**Pass 1 — Block structure:**

Scan the full text content and identify all block boundaries. Build a list of scopes:

```
TEMPLATE_TEXT
├── [top-level] ... {{ client_name }} ...
├── [if include_ip_assignment]
│   ├── [if-branch] ... {{ ip_ownership_entity }} ... {{ ip_assignment_date }} ...
│   └── [else-branch] ... (empty or has variables) ...
├── [top-level] ... {{ payment_method }} ...
├── [if payment_method == 'bank_transfer']
│   └── [if-branch] ... {{ bank_name }} ... {{ account_number }} ...
└── [for milestone in milestones]
    └── [loop-body] ... {{ milestone.description }} ... {{ milestone.date }} ...
```

**Pass 2 — Variable classification:**

For each `{{ variable }}` found, classify it based on its scope:

| Scope | Classification | Manifest location |
|---|---|---|
| Top-level | Unconditional | `variables` |
| Inside `{% if %}` if-branch | Conditional (if) | `conditionals[].if_variables` |
| Inside `{% if %}` else-branch | Conditional (else) | `conditionals[].else_variables` |
| Inside `{% for %}` body | Loop-scoped | `loops[].variables` |

### 5.3 Boolean Type Inference

If a variable name appears **only** as a condition in `{% if variable_name %}` (truthiness test) and **never** inside `{{ variable_name }}`, infer it as `type: boolean`. The Orchestrator will ask a yes/no question for it.

If a variable appears both as a condition and as a `{{ }}` reference, keep its inferred type from the `{{ }}` context (it's used as both a gate and a display value).

### 5.4 Loop Sub-Variable Extraction

For `{% for milestone in milestones %}` containing `{{ milestone.description }}`:

1. `milestones` is the **collection** variable (type: `list`, not directly asked)
2. `milestone` is the **loop variable** (iteration alias)
3. `milestone.description` → sub-variable `description` (strip the loop variable prefix)
4. Apply standard type inference to the sub-variable name: `description` → `text`, `date` → `date`, `amount` → `number`

### 5.5 Condition Parsing

The Analyzer extracts condition metadata for each `{% if %}` block:

| Condition form | Example | `gate_type` | `gate_variable` | `gate_value` |
|---|---|---|---|---|
| Truthiness | `{% if include_ip %}` | `boolean` | `include_ip` | — |
| Equality | `{% if method == 'bank' %}` | `equality` | `method` | `"bank"` |

For equality conditions, the Analyzer extracts the variable name and comparison value using regex: `(\w+)\s*==\s*['\"](.+?)['\"]`

### 5.6 Docx-Specific Handling

In `.docx` files, Word may split Jinja2 tags across multiple XML runs (e.g., `{% ` in one run and `if x %}` in another). The Analyzer must handle this:

1. Load the template via `docxtpl.DocxTemplate(path)`
2. Access the preprocessed XML source where `docxtpl` has merged split runs
3. Apply regex extraction on the merged text

If accessing `docxtpl` internals proves fragile, fall back to: extract all text by concatenating paragraph runs, table cell text, header/footer text, then apply regex. This loses positional information but is robust.

For HTML templates, read the raw file text directly — no preprocessing needed.

### 5.7 Dependency Graph Generation

After extracting all conditionals, the Analyzer builds the `dependencies` map:

```python
dependencies = {}
for cond in conditionals:
    gate_var = cond["gate_variable"]  # or condition name for boolean
    dep_vars = [v["name"] for v in cond["if_variables"] + cond["else_variables"]]
    dependencies.setdefault(gate_var, []).extend(dep_vars)
```

### 5.8 Edge Cases

- **Malformed blocks** (e.g., `{% if %}` without `{% endif %}`) — warn the user, skip the block, extract variables as unconditional
- **Nested blocks** — warn the user that nesting is not supported in v2; treat inner block as part of the outer block's scope
- **Variable in multiple scopes** — if the same variable name appears both at top-level and inside a conditional, classify it as unconditional (it's always needed)
- **Empty conditional/loop body** — valid; record the block with no variables
- **`{% else %}` without variables** — record `else_variables: []`

---

## 6. Orchestrator v2

### 6.1 Interview Plan Changes

The v1 interview plan groups all variables by logical affinity. The v2 plan must additionally account for:

1. **Gate variables** — boolean and choice variables that control conditionals must be asked **before** their dependent groups
2. **Conditional groups** — groups that are only asked if a gate condition is met
3. **Loop groups** — groups that collect lists, planned after unconditional/conditional groups

**Planning algorithm:**

1. Read the manifest's `variables`, `conditionals`, `loops`, `dependencies`, and `groups`
2. If `groups` is present (from config), use it as the interview structure
3. If `groups` is absent, auto-group:
   a. Separate unconditional variables into logical groups (same as v1)
   b. Ensure gate variables are placed in groups that come **before** their dependent conditional groups
   c. Add one group per conditional block
   d. Add one group per loop block, placed last
4. Order: unconditional groups → conditional groups (interleaved after their gates) → loop groups

### 6.2 Conditional Interview Flow

During the interview loop:

1. Ask the group containing the gate variable (e.g., "Does this engagement involve IP assignment?")
2. Record the answer
3. Evaluate the condition:
   - **Boolean gate:** `true` if user answered yes/affirmative, `false` otherwise
   - **Equality gate:** `true` if the collected value matches `gate_value`
4. If condition is **true**: ask the `if_variables` group
5. If condition is **false** and `else_variables` is non-empty: ask the `else_variables` group
6. If condition is **false** and `else_variables` is empty: skip, move to next group

### 6.3 Loop Collection Flow

For each loop group:

1. **Introduce:** "Now let's add the project milestones. I'll ask for each one individually."
2. **First item:** Ask for all sub-variables as a group: "What's the description, due date, and amount for the first milestone?"
3. **Confirm item:** "Got it — Milestone 1: 'Design phase', due 15 March 2026, $5,000."
4. **Continue:** "Would you like to add another milestone?"
5. **Repeat** steps 2-4 until the user says no
6. **Minimum check:** At least `min_items` (default 1) must be collected
7. **Summary:** "I have 3 milestones recorded: [numbered list]"

The collected data is a list of dictionaries:

```python
{
    "milestones": [
        {"description": "Design phase", "date": "2026-03-15", "amount": "5000"},
        {"description": "Development", "date": "2026-04-30", "amount": "10000"},
    ]
}
```

### 6.4 Confirmation Phase Changes

The v2 confirmation summary:

1. Shows unconditional values grouped as before
2. Shows conditional sections with their gate status:
   - If included: display the collected values
   - If skipped: "IP Assignment: *Skipped (not applicable)*"
3. Shows loop items as a numbered list
4. Allows the user to:
   - Edit any individual value
   - Change a gate answer (which reveals or hides dependent sections; if revealing, asks the newly-required questions)
   - Add, edit, or remove loop items

### 6.5 Validation

If the manifest includes `validation` rules (from config), the Orchestrator evaluates them during confirmation:

1. After the user confirms all values, check each rule
2. If a rule fails, report the error message and ask the user to correct the relevant values
3. Re-validate after corrections
4. Do not proceed to rendering until all rules pass

---

## 7. Renderer v2

### 7.1 Changes from v1

The renderer requires minimal changes because `docxtpl` and `jinja2` natively support `{% if %}` and `{% for %}`:

1. **Data structure** — the context dictionary now contains both flat values and list values (for loops). No code change needed — both `docxtpl.render(context)` and `jinja2.Template.render(context)` accept nested structures.

2. **Boolean coercion** — ensure boolean variables are passed as Python `True`/`False`, not strings `"yes"/"no"`. The renderer should coerce `type: boolean` variables before rendering.

3. **Validation scan update** — the post-render validator should check for unrendered `{% %}` tags in addition to `{{ }}` placeholders. Add regex: `\{%.*?%\}`. An unrendered control tag means a conditional or loop was not processed correctly.

---

## 8. Directory Structure (v2)

```
codraft/
├── CLAUDE.md
├── README.md
├── LICENSE
├── .gitignore
├── .claude/
│   └── skills/
│       ├── codraft/
│       │   └── SKILL.md              # Orchestrator (entry point)
│       ├── codraft-analyzer/
│       │   └── SKILL.md              # Analyzer
│       └── codraft-renderer/
│           └── SKILL.md              # Renderer
├── docs/
│   ├── codraft_mvp_spec.md           # MVP specification
│   └── codraft_v2_spec.md            # This file
├── templates/
│   ├── _examples/
│   │   ├── Bonterms_Mutual_NDA/
│   │   │   ├── Bonterms-Mutual-NDA.docx
│   │   │   └── Readme.md
│   │   ├── invoice/
│   │   │   └── invoice.html
│   │   ├── consulting_agreement/     # NEW — v2 example (docx)
│   │   │   ├── consulting_agreement.docx
│   │   │   └── config.yaml
│   │   └── event_invitation/         # NEW — v2 example (html)
│   │       ├── event_invitation.html
│   │       └── config.yaml
│   └── <user_template>/
│       ├── <name>.docx or <name>.html
│       ├── manifest.yaml             # auto-generated
│       └── config.yaml               # optional, developer-authored
└── output/
    └── <job_name>/
```

---

## 9. Example Session (v2 — Conditionals + Loops)

```
User: I need to prepare a consulting agreement

Claude: I'll use the Consulting Agreement template. I've found 12 fields to
        complete across several sections. Some sections are optional depending
        on your answers.

        Let's start with the parties. What is the client's full legal name
        and address?

User: TechCorp Pte Ltd, 1 Raffles Place #30-01 Singapore 048616

Claude: And the consultant's full name and address?

User: Sarah Chen, 88 Telok Ayer Street #03-01 Singapore 048468

Claude: Now the engagement terms. When should this agreement take effect,
        and what is the scope of work?

User: 1 March 2026. The scope is full-stack web application development.

Claude: How will the consultant be paid?
        Options: bank transfer, cheque, or crypto

User: Bank transfer

Claude: Since you chose bank transfer, I'll need the bank details.
        What is the bank name and account number?

User: DBS Bank, 012-345678-9

Claude: Does this engagement involve intellectual property that should be
        assigned to the client?

User: Yes

Claude: What entity should own the IP, and from what date?

User: TechCorp Pte Ltd, from 1 March 2026

Claude: Now let's add the project milestones. I'll ask for each one.
        What's the description, due date, and amount for the first milestone?

User: Design phase, 15 March 2026, $5,000

Claude: Got it — Milestone 1: Design phase, due 15 March 2026, $5,000.
        Would you like to add another milestone?

User: Yes. Development phase, 30 April 2026, $10,000

Claude: Milestone 2: Development phase, due 30 April 2026, $10,000.
        Another?

User: No, that's all

Claude: Here's a summary of all the details:

        Parties:
        - Client: TechCorp Pte Ltd, 1 Raffles Place #30-01 Singapore 048616
        - Consultant: Sarah Chen, 88 Telok Ayer Street #03-01 Singapore 048468

        Engagement Terms:
        - Effective Date: 01/03/2026
        - Scope: Full-stack web application development
        - Payment Method: Bank transfer

        Bank Details:
        - Bank: DBS Bank
        - Account: 012-345678-9

        IP Assignment:
        - Ownership Entity: TechCorp Pte Ltd
        - Assignment Date: 01/03/2026

        Milestones:
        1. Design phase — 15 March 2026 — $5,000
        2. Development phase — 30 April 2026 — $10,000

        Shall I produce the document?

User: Yes

Claude: Done! Your consulting agreement has been saved as:
        output/consulting_agreement_techcorp_pte_ltd_2026-02-16/
        consulting_agreement_techcorp_pte_ltd_2026-02-16.docx
```

---

## 10. Technical Decisions (v2)

| Decision | Choice | Rationale |
|---|---|---|
| Nesting depth | Single-level only | Covers majority of real templates; nested flows too complex for prompt-based skills |
| Condition forms | Truthiness + equality | Evaluable from collected answers without expression parsing |
| Config → Manifest | Analyzer merges config into manifest | Orchestrator reads one file; config changes only affect Analyzer |
| `{% elif %}` | Deferred to v3 | Multi-way branching complicates manifest and interview; rare in practice |
| Skill invocation | Prompt-level references | No programmatic API in Cowork; consistent with how MVP works |
| Loop minimum | At least 1 item (configurable via `min_items`) | A `{% for %}` block with 0 items renders empty |
| Manifest format | YAML (unchanged from MVP implementation) | Human-readable, extensible, consistent |
| `schema_version` | Integer, starting at 2 | Forward compatibility; Analyzer regenerates stale manifests |
