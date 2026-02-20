---
name: codraft-analyzer
description: "Template analyzer for Codraft (v2). Parses docx/HTML templates, extracts variables including conditionals and loops, merges config.yaml overrides, infers types, and generates a v2 manifest.yaml. Called by the codraft orchestrator — not triggered directly by the user."
---

# Codraft — Template Analyzer v2

You are running the Codraft template analyzer. Your job is to analyze a template file, extract all variables (including those inside conditional and loop blocks), merge any developer-provided `config.yaml` overrides, and produce a **v2 `manifest.yaml`** in the template's directory.

This skill is called by the Codraft orchestrator. You receive a **template directory path** as input (e.g., `templates/consulting_agreement/` or `templates/_examples/event_invitation/`).

## Prerequisites

Ensure dependencies are installed:

```bash
uv pip install docxtpl pyyaml jinja2 weasyprint --break-system-packages
```

---

## Step 1 — Detect Template Format

1. Look for a `.docx` or `.html` file in the template directory.
2. Each directory should contain exactly one template file. If multiple are found, use the first and warn.
3. The file extension determines the format (`docx` or `html`), which is recorded in the manifest.
4. If no `.docx` or `.html` file is found, inform the user and stop.

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

Save `manifest.yaml` in the template directory with the **v2 schema**. The full structure is shown below.

### Manifest v2 Schema

```yaml
# -- Metadata --
schema_version: 2
template: "consulting_agreement.docx"
template_path: "templates/consulting_agreement/consulting_agreement.docx"
format: docx                          # "docx" or "html"
analyzed_at: "2026-02-16T10:30:00Z"   # ISO 8601 timestamp
variable_count: 12                    # total unique variables (all scopes)

# -- From config.yaml (optional, present only if config provides it) --
meta:
  display_name: "Consulting Agreement"
  description: "Standard consulting engagement agreement"

# -- Unconditional variables --
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
    type: choice
    choices:
      - bank_transfer
      - cheque
      - crypto
    # question: "How will the consultant be paid?"
    # default: "bank_transfer"

  - name: effective_date
    label: "Effective Date"
    type: date

# -- Conditional blocks --
# Variables gated by {% if %} / {% else %} blocks.
# Asked only if the condition evaluates to true/false.
conditionals:
  - condition: "include_ip_assignment"
    gate_type: boolean
    if_variables:
      - name: ip_ownership_entity
        label: "IP Ownership Entity"
        type: text
      - name: ip_assignment_date
        label: "IP Assignment Date"
        type: date
    else_variables: []

  - condition: "payment_method == 'bank_transfer'"
    gate_type: equality
    gate_variable: payment_method
    gate_value: "bank_transfer"
    if_variables:
      - name: bank_name
        label: "Bank Name"
        type: text
      - name: account_number
        label: "Account Number"
        type: text
    else_variables: []

# -- Loop blocks --
# Variables inside {% for %} blocks. Collected as lists.
loops:
  - loop_var: "milestone"
    collection: "milestones"
    label: "Project Milestone"
    min_items: 1
    variables:
      - name: description
        label: "Description"
        type: text
      - name: date
        label: "Due Date"
        type: date
      - name: amount
        label: "Amount"
        type: number

# -- Dependencies (pre-computed) --
# Gate variable -> list of dependent variable names.
dependencies:
  include_ip_assignment:
    - ip_ownership_entity
    - ip_assignment_date
  payment_method:
    - bank_name
    - account_number

# -- Interview groups (optional, from config.yaml) --
groups:
  - name: "Parties"
    variables: [client_name, client_address, consultant_name, consultant_address]

  - name: "Engagement Terms"
    variables: [effective_date, scope_of_work, payment_method]

  - name: "IP Assignment"
    condition: include_ip_assignment
    variables: [ip_ownership_entity, ip_assignment_date]

  - name: "Bank Details"
    condition: "payment_method == 'bank_transfer'"
    variables: [bank_name, account_number]

  - name: "Milestones"
    loop: milestones
    variables: [description, date, amount]

# -- Validation rules (optional, from config.yaml) --
validation:
  - rule: "end_date > effective_date"
    message: "The end date must be after the effective date"
```

