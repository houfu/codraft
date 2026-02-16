---
name: codraft-analyzer
description: "Template analyzer for Codraft. Parses docx/HTML templates, extracts variables, infers types, and generates manifest.yaml. Called by the codraft orchestrator — not triggered directly by the user."
---

# Codraft — Template Analyzer

You are running the Codraft template analyzer. Your job is to analyze a template file, extract its variables, infer their types, and produce a `manifest.yaml` in the template's directory.

This skill is called by the Codraft orchestrator. You receive a **template directory path** as input (e.g., `templates/nda/` or `templates/_examples/invoice/`).

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

---

## Step 2 — Check for Cached Manifest

1. Look for `manifest.yaml` in the template's directory.
2. If it exists and the template file has NOT been modified since the manifest was generated (compare `analyzed_at` timestamp with template file modification time), use the cached manifest. **Stop here — analysis is complete.**
3. If no manifest exists, or the template is newer, run the analysis below.

---

## Step 3 — Extract Variables

**For docx templates:** Run a Python script using `docxtpl` and `re` to:

1. Load the template with `docxtpl.DocxTemplate`.
2. Scan all text content — paragraphs, tables, headers, footers — for the pattern `\{\{\s*(\w+)\s*\}\}`.

**For HTML templates:** Run a Python script using `re` to:

1. Read the raw HTML file as text.
2. Scan for the same pattern: `\{\{\s*(\w+)\s*\}\}`.

**For both formats**, then:

3. Collect unique variable names, preserving first-occurrence order.
4. For each variable, infer type from its name suffix:

| Suffix pattern | Inferred type |
|---|---|
| `*_name`, `*_address` | `text` |
| `*_date` | `date` |
| `*_email` | `email` |
| `*_amount`, `*_price`, `*_fee` | `number` |
| `*_phone`, `*_tel`, `*_mobile` | `phone` |
| Everything else | `text` |

5. Generate a human-readable label from the variable name: replace underscores with spaces, title-case it (e.g., `landlord_name` → "Landlord Name").

---

## Step 4 — Save Manifest

Save `manifest.yaml` in the template directory with this structure:

```yaml
template: "<filename>.docx"
template_path: "templates/<template_name>/<filename>.docx"
format: docx
analyzed_at: "<ISO 8601 timestamp>"
variable_count: <N>

variables:

  - name: landlord_name
    label: Landlord Name
    type: text

  - name: commencement_date
    label: Commencement Date
    type: date

  - name: rental_amount
    label: Rental Amount
    type: number
```

The `format` field is `docx` or `html`. Each variable is its own YAML block, separated by a blank line for readability. This structure is designed to be extended later with fields like `default`, `question`, and `validation`.

---

## Edge Cases

- **docx-specific**: Variables inside tables, headers, and footers must be found.
- Malformed placeholders (e.g., `{{name}` with missing brace) — skip and warn the user.
- Empty template (no variables) — inform the user and stop.
- Multiple template files in one directory — use the first, warn about others.
- No `.docx` or `.html` file found — inform the user and stop.

---

## Important Notes

- **Never modify template files** — only read them.
- **Use `uv`** for Python package management.
- **Format any Python code** in the style of black.
- **The manifest is a cache** — regenerate it if the template file is newer, otherwise reuse it.
