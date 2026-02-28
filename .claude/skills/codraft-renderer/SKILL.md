---
name: codraft-renderer
description: "Document renderer for Codraft. Takes a template, variable values, and produces rendered documents (docx or html+pdf). Validates output for unfilled placeholders. Called by the codraft orchestrator — not triggered directly by the user."
---

# Codraft — Document Renderer (v2)

You are running the Codraft document renderer. Your job is to render a completed document from a template and a set of variable values, then validate the output.

This skill is called by the Codraft orchestrator. You receive:
- **Template path** (e.g., `templates/_examples/Bonterms_Mutual_NDA/Bonterms-Mutual-NDA.docx`)
- **Format** (`docx`, `html`, or `markdown`)
- **Variable dictionary** — all collected values, including:
  - Flat key-value pairs for simple and conditional variables
  - Boolean values as Python `True`/`False` (not strings like `"yes"` or `"no"`)
  - Lists of dictionaries for loop collections (e.g., `"milestones": [{"description": "...", "date": "..."}, ...]`)
- **Output directory** (e.g., `output/`)

## Prerequisites

Ensure core rendering dependencies are installed:

```bash
command -v uv > /dev/null 2>&1 \
  && uv pip install docxtpl pyyaml jinja2 \
  || pip install docxtpl pyyaml jinja2
```

Install on-demand tools based on format and PDF intent:

| Format | Outputs | PDF tool |
|---|---|---|
| `docx` | `.docx` + optional `.pdf` | `docx2pdf` (if Word available) → LibreOffice headless (auto-installed) |
| `html` | `.html` + `.pdf` (always) | `weasyprint` |
| `markdown` | `.md` + optional `.pdf` (soft-fail) | `markdown` library → `weasyprint` |

For HTML: also install `weasyprint`. For Markdown: also install `markdown` and `weasyprint`.

---

## Step 1 — Prepare Context

Before rendering, ensure the variable dictionary is properly formatted for the template engine.

### Boolean Coercion

Boolean gate variables must be Python `True`/`False`, not string representations. The script handles this automatically, but ensure the values you pass are correct. A string `"false"` is truthy in Jinja2 and would incorrectly include conditional sections.

### Loop Data

Loop collections should be lists of dictionaries:

```python
# Example expected structure for milestones loop:
# context["milestones"] = [
#     {"description": "Design phase", "due_date": "2026-03-15", "amount": "5000"},
#     {"description": "Development", "due_date": "2026-04-30", "amount": "10000"},
# ]
```

### Edge cases
- All variables in the manifest MUST have values — never render with blanks.
- If a value is missing, report it back to the orchestrator so it can re-collect from the user.
- Boolean values that are `False` will cause `{% if var %}` sections to be excluded and `{% else %}` sections to be included — this is correct and expected.
- Loop collections that are empty lists will produce no output for `{% for %}` sections — warn if `min_items` was supposed to be enforced.

---

## Step 2 — Write Context and Run Render Script

### Output structure

Each rendering job gets its own folder inside `output/`:

```
output/
└── bonterms_mutual_nda_acme_corp_2026-02-28/
    ├── bonterms_mutual_nda_acme_corp_2026-02-28.docx
    └── bonterms_mutual_nda_acme_corp_2026-02-28.pdf   ← when tooling available
```

The job folder and filenames follow the pattern `{template_name}_{key_variable}_{date}`:
- `key_variable` is the most identifying variable (typically a person/company name) — slugified (lowercase, underscores, no special characters).
- `date` is today's date in `YYYY-MM-DD` format.

### 2a — Write context.json

Write the full variable dictionary as a JSON file. The Orchestrator provides all collected values; you serialize them to a temporary file that the render script will read.

```python
import json, tempfile
context = {
    # all variable_name: value pairs from the orchestrator
}
context_file = tempfile.mktemp(suffix=".json")
with open(context_file, "w") as f:
    json.dump(context, f)
```

### 2b — Resolve script path

