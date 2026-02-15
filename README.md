![Codraft Logo](./docs/logo.png)
# Codraft

A document assembly tool built on Claude Cowork. Codraft replaces traditional document automation platforms (docassemble, HotDocs) by using Claude to interview users, collect field values, and produce completed documents from templates.

## How It Works

1. Place your templates in `templates/`, each in its own subdirectory
2. Add `{{ variable_name }}` placeholders wherever you need dynamic content
3. Ask Claude to "prepare a [document type]"
4. Claude walks you through a conversational interview, collecting all the field values
5. A completed document is rendered and saved to a job folder in `output/`

Two template formats are supported:
- **`.docx`** — rendered via `docxtpl`, produces a Word document
- **`.html`** — rendered via `jinja2`, produces both an HTML file and a PDF (via `weasyprint`)

## Installation

### Prerequisites

You'll need a [Claude Cowork](https://claude.ai) account.

### Download Codraft

1. On the Codraft GitHub page, click the green **Code** button, then click **Download ZIP**
2. Extract the ZIP file to a folder of your choice (e.g., your Documents folder)

### Open in Cowork

1. Open Claude Cowork and add the extracted folder as a project
2. That's it — Python dependencies are installed automatically the first time you use the skill

## Quick Start

### 1. Add a template

Create a subdirectory in `templates/` and place your template file inside:

```
templates/
└── nda/
    └── nda.docx      ← contains {{ disclosing_party_name }}, {{ effective_date }}, etc.
```

Or for an HTML template:

```
templates/
└── invoice/
    └── invoice.html  ← same {{ variable }} syntax, styled with CSS
```

### 2. Prepare a document

Tell Claude:

> "I need to prepare an NDA"

Claude will find the template, extract its variables, and interview you for the values — grouping related fields together for a natural flow.

### 3. Get your document

After confirming all values, the rendered document is saved to a job folder:

```
output/
└── nda_acme_pte_ltd_2026-02-15/
    └── nda_acme_pte_ltd_2026-02-15.docx
```

For HTML templates, both the HTML and PDF are saved:

```
output/
└── invoice_acme_2026-02-15/
    ├── invoice_acme_2026-02-15.html
    └── invoice_acme_2026-02-15.pdf
```

## Template Authoring

### Placeholders

Use Jinja2-style double-brace syntax in both `.docx` and `.html` templates:

```
This Agreement is entered into by {{ disclosing_party_name }}
(the "Disclosing Party") with address at {{ disclosing_party_address }}.
```

### Variable Naming Conventions

Name your variables with descriptive suffixes for automatic type inference:

| Suffix | Inferred type | Example |
|--------|--------------|---------|
| `*_name` | text | `landlord_name` |
| `*_address` | text | `property_address` |
| `*_date` | date | `commencement_date` |
| `*_email` | email | `tenant_email` |
| `*_amount`, `*_price`, `*_fee` | number | `rental_amount` |
| `*_phone`, `*_tel`, `*_mobile` | phone | `contact_phone` |
| (other) | text | `governing_law` |

### Rules

- One template file per directory (`.docx` or `.html`, not both)
- Use `{{ }}` with spaces around the variable name: `{{ name }}` not `{{name}}`
- Variable names must be valid Python identifiers: lowercase, underscores, no spaces
- The same variable can appear multiple times in the document — it will be filled with one value

## Project Structure

```
codraft/
├── CLAUDE.md                    # Project instructions for Claude
├── README.md                    # This file
├── LICENSE                      # MIT License
├── codraft_mvp_spec.md          # Full MVP specification
├── .gitignore
├── .claude/
│   └── skills/
│       └── codraft/
│           └── SKILL.md         # Orchestrator skill
├── templates/
│   ├── _examples/               # Bundled example templates (tracked in git)
│   │   └── nda/
│   │       └── nda.docx
│   └── <your_template>/         # Your templates (gitignored)
│       ├── <name>.docx or .html
│       └── manifest.yaml        # Auto-generated (do not edit)
└── output/                      # Rendered documents (gitignored)
    └── <job_name>/              # One folder per rendering job
```

## Technical Details

- **Template engines:** `docxtpl` for docx (preserves formatting), `jinja2` + `weasyprint` for HTML→PDF
- **Python environment:** managed with `uv`
- **Manifest caching:** variable analysis is cached in `manifest.yaml` per template and only regenerated when the template file changes

## MVP Scope

This version supports simple variable substitution: `{{ variable_name }}` placeholders with no conditional logic, loops, or computed fields. See `codraft_mvp_spec.md` for the full specification and future roadmap.

## License

MIT — see [LICENSE](LICENSE).
