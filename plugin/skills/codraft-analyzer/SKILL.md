---
name: codraft-analyzer
description: "Template analyzer for Codraft (v2). Parses docx/HTML templates, extracts variables including conditionals and loops, merges config.yaml overrides, infers types, and generates a v2 manifest.yaml. Called by the codraft orchestrator — not triggered directly by the user."
---

# Codraft — Template Analyzer v2

You are running the Codraft template analyzer. Your job is to analyze a template file, extract all variables (including those inside conditional and loop blocks), merge any developer-provided `config.yaml` overrides, and produce a **v2 `manifest.yaml`** in the template's directory.

This skill is called by the Codraft orchestrator. You receive a **template directory path** as input (e.g., `templates/_examples/Bonterms_Mutual_NDA/` or `templates/_examples/meeting_notes/`).

## Prerequisites

Ensure dependencies are installed:

```bash
command -v uv > /dev/null 2>&1 && uv pip install docxtpl pyyaml jinja2 weasyprint || pip install docxtpl pyyaml jinja2 weasyprint
```

---

## Step 1 — Detect Template Format

1. Look for a `.docx`, `.html`, or `.md` file in the template directory.
2. Each directory should contain exactly one template file. If multiple are found, use the first and warn.
3. The file extension determines the format (`docx`, `html`, or `markdown`), which is recorded in the manifest.
4. If no `.docx`, `.html`, or `.md` file is found, inform the user and stop.

---

## Step 2 — Check for Cached Manifest

1. Look for `manifest.yaml` in the template's directory.
2. Check if the manifest needs regeneration. Regenerate if **any** of these are true:
   - No `manifest.yaml` exists
   - The template file is newer than the manifest's `analyzed_at` timestamp
   - A `config.yaml` file exists and is newer than the manifest's `analyzed_at` timestamp
   - The manifest has no `schema_version` field (it is a v1 manifest that must be upgraded)
   - The manifest's `schema_version` is less than `2`
3. If none of the above conditions are true, the cached manifest is valid. **Stop here — analysis is complete.**

---

## Step 3 — Extract Text Content

The goal of this step is to get the full text content of the template for regex analysis.

### For docx templates

Run a Python script that:

1. Loads the template with `docxtpl.DocxTemplate(path)`.
2. Accesses the preprocessed XML source where `docxtpl` has merged split XML runs. Use `doc.get_xml()` to get the merged XML content.
3. If `get_xml()` is unavailable or fails, fall back to: extract all text by concatenating paragraph runs, table cell text, header/footer text. This loses positional information but is robust.
4. The extracted text is used for regex analysis in the following steps.

**Why this matters:** In `.docx` files, Word may split Jinja2 tags across multiple XML runs (e.g., `{% ` in one run and `if x %}` in another). The `docxtpl` preprocessor merges these split runs so that regex matching works correctly.

### For HTML templates

Read the raw HTML file as text. No preprocessing is needed.

### For markdown templates

Read the raw `.md` file as text. No preprocessing is needed — identical to the HTML path.

---

## Step 4 — Two-Pass Analysis

### Pass 1 — Block Structure Identification

Scan the full text content and identify all block boundaries using these regex patterns:

| Pattern | Regex | Captures |
|---|---|---|
| If open | `\{%[-\s]*if\s+(.+?)\s*[-]?%\}` | condition expression |
| Else | `\{%[-\s]*else\s*[-]?%\}` | (none) |
| Endif | `\{%[-\s]*endif\s*[-]?%\}` | (none) |
| For open | `\{%[-\s]*for\s+(\w+)\s+in\s+(\w+)\s*[-]?%\}` | loop_var, collection |
| Endfor | `\{%[-\s]*endfor\s*[-]?%\}` | (none) |
| Variable | `\{\{\s*([\w.]+)\s*\}\}` | variable name (supports dotted names) |

Build a list of scopes by walking through the text linearly. Track the current scope as you encounter block tags:

```
TEMPLATE_TEXT
  [top-level]        ... {{ client_name }} ...
  [if include_ip]
    [if-branch]      ... {{ ip_ownership_entity }} ...
    [else-branch]    ... (may have variables or be empty) ...
  [top-level]        ... {{ payment_method }} ...
  [if payment_method == 'bank_transfer']
    [if-branch]      ... {{ bank_name }} ... {{ account_number }} ...
  [for milestone in milestones]
    [loop-body]      ... {{ milestone.description }} ... {{ milestone.date }} ...
```