### Schema Rules

- **`schema_version`** — always `2`.
- **`variable_count`** — total unique variables across all scopes (unconditional + conditional + loop sub-variables).
- **`conditionals`** — list of conditional blocks. Empty list `[]` if the template has no conditionals.
- **`loops`** — list of loop blocks. Empty list `[]` if the template has no loops.
- **`dependencies`** — map of gate variables to their dependent variables. Empty map `{}` if no conditionals.
- **`meta`**, **`groups`**, **`validation`** — present only if `config.yaml` provides them.
- **Backward compatibility** — templates with no conditionals or loops produce a valid v2 manifest with `conditionals: []`, `loops: []`, and `dependencies: {}`. The Orchestrator treats this identically to v1 behaviour.

### Loop Label and Min Items

For each loop in the manifest:
- `label`: a human-readable label for the loop group, generated from the collection name (e.g., `milestones` -> "Project Milestone"). If config provides a group with `loop: <collection>`, use the group's `name` field as the label.
- `min_items`: defaults to `1`. Can be overridden by config if supported in a future version.

---

## Step 11 — Produce the Analysis Script

Write and run a single Python script that performs all of the above steps. The script should:

1. Accept the template directory path as input
2. Detect the template format
3. Check cache validity (including config.yaml freshness and schema version)
4. Extract text content (docx preprocessing or raw HTML)
5. Run two-pass analysis (block structure + variable classification)
6. Infer types and generate labels
7. Parse conditions and extract loop sub-variables
8. Build the dependency graph
9. Merge config.yaml if present
10. Write `manifest.yaml`

### Python Script Template

