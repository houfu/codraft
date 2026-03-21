# CoQuill

CoQuill is a document assembly tool built as a Claude Code plugin. It interviews users conversationally, collects the information needed to fill in a template, and renders completed documents. Templates support variable substitution, conditional sections, loops, and optional developer configuration.

## Installation

Install CoQuill in Claude Code:

```
/plugin marketplace add houfu/coquill
/plugin install coquill@coquill
```

## Quick Start

Once installed, ask Claude to prepare a document with CoQuill using one of the built-in example templates:

- "Prepare an NDA with CoQuill"
- "Prepare an invoice with CoQuill"

Claude will walk you through an interview, asking for the information needed to complete the document, then render the final output.

## Adding Your Own Templates

Create a `templates/` directory in your project and add a subdirectory for each template:

```
your-project/
  templates/
    my_contract/
      my_contract.docx
    offer_letter/
      offer_letter.html
```

Each template directory should contain a single `.docx` or `.html` file using Jinja2-style placeholders:

```
This Agreement is entered into by {{ party_name }} on {{ effective_date }}.
```

You can also add an optional `config.yaml` alongside the template to customize interview questions, group related fields, add validation rules, and define choice types.

## Documentation

For full documentation on template authoring, config.yaml options, conditional logic, loops, and more, visit:

https://github.com/houfu/coquill