**Implementation approach:** Process the text sequentially. Maintain a state machine:
- Start in `top-level` scope
- `{% if ... %}` → push to `if-branch` scope, record the condition expression
- `{% else %}` → switch to `else-branch` scope (same conditional block)
- `{% endif %}` → pop back to `top-level` scope
- `{% for ... in ... %}` → push to `loop-body` scope, record loop_var and collection
- `{% endfor %}` → pop back to `top-level` scope

Record each `{{ variable }}` with its current scope.

### Pass 2 — Variable Classification

For each `{{ variable }}` found, classify it based on the scope it was found in:

| Scope | Classification | Manifest location |
|---|---|---|
| Top-level | Unconditional | `variables` |
| Inside `{% if %}` if-branch | Conditional (if) | `conditionals[].if_variables` |
| Inside `{% if %}` else-branch | Conditional (else) | `conditionals[].else_variables` |
| Inside `{% for %}` body | Loop-scoped | `loops[].variables` |

**Variable in multiple scopes:** If the same variable name appears both at top-level and inside a conditional, classify it as **unconditional** (it is always needed). Remove it from the conditional's variable list.

---

## Step 5 — Type Inference

For each variable, infer its type from its name suffix:

| Suffix pattern | Inferred type |
|---|---|
| `*_name`, `*_address` | `text` |
| `*_date` | `date` |
| `*_email` | `email` |
| `*_amount`, `*_price`, `*_fee` | `number` |
| `*_phone`, `*_tel`, `*_mobile` | `phone` |
| Everything else | `text` |

### Boolean Type Inference

If a variable name appears **only** as a condition in `{% if variable_name %}` (truthiness test) and **never** inside `{{ variable_name }}`, infer it as `type: boolean`. The Orchestrator will ask a yes/no question for it.

If a variable appears both as a condition and as a `{{ }}` reference, keep its inferred type from the `{{ }}` context — it is used as both a gate and a display value.

### Label Generation

Generate a human-readable label from the variable name: replace underscores with spaces, title-case it (e.g., `landlord_name` -> "Landlord Name").

---

## Step 6 — Condition Parsing

For each `{% if %}` block, extract condition metadata:

| Condition form | Example | `gate_type` | `gate_variable` | `gate_value` |
|---|---|---|---|---|
| Truthiness | `{% if include_ip %}` | `boolean` | `include_ip` | (omitted) |
| Equality | `{% if method == 'bank' %}` | `equality` | `method` | `"bank"` |

**For truthiness conditions:** The condition expression is a single variable name. Set `gate_type: boolean`.

**For equality conditions:** Use regex `(\w+)\s*==\s*['\"](.+?)['\"]` to extract the variable name and comparison value. Set `gate_type: equality`, `gate_variable` to the variable name, and `gate_value` to the comparison string.

**Gate variables as unconditional:** The gate variable itself (e.g., `include_ip_assignment`, `payment_method`) is always an unconditional variable — it must be collected before the conditional block can be evaluated. Ensure gate variables appear in the `variables` list (top-level), not inside their own conditional block.

---

## Step 7 — Loop Sub-Variable Extraction

For `{% for milestone in milestones %}` containing `{{ milestone.description }}`:

1. `milestones` is the **collection** variable (not directly asked — it is the list the loop iterates over)
2. `milestone` is the **loop variable** (iteration alias, not collected)
3. `milestone.description` -> sub-variable `description` (strip the loop variable prefix and dot)
4. Apply standard type inference to the sub-variable name: `description` -> `text`, `date` -> `date`, `amount` -> `number`

The loop entry in the manifest records:
- `loop_var`: the iteration alias (e.g., `milestone`)
- `collection`: the collection name (e.g., `milestones`)
- `variables`: list of sub-variables with name, label, and type

---

## Step 8 — Dependency Graph Generation

After extracting all conditionals, build the `dependencies` map. This tells the Orchestrator which variables depend on which gate variables.

