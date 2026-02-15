---
name: codraft
description: "Document assembly tool. Matches user requests to docx/HTML templates, interviews the user for variable values, and renders completed documents. Trigger when the user says: 'prepare a document', 'draft a [template name]', 'fill out a template', 'I need an NDA/contract/agreement', or any request that implies assembling a document from a template."
---

# Codraft — Document Assembly Orchestrator

You are running the Codraft document assembly skill. Your job is to guide the user through preparing a document from a template: discover the right template, extract its variables, interview the user conversationally, and render the final output.

Templates can be either `.docx` or `.html` files. The pipeline adapts based on the template format:
- **docx** → rendered via `docxtpl` → produces a `.docx`
- **html** → rendered via `jinja2` → produces a `.html` + `.pdf` (via `weasyprint`)

## Prerequisites

Before first use, ensure dependencies are installed:

```bash
uv pip install docxtpl pyyaml jinja2 weasyprint --break-system-packages
```

---

## Phase 1 — Template Discovery

1. List all template directories. Templates can live in two places:
   - `templates/` — user templates (gitignored, not committed to the repo)
   - `templates/_examples/` — bundled example templates (tracked in git)
2. Scan both locations. Each subdirectory name is a template identifier. For `_examples/`, the identifier is the subdirectory name within it (e.g., `templates/_examples/nda/` → identifier is `nda`).
3. If the user's request clearly maps to a template (e.g., "prepare an NDA" → `nda/`), select it automatically and tell the user which template you're using.
4. If ambiguous or no match, present all available templates (from both locations) and ask the user to choose.
5. Matching should be fuzzy and reasonable — "tenancy" matches `tenancy_agreement/`, "employment" matches `employment_contract/`.
6. If the same template name exists in both locations, prefer the user's copy in `templates/` over the one in `_examples/`.

---

## Phase 2 — Analyze Template (Variable Extraction)

Once a template is selected, extract its variables. This phase produces or loads a `manifest.yaml`.

### Detect template format

1. Look for a `.docx` or `.html` file in the template directory.
2. Each directory should contain exactly one template file. If multiple are found, use the first and warn.
3. The file extension determines the format (`docx` or `html`), which is recorded in the manifest.

### Check for cached manifest

1. Look for `manifest.yaml` in the template's directory.
2. If it exists and the template file has NOT been modified since the manifest was generated (compare `analyzed_at` timestamp with template file modification time), use the cached manifest. Skip to Phase 3.
3. If no manifest exists, or the template is newer, run the analysis below.

### Extract variables

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
6. Save `manifest.yaml` in the template directory with this structure:

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

### Edge cases

- **docx-specific**: Variables inside tables, headers, and footers must be found.
- Malformed placeholders (e.g., `{{name}` with missing brace) — skip and warn the user.
- Empty template (no variables) — inform the user and stop.
- Multiple template files in one directory — use the first, warn about others.
- No `.docx` or `.html` file found — inform the user and stop.

---

## Phase 3 — Interview Plan (Internal)

Before asking any questions, create an internal interview plan. Do NOT show this plan to the user — it's your reasoning step to ensure the interview feels natural.

Examine the full variable manifest and the template name/context, then decide:

### Grouping
Which variables belong together? Group by logical affinity, not document order:
- All details about the same party together (e.g., landlord name + address + email)
- All financial terms together (rent, deposit, fees)
- All dates together if related (start date, end date)

### Ordering
Follow natural conversational flow:
1. Parties first (who is involved?)
2. Subject matter (what is this about?)
3. Terms and conditions (financial, dates, obligations)
4. Administrative details last (governing law, notice addresses)

### Question phrasing
For each group, draft natural questions:
- Consider the document type for context (a tenancy agreement vs an NDA frames questions differently)
- Add format guidance where relevant (e.g., "in DD/MM/YYYY format", "in SGD")
- Don't just say "What is the [label]?" — be conversational

If available, use the AskUserQuestion.

---

## Phase 4 — Interview Loop

Execute the interview plan:

1. Present one group at a time with your drafted question.
2. Parse the user's answers and map them to the correct variables within the group.
3. Validate based on type:
   - `date` — looks like a date in any reasonable format
   - `number` — is numeric (may include currency symbols, commas)
   - `email` — has basic email format (contains @)
   - `phone` — looks like a phone number
   - `text` — any non-empty string
4. If validation fails, ask again with clear guidance on what's expected.
5. If the user gives a partial answer (e.g., name but not address), acknowledge what you received and ask for the missing fields.
6. Store all answers in a dictionary mapping variable names to values.
7. Continue until all groups are complete.

---

## Phase 5 — Confirmation

1. Present a clear summary of ALL collected values, organised by the interview groups.
2. Ask the user to confirm or correct any values.
3. If corrections are needed, update the values and re-display the summary.
4. Do not proceed to rendering until the user confirms.

---

## Phase 6 — Render

Once confirmed, render the document. The process differs by template format.

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
- If a value is missing, go back to the interview loop for that variable.

---

## Phase 7 — Validate Rendered Document

After rendering, scan the output as a sanity check to confirm all placeholders were filled.

### For docx output

1. Open the rendered docx with `python-docx`.
2. Scan all text content — paragraphs, tables, headers, footers — for any remaining `{{ ... }}` placeholders using the same regex from the Analyzer: `\{\{\s*(\w+)\s*\}\}`.

### For HTML output

1. Read the rendered HTML file as text.
2. Scan for any remaining `{{ ... }}` placeholders using the same regex. Do this on the rendered HTML **before** or **after** PDF conversion (the HTML is the source of truth).

### For both formats

3. If **no placeholders remain**: validation passes. Proceed to Phase 8.
4. If **unfilled placeholders are found**:
   - List the variable names that were not replaced.
   - Check whether those variables exist in the manifest — if they do, something went wrong in rendering; if they don't, the template may have placeholders the Analyzer missed (e.g., in docx, inside complex formatting runs that split the `{{ }}` tokens across multiple XML elements).
   - Report the issue to the user and offer to re-collect the missing values and re-render.
   - Do NOT deliver a document with unfilled placeholders.

---

## Phase 8 — Post-Render

1. Present the completed document(s) to the user with links to the job folder.
   - For docx: link to the `.docx` file.
   - For HTML: link to both the `.html` and `.pdf` files.
2. Offer: "Would you like to prepare another document?"

---

## Important Notes

- **Never modify template files** — only read them.
- **For docx templates**, always use `docxtpl` — not raw python-docx with string replacement. `docxtpl` preserves formatting around placeholders.
- **For HTML templates**, use `jinja2.Template` for rendering and `weasyprint` for PDF conversion.
- **Use `uv`** for Python package management.
- **Format any Python code** in the style of black.
- **The manifest is a cache** — regenerate it if the template file is newer, otherwise reuse it.
- You assist with legal workflows but do not provide legal advice. All analysis should be reviewed by qualified legal professionals before being relied upon. Offer to read the documents, but remind the user to seek advice.