```python
import os
import sys
import re
import yaml
from datetime import datetime, timezone

# ── Configuration ──
template_dir = "<TEMPLATE_DIR_PATH>"  # set by the analyzer

# ── Step 1: Detect format ──
template_file = None
template_format = None
for f in os.listdir(template_dir):
    if f.endswith(".docx"):
        template_file = f
        template_format = "docx"
        break
    elif f.endswith(".html"):
        template_file = f
        template_format = "html"
        break

if not template_file:
    print("ERROR: No .docx or .html template found in", template_dir)
    sys.exit(1)

template_path = os.path.join(template_dir, template_file)

# ── Step 2: Check cache ──
manifest_path = os.path.join(template_dir, "manifest.yaml")
config_path = os.path.join(template_dir, "config.yaml")

needs_regen = True
if os.path.exists(manifest_path):
    with open(manifest_path, "r") as mf:
        existing = yaml.safe_load(mf)
    if existing and existing.get("schema_version", 0) >= 2:
        analyzed_at = existing.get("analyzed_at", "")
        if analyzed_at:
            analyzed_time = datetime.fromisoformat(analyzed_at.replace("Z", "+00:00"))
            tmpl_mtime = datetime.fromtimestamp(
                os.path.getmtime(template_path), tz=timezone.utc
            )
            config_mtime = None
            if os.path.exists(config_path):
                config_mtime = datetime.fromtimestamp(
                    os.path.getmtime(config_path), tz=timezone.utc
                )
            if tmpl_mtime <= analyzed_time and (
                config_mtime is None or config_mtime <= analyzed_time
            ):
                needs_regen = False

if not needs_regen:
    print("Manifest is up to date. Skipping analysis.")
    sys.exit(0)

# ── Step 3: Extract text ──
if template_format == "docx":
    from docxtpl import DocxTemplate

    doc = DocxTemplate(template_path)
    try:
        text = doc.get_xml()
    except Exception:
        # Fallback: concatenate all paragraph and table text
        text = ""
        for p in doc.docx.paragraphs:
            text += p.text + "\n"
        for table in doc.docx.tables:
            for row in table.rows:
                for cell in row.cells:
                    text += cell.text + "\n"
        for section in doc.docx.sections:
            if section.header:
                for p in section.header.paragraphs:
                    text += p.text + "\n"
            if section.footer:
                for p in section.footer.paragraphs:
                    text += p.text + "\n"
else:
    with open(template_path, "r", encoding="utf-8") as f:
        text = f.read()

# ── Step 4: Two-pass analysis ──

# Regex patterns
RE_IF = re.compile(r"\{%[-\s]*if\s+(.+?)\s*[-]?%\}")
RE_ELSE = re.compile(r"\{%[-\s]*else\s*[-]?%\}")
RE_ENDIF = re.compile(r"\{%[-\s]*endif\s*[-]?%\}")
RE_FOR = re.compile(r"\{%[-\s]*for\s+(\w+)\s+in\s+(\w+)\s*[-]?%\}")
RE_ENDFOR = re.compile(r"\{%[-\s]*endfor\s*[-]?%\}")
RE_VAR = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
RE_EQUALITY = re.compile(r"(\w+)\s*==\s*['\"](.+?)['\"]")

# Find all tags with positions
tags = []
for m in RE_IF.finditer(text):
    tags.append(("if", m.start(), m.group(1).strip()))
for m in RE_ELSE.finditer(text):
    tags.append(("else", m.start(), None))
for m in RE_ENDIF.finditer(text):
    tags.append(("endif", m.start(), None))
for m in RE_FOR.finditer(text):
    tags.append(("for", m.start(), (m.group(1), m.group(2))))
for m in RE_ENDFOR.finditer(text):
    tags.append(("endfor", m.start(), None))
for m in RE_VAR.finditer(text):
    tags.append(("var", m.start(), m.group(1)))

tags.sort(key=lambda t: t[1])

# Walk through tags and classify
# Scope states: "top", "if-branch", "else-branch", "loop-body"
scope_stack = [{"type": "top"}]
unconditional_vars = []  # list of variable names (ordered, unique)
conditionals = []  # list of conditional block dicts
loops = []  # list of loop block dicts
condition_only_vars = set()  # vars that appear only in {% if var %}

current_conditional = None
current_loop = None

for tag_type, pos, data in tags:
    current_scope = scope_stack[-1]

    if tag_type == "if":
        # Parse the condition
        condition_expr = data
        eq_match = RE_EQUALITY.match(condition_expr)
        if eq_match:
            cond_block = {
                "condition": condition_expr,
                "gate_type": "equality",
                "gate_variable": eq_match.group(1),
                "gate_value": eq_match.group(2),
                "if_variables": [],
                "else_variables": [],
            }
        else:
            # Truthiness test
            var_name = condition_expr.strip()
            cond_block = {
                "condition": var_name,
                "gate_type": "boolean",
                "if_variables": [],
                "else_variables": [],
            }
            condition_only_vars.add(var_name)

        conditionals.append(cond_block)
        scope_stack.append({"type": "if-branch", "block": cond_block})

    elif tag_type == "else":
        if len(scope_stack) > 1 and scope_stack[-1]["type"] == "if-branch":
            block = scope_stack[-1]["block"]
            scope_stack[-1] = {"type": "else-branch", "block": block}
        # else: malformed — ignore

    elif tag_type == "endif":
        if len(scope_stack) > 1 and scope_stack[-1]["type"] in (
            "if-branch",
            "else-branch",
        ):
            scope_stack.pop()
        # else: malformed — warn

    elif tag_type == "for":
        loop_var, collection = data
        loop_block = {
            "loop_var": loop_var,
            "collection": collection,
            "variables": [],
        }
        loops.append(loop_block)
        scope_stack.append({"type": "loop-body", "block": loop_block})

    elif tag_type == "endfor":
        if len(scope_stack) > 1 and scope_stack[-1]["type"] == "loop-body":
            scope_stack.pop()
        # else: malformed — warn

    elif tag_type == "var":
        var_name = data
        current = scope_stack[-1]

        if current["type"] == "top":
            if var_name not in unconditional_vars:
                unconditional_vars.append(var_name)
        elif current["type"] == "if-branch":
            block = current["block"]
            if var_name not in [v["name"] for v in block["if_variables"]]:
                block["if_variables"].append({"name": var_name})
        elif current["type"] == "else-branch":
            block = current["block"]
            if var_name not in [v["name"] for v in block["else_variables"]]:
                block["else_variables"].append({"name": var_name})
        elif current["type"] == "loop-body":
            block = current["block"]
            loop_var = block["loop_var"]
            if "." in var_name and var_name.startswith(loop_var + "."):
                sub_name = var_name[len(loop_var) + 1 :]
                if sub_name not in [v["name"] for v in block["variables"]]:
                    block["variables"].append({"name": sub_name})
            else:
                # Variable not prefixed with loop var — treat as unconditional
                if var_name not in unconditional_vars:
                    unconditional_vars.append(var_name)

# ── Variable in multiple scopes ──
# If a var appears at top-level AND in a conditional, keep it unconditional only
for cond in conditionals:
    cond["if_variables"] = [
        v for v in cond["if_variables"] if v["name"] not in unconditional_vars
    ]
    cond["else_variables"] = [
        v for v in cond["else_variables"] if v["name"] not in unconditional_vars
    ]

# ── Boolean inference ──
# Vars that appear only in {% if var %} and never in {{ var }}
all_rendered_vars = set()
for v in unconditional_vars:
    all_rendered_vars.add(v)
for cond in conditionals:
    for v in cond["if_variables"]:
        all_rendered_vars.add(v["name"])
    for v in cond["else_variables"]:
        all_rendered_vars.add(v["name"])
for loop in loops:
    for v in loop["variables"]:
        all_rendered_vars.add(v["name"])

boolean_gate_vars = condition_only_vars - all_rendered_vars

# ── Ensure gate variables are in unconditional list ──
for cond in conditionals:
    if cond["gate_type"] == "boolean":
        gate_var = cond["condition"]
    else:
        gate_var = cond["gate_variable"]
    if gate_var not in unconditional_vars:
        unconditional_vars.append(gate_var)


# ── Step 5: Type inference and labels ──
def infer_type(name):
    if name in boolean_gate_vars:
        return "boolean"
    lower = name.lower()
    if lower.endswith(("_name", "_address")):
        return "text"
    if lower.endswith("_date"):
        return "date"
    if lower.endswith("_email"):
        return "email"
    if lower.endswith(("_amount", "_price", "_fee")):
        return "number"
    if lower.endswith(("_phone", "_tel", "_mobile")):
        return "phone"
    return "text"


def make_label(name):
    return name.replace("_", " ").title()


def build_var_entry(name):
    return {"name": name, "label": make_label(name), "type": infer_type(name)}


# Build final variable lists
final_variables = [build_var_entry(v) for v in unconditional_vars]

for cond in conditionals:
    cond["if_variables"] = [build_var_entry(v["name"]) for v in cond["if_variables"]]
    cond["else_variables"] = [
        build_var_entry(v["name"]) for v in cond["else_variables"]
    ]

for loop in loops:
    loop["variables"] = [build_var_entry(v["name"]) for v in loop["variables"]]
    loop["label"] = make_label(loop["collection"]).rstrip("s")
    loop["min_items"] = 1


# ── Step 6: Dependencies ──
dependencies = {}
for cond in conditionals:
    if cond["gate_type"] == "boolean":
        gate_var = cond["condition"]
    else:
        gate_var = cond["gate_variable"]

    dep_vars = [v["name"] for v in cond["if_variables"]] + [
        v["name"] for v in cond["else_variables"]
    ]
    if dep_vars:
        dependencies.setdefault(gate_var, []).extend(dep_vars)

# ── Step 7: Config merge ──
config = None
if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as cf:
        config = yaml.safe_load(cf)

if config and isinstance(config, dict):
    config_vars = config.get("variables", {})
    if config_vars:

        def merge_var_overrides(var_entry):
            """Merge config overrides into a variable entry."""
            name = var_entry["name"]
            if name in config_vars:
                overrides = config_vars[name]
                for field in [
                    "label",
                    "type",
                    "question",
                    "description",
                    "default",
                    "required",
                    "format_hint",
                    "choices",
                    "validation",
                ]:
                    if field in overrides:
                        var_entry[field] = overrides[field]
            return var_entry

        final_variables = [merge_var_overrides(v) for v in final_variables]
        for cond in conditionals:
            cond["if_variables"] = [
                merge_var_overrides(v) for v in cond["if_variables"]
            ]
            cond["else_variables"] = [
                merge_var_overrides(v) for v in cond["else_variables"]
            ]
        for loop in loops:
            loop["variables"] = [merge_var_overrides(v) for v in loop["variables"]]

# ── Count all unique variables ──
all_var_names = set(v["name"] for v in final_variables)
for cond in conditionals:
    for v in cond["if_variables"]:
        all_var_names.add(v["name"])
    for v in cond["else_variables"]:
        all_var_names.add(v["name"])
for loop in loops:
    for v in loop["variables"]:
        all_var_names.add(v["name"])

variable_count = len(all_var_names)

# ── Step 8: Build manifest ──
manifest = {
    "schema_version": 2,
    "template": template_file,
    "template_path": os.path.join(template_dir, template_file),
    "format": template_format,
    "analyzed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "variable_count": variable_count,
}

# Meta (from config only)
if config and "meta" in config:
    manifest["meta"] = config["meta"]

# Variables
manifest["variables"] = final_variables

# Conditionals
manifest["conditionals"] = conditionals

# Loops
manifest["loops"] = loops

# Dependencies
manifest["dependencies"] = dependencies

# Groups (from config only)
if config and "groups" in config:
    manifest["groups"] = config["groups"]

# Validation (from config only)
if config and "validation" in config:
    manifest["validation"] = config["validation"]

# ── Step 9: Write manifest ──
# Clean up internal fields from conditionals before writing
for cond in manifest["conditionals"]:
    # Ensure the condition field is clean
    pass

with open(manifest_path, "w", encoding="utf-8") as mf:
    yaml.dump(manifest, mf, default_flow_style=False, sort_keys=False, allow_unicode=True)

print(f"Manifest written: {manifest_path}")
print(f"  Format: {template_format}")
print(f"  Variables: {variable_count}")
print(f"  Conditionals: {len(conditionals)}")
print(f"  Loops: {len(loops)}")
```

