---
name: codraft-renderer
description: "Document renderer for Codraft. Takes a template, variable values, and produces rendered documents (docx or html+pdf). Validates output for unfilled placeholders. Called by the codraft orchestrator — not triggered directly by the user."
---

# Codraft — Document Renderer (v2)

You are running the Codraft document renderer. Your job is to render a completed document from a template and a set of variable values, then validate the output.

This skill is called by the Codraft orchestrator. You receive:
- **Template path** (e.g., `templates/consulting_agreement/Consulting-Agreement.docx`)
- **Format** (`docx` or `html`)
- **Variable dictionary** — all collected values, including:
  - Flat key-value pairs for simple and conditional variables
  - Boolean values as Python `True`/`False` (not strings like `"yes"` or `"no"`)
  - Lists of dictionaries for loop collections (e.g., `"milestones": [{"description": "...", "date": "..."}, ...]`)
- **Output directory** (e.g., `output/`)

## Prerequisites

Ensure dependencies are installed:

```bash
command -v uv > /dev/null 2>&1 && uv pip install docxtpl pyyaml jinja2 weasyprint || pip install docxtpl pyyaml jinja2 weasyprint
```

---

## Step 1 — Prepare Context

Before rendering, ensure the variable dictionary is properly formatted for the template engine:

### Boolean Coercion

Boolean gate variables must be Python `True`/`False`, not string representations. The Orchestrator should pass them correctly, but verify:

```python
# Ensure boolean values are actual booleans
for key, value in context.items():
    if isinstance(value, str) and value.lower() in ("true", "yes", "y"):
        context[key] = True
    elif isinstance(value, str) and value.lower() in ("false", "no", "n"):
        context[key] = False
```

This is critical for `{% if %}` conditionals — Jinja2 evaluates `"false"` (a non-empty string) as truthy, which would incorrectly include conditional sections.

### Loop Data

Loop collections should already be lists of dictionaries. Verify the structure:

```python
# Example expected structure for milestones loop:
# context["milestones"] = [
#     {"description": "Design phase", "due_date": "2026-03-15", "amount": "5000"},
#     {"description": "Development", "due_date": "2026-04-30", "amount": "10000"},
# ]
```

---

## Step 2 — Render

### Output structure

Each rendering job gets its own folder inside `output/`:

```
output/
└── consulting_agreement_techcorp_2026-02-17/
    └── consulting_agreement_techcorp_2026-02-17.docx

output/
└── event_invitation_annual_gala_2026-02-17/
    ├── event_invitation_annual_gala_2026-02-17.html
    └── event_invitation_annual_gala_2026-02-17.pdf
```

The job folder and filenames follow the pattern `{template_name}_{key_variable}_{date}`:
- `key_variable` is the most identifying variable (typically a person/company name) — slugified (lowercase, underscores, no special characters).
- `date` is today's date in `YYYY-MM-DD` format.

### Docx rendering

```python
from docxtpl import DocxTemplate
import os
from datetime import date

template_path = "<path to template docx>"
output_dir = "<path to output/>"

doc = DocxTemplate(template_path)
context = {
    # all variable_name: value pairs
    # boolean values as True/False
    # loop collections as lists of dicts
}
doc.render(context)

# Build job folder and filename
key_var = context.get("<most_identifying_variable>", "document")
slug = key_var.lower().replace(" ", "_").replace(".", "")
job_name = f"<template_name>_{slug}_{date.today().isoformat()}"
job_dir = os.path.join(output_dir, job_name)
os.makedirs(job_dir, exist_ok=True)

output_path = os.path.join(job_dir, f"{job_name}.docx")
doc.save(output_path)
print(f"Saved: {output_path}")
```

**Note:** `docxtpl` natively supports Jinja2 `{% if %}`, `{% else %}`, `{% endif %}`, `{% for %}`, and `{% endfor %}` tags. No special handling is needed — just pass the context with correctly-typed values.

### HTML rendering