```python
import os
script = os.path.join(
    os.environ.get("CLAUDE_PLUGIN_ROOT", ""),
    "scripts", "render.py"
)
```

If `CLAUDE_PLUGIN_ROOT` is not set, the path resolves to `scripts/render.py` relative to the current working directory (project root).

### 2c — Run the render script

```bash
python <script_path> \
  --template <template_path> \
  --format <docx|html|markdown> \
  --context <context_file> \
  --output-dir <output_dir> \
  --job-name <job_name> \
  [--pdf]
```

The script handles:
- Boolean coercion (string "true"/"yes"/"y" → `True`, "false"/"no"/"n" → `False`)
- Job folder creation with deduplication (appends `_2`, `_3`, etc. if folder exists)
- Template rendering (docx via `docxtpl`, html/markdown via `jinja2`)
- PDF conversion (docx: `docx2pdf` → `soffice` fallback; html: `weasyprint`; markdown: `markdown` + `weasyprint`)
- Output validation (scans for unfilled `{{ }}` and `{% %}` tags)

The script prints a JSON result to stdout:

```json
{
  "job_dir": "output/some_job_name/",
  "files": ["output/some_job_name/file.docx"],
  "pdf_produced": true,
  "pdf_warning": null,
  "validation": {"passed": true, "unfilled_variables": [], "unprocessed_tags": []}
}
```

### 2d — Cowork DOCX → PDF fallback

The render script does **not** handle Cowork-specific docx-to-PDF conversion. If you are running inside Cowork (check for `/home/user/.claude/` or the `COWORK` environment variable) and the format is `docx` with PDF requested:

1. Run the render script **without** `--pdf` to produce the `.docx`.
2. Use the Cowork built-in `docx` skill to read the rendered `.docx` file.
3. Use the Cowork built-in `pdf` skill to produce a `.pdf` from it.
4. Save the resulting PDF to the job folder as `{job_name}.pdf`.

Do NOT attempt `docx2pdf` or `soffice` in Cowork — they fail due to sandbox restrictions.

---

## Step 3 — Interpret Validation Results

The render script's JSON output includes a `validation` object. Interpret it as follows:

- **`validation.passed == true`**: All placeholders and control tags were processed. The document is ready.
- **`validation.unfilled_variables`** (non-empty): Lists variable names that remain as `{{ var }}` in the rendered output. Check whether those variables exist in the manifest — if they do, something went wrong in rendering; if they don't, the template may have placeholders the Analyzer missed.
- **`validation.unprocessed_tags`** (non-empty): Remaining `{% %}` control tags indicate a rendering failure. Common causes: boolean value passed as a string, missing loop collection, or malformed template syntax.

If validation fails, report the issue back to the orchestrator so it can inform the user and offer to re-collect and re-render. Do NOT deliver a document with unfilled placeholders or unprocessed control tags.

---

## Step 4 — Report Results

Return to the orchestrator:
- The `job_dir` and `files` list from the script's JSON output
- Whether validation passed or failed
- If failed: the list of unfilled variable names and/or unprocessed control tags
- Whether PDF was produced (`pdf_produced`). If not, include the `pdf_warning` text so the Orchestrator can relay it to the user.

**Soft-fail semantics for PDF:** Always deliver the primary document (`.docx`, `.html`, or `.md`). Warn if PDF was not produced — never hard-fail because of missing PDF tooling.

---

## Important Notes

- **Never modify template files** — only read them.
- **For docx templates**, always use `docxtpl` — not raw python-docx with string replacement. `docxtpl` preserves formatting around placeholders and natively supports Jinja2 control tags.
- **PDF output for docx templates** — In Cowork, use the built-in `docx` and `pdf` skills (see Step 2d). Outside Cowork, the render script handles `docx2pdf` with LibreOffice fallback. PDF is always soft-fail.
- **Boolean coercion is critical** — the render script coerces automatically, but ensure the orchestrator passes correctly-typed values when possible.
- **Use `uv`** for Python package management.
- **Format any Python code** in the style of black.