---

## Edge Cases

- **Malformed blocks** (e.g., `{% if %}` without `{% endif %}`) — warn the user, skip the block, extract any variables found within it as unconditional.
- **Nested blocks** (e.g., `{% for %}` inside `{% if %}`) — warn the user that nesting is not supported in v2. Treat the inner block as part of the outer block's scope.
- **Variable in multiple scopes** — if the same variable name appears both at top-level and inside a conditional, classify it as unconditional (it is always needed).
- **Empty conditional/loop body** — valid. Record the block with an empty variables list.
- **`{% else %}` without variables** — record `else_variables: []`.
- **Empty template** (no variables at all) — inform the user and stop.
- **Multiple template files** in one directory — use the first `.docx` or `.html` found, warn about others.
- **No `.docx` or `.html` file found** — inform the user and stop.
- **Variables in config but not in template** — ignore them. Config can only override variables the template actually uses.

---

## Important Notes

- **Never modify template files** — only read them.
- **Use `uv`** for Python package management.
- **Format any Python code** in the style of black.
- **The manifest is a cache** — regenerate it if the template file or config.yaml is newer, or if the schema version is outdated.
- **config.yaml is developer-authored** — the Analyzer reads it but never modifies it.
- **The Orchestrator reads only the manifest** — it never reads config.yaml directly. All config overrides are baked into the manifest by the Analyzer.