```python
dependencies = {}
for cond in conditionals:
    # For boolean gates, the gate_variable is the condition name itself
    # For equality gates, gate_variable is explicitly set
    if cond["gate_type"] == "boolean":
        gate_var = cond["condition"]  # e.g., "include_ip_assignment"
    else:
        gate_var = cond["gate_variable"]  # e.g., "payment_method"

    dep_vars = []
    for v in cond.get("if_variables", []):
        dep_vars.append(v["name"])
    for v in cond.get("else_variables", []):
        dep_vars.append(v["name"])

    dependencies.setdefault(gate_var, []).extend(dep_vars)
```

---

## Step 9 — Config Merge

If a `config.yaml` file exists in the template directory, read it and merge its contents into the manifest.

### Merge Rules

1. **`meta`** — copy to the manifest as-is. The `meta` section appears in the manifest only if config provides it.

2. **`variables`** — for each variable name in config, override matching fields in the manifest's variable entries. Config values take precedence over auto-inferred values. Fields not in config retain their auto-inferred values. Apply these overrides to variables in all sections: top-level `variables`, `conditionals[].if_variables`, `conditionals[].else_variables`, and `loops[].variables`.
   - **Important:** Do not create variables that appear in config but not in the template. Config can only override variables the template actually uses.
   - If config sets `type: choice` for a variable, include the `choices` list from config in the variable entry.
   - If config sets `type: boolean` for a variable, use it (config overrides auto-inference).
   - Copy these config fields when present: `label`, `type`, `question`, `description`, `default`, `required`, `format_hint`, `choices`, `validation`.

3. **`groups`** — copy to the manifest as the `groups` section. If absent in config, the manifest has no `groups` section and the Orchestrator will auto-group.

4. **`validation`** — copy to the manifest as-is. If absent in config, the manifest has no `validation` section.

---

## Step 10 — Save Manifest

Save `manifest.yaml` in the template directory with the **v2 schema**.

### Key Manifest Sections

- **`schema_version: 2`** — always `2`
- **`variables`** — unconditional variables with `name`, `label`, `type`
- **`conditionals`** — blocks with `condition`, `gate_type` (boolean/equality), `if_variables`, `else_variables`
- **`loops`** — blocks with `loop_var`, `collection`, `label`, `min_items`, `variables`
- **`dependencies`** — map of gate variables → dependent variable names
- **`meta`**, **`groups`**, **`validation`** — present only if `config.yaml` provides them

### Schema Rules

- `variable_count` = total unique variables across all scopes
- Templates with no conditionals/loops → `conditionals: []`, `loops: []`, `dependencies: {}`
- Loop `label` generated from collection name (e.g., `milestones` → "Project Milestone"); `min_items` defaults to `1`

See `codraft_v2_spec.md` section 3 for the full manifest schema with examples.

---

## Edge Cases

- **Malformed blocks** (e.g., `{% if %}` without `{% endif %}`) — warn the user, skip the block, extract any variables found within it as unconditional.
- **Nested blocks** (e.g., `{% for %}` inside `{% if %}`) — warn the user that nesting is not supported in v2. Treat the inner block as part of the outer block's scope.
- **Variable in multiple scopes** — if the same variable name appears both at top-level and inside a conditional, classify it as unconditional (it is always needed).
- **Empty conditional/loop body** — valid. Record the block with an empty variables list.
- **`{% else %}` without variables** — record `else_variables: []`.
- **Empty template** (no variables at all) — inform the user and stop.
- **Multiple template files** in one directory — use the first `.docx`, `.html`, or `.md` found, warn about others.
- **No `.docx`, `.html`, or `.md` file found** — inform the user and stop.
- **Variables in config but not in template** — ignore them. Config can only override variables the template actually uses.

---

## Important Notes

- **Never modify template files** — only read them.
- **Use `uv`** for Python package management.
- **Format any Python code** in the style of black.
- **The manifest is a cache** — regenerate it if the template file or config.yaml is newer, or if the schema version is outdated.
- **config.yaml is developer-authored** — the Analyzer reads it but never modifies it.
- **The Orchestrator reads only the manifest** — it never reads config.yaml directly. All config overrides are baked into the manifest by the Analyzer.