```python
from jinja2 import Template
import weasyprint
import os
from datetime import date

template_path = "<path to template html>"
output_dir = "<path to output/>"

with open(template_path) as f:
    template = Template(f.read())

context = {
    # all variable_name: value pairs
    # boolean values as True/False
    # loop collections as lists of dicts
}
rendered_html = template.render(context)

# Build job folder and filename
key_var = context.get("<most_identifying_variable>", "document")
slug = key_var.lower().replace(" ", "_").replace(".", "")
job_name = f"<template_name>_{slug}_{date.today().isoformat()}"
job_dir = os.path.join(output_dir, job_name)
os.makedirs(job_dir, exist_ok=True)

# Save rendered HTML
html_path = os.path.join(job_dir, f"{job_name}.html")
with open(html_path, "w") as f:
    f.write(rendered_html)
print(f"Saved HTML: {html_path}")

# Convert to PDF
pdf_path = os.path.join(job_dir, f"{job_name}.pdf")
weasyprint.HTML(filename=html_path).write_pdf(pdf_path)
print(f"Saved PDF: {pdf_path}")
```

**Note:** Jinja2 natively handles `{% if %}`, `{% else %}`, `{% endif %}`, `{% for %}`, and `{% endfor %}` tags. No special handling is needed.

### Edge cases
- All variables in the manifest MUST have values — never render with blanks.
- If a value is missing, report it back to the orchestrator so it can re-collect from the user.
- Boolean values that are `False` will cause `{% if var %}` sections to be excluded and `{% else %}` sections to be included — this is correct and expected.
- Loop collections that are empty lists will produce no output for `{% for %}` sections — warn if `min_items` was supposed to be enforced.

---

## Step 3 — Validate Rendered Document

After rendering, scan the output to confirm all placeholders and control tags were processed.

### For docx output

1. Open the rendered docx with `python-docx`.
2. Scan all text content — paragraphs, tables, headers, footers — for any remaining `{{ ... }}` placeholders using the regex: `\{\{\s*([\w.]+)\s*\}\}`.
3. Also scan for any remaining `{% ... %}` control tags using the regex: `\{%.*?%\}`. These indicate unprocessed conditionals or loops.

### For HTML output

1. Read the rendered HTML file as text.
2. Scan for any remaining `{{ ... }}` placeholders using the regex: `\{\{\s*([\w.]+)\s*\}\}`. Do this on the rendered HTML (the HTML is the source of truth).
3. Also scan for any remaining `{% ... %}` control tags using the regex: `\{%.*?%\}`.

### For both formats

4. If **no placeholders or control tags remain**: validation passes. Report success.
5. If **unfilled placeholders are found** (`{{ }}`):
   - List the variable names that were not replaced.
   - Check whether those variables exist in the manifest — if they do, something went wrong in rendering; if they don't, the template may have placeholders the Analyzer missed (e.g., in docx, inside complex formatting runs that split the `{{ }}` tokens across multiple XML elements).
   - Report the issue back to the orchestrator so it can inform the user and offer to re-collect and re-render.
   - Do NOT deliver a document with unfilled placeholders.
6. If **unprocessed control tags are found** (`{% %}`):
   - This indicates a rendering failure — the template engine did not process a conditional or loop block.
   - Common causes: boolean value passed as a string instead of `True`/`False`, missing loop collection, or malformed template syntax.
   - Report the issue back to the orchestrator.
   - Do NOT deliver a document with unprocessed control tags.

---

## Step 4 — Report Results

Return to the orchestrator:
- The path(s) to the rendered document(s) (docx, or html + pdf)
- Whether validation passed or failed
- If failed: the list of unfilled variable names and/or unprocessed control tags

---

## Important Notes

- **Never modify template files** — only read them.
- **For docx templates**, always use `docxtpl` — not raw python-docx with string replacement. `docxtpl` preserves formatting around placeholders and natively supports Jinja2 control tags.
- **For HTML templates**, use `jinja2.Template` for rendering and `weasyprint` for PDF conversion.
- **Boolean coercion is critical** — always ensure boolean gate variables are Python `True`/`False` before rendering. A string `"false"` is truthy in Jinja2 and will cause incorrect conditional evaluation.
- **Use `uv`** for Python package management.
- **Format any Python code** in the style of black.
