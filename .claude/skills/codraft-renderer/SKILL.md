---
name: codraft-renderer
description: "Document renderer for Codraft. Takes a template, variable values, and produces rendered documents (docx or html+pdf). Validates output for unfilled placeholders. Called by the codraft orchestrator — not triggered directly by the user."
---

# Codraft — Document Renderer

You are running the Codraft document renderer. Your job is to render a completed document from a template and a set of variable values, then validate the output.

This skill is called by the Codraft orchestrator. You receive:
- **Template path** (e.g., `templates/nda/nda.docx`)
- **Format** (`docx` or `html`)
- **Variable dictionary** (all variable_name: value pairs)
- **Output directory** (e.g., `output/`)

## Prerequisites

Ensure dependencies are installed:

```bash
uv pip install docxtpl pyyaml jinja2 weasyprint --break-system-packages
```

---

## Step 1 — Render

### Output structure

Each rendering job gets its own folder inside `output/`:

```
output/
└── nda_acme_pte_ltd_2026-02-15/
    └── nda_acme_pte_ltd_2026-02-15.docx

output/
└── invoice_acme_2026-02-15/
    ├── invoice_acme_2026-02-15.html
    └── invoice_acme_2026-02-15.pdf
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

### Edge cases
- All variables in the manifest MUST have values — never render with blanks.
- If a value is missing, report it back to the orchestrator so it can re-collect from the user.

---

## Step 2 — Validate Rendered Document

After rendering, scan the output to confirm all placeholders were filled.

### For docx output

1. Open the rendered docx with `python-docx`.
2. Scan all text content — paragraphs, tables, headers, footers — for any remaining `{{ ... }}` placeholders using the regex: `\{\{\s*(\w+)\s*\}\}`.

### For HTML output

1. Read the rendered HTML file as text.
2. Scan for any remaining `{{ ... }}` placeholders using the same regex. Do this on the rendered HTML (the HTML is the source of truth).

### For both formats

3. If **no placeholders remain**: validation passes. Report success.
4. If **unfilled placeholders are found**:
   - List the variable names that were not replaced.
   - Check whether those variables exist in the manifest — if they do, something went wrong in rendering; if they don't, the template may have placeholders the Analyzer missed (e.g., in docx, inside complex formatting runs that split the `{{ }}` tokens across multiple XML elements).
   - Report the issue back to the orchestrator so it can inform the user and offer to re-collect and re-render.
   - Do NOT deliver a document with unfilled placeholders.

---

## Step 3 — Report Results

Return to the orchestrator:
- The path(s) to the rendered document(s) (docx, or html + pdf)
- Whether validation passed or failed
- If failed: the list of unfilled variable names

---

## Important Notes

- **Never modify template files** — only read them.
- **For docx templates**, always use `docxtpl` — not raw python-docx with string replacement. `docxtpl` preserves formatting around placeholders.
- **For HTML templates**, use `jinja2.Template` for rendering and `weasyprint` for PDF conversion.
- **Use `uv`** for Python package management.
- **Format any Python code** in the style of black.
