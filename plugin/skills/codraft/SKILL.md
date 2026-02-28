---
name: codraft
description: "Document assembly tool. Matches user requests to docx/HTML templates, interviews the user for variable values, and renders completed documents. Supports conditional sections, loops, and developer-configured interview flows. Trigger when the user says: 'prepare a document', 'draft a [template name]', 'fill out a template', 'I need an NDA/contract/agreement', or any request that implies assembling a document from a template."
---

# Codraft — Document Assembly Orchestrator (v2)

You are running the Codraft document assembly skill. Your job is to guide the user through preparing a document from a template: discover the right template, analyze it for variables and logic, interview the user conversationally (including conditional sections and repeating items), confirm their answers, and render the final output.

Templates can be `.docx`, `.html`, or `.md` files. The pipeline adapts based on the template format:
- **docx** -> rendered via `docxtpl` -> produces `.docx` + `.pdf` (when docx2pdf or LibreOffice available)
- **html** -> rendered via `jinja2` -> produces a `.html` + `.pdf` (via `weasyprint`)
- **md** -> rendered via `jinja2` -> produces `.md` + optional `.pdf` (via `markdown` + `weasyprint`)

v2 templates may contain conditional sections (`{% if %}` / `{% else %}`) and loops (`{% for %}`). The interview adapts: it skips irrelevant questions and collects lists when needed.

## Prerequisites

Before first use, ensure dependencies are installed:

```bash
command -v uv > /dev/null 2>&1 \
  && uv pip install docxtpl pyyaml jinja2 \
  || pip install docxtpl pyyaml jinja2
```

---

## Phase 1 — Template Discovery

1. List all template directories. Templates can live in multiple locations, checked in this priority order:
   - `templates/` — user templates in the current working directory (highest priority)
   - `${CLAUDE_PLUGIN_ROOT}/templates/_examples/` — bundled templates when running as a Claude Code plugin (if `CLAUDE_PLUGIN_ROOT` is set)
   - `templates/_examples/` — bundled example templates in Cowork context (fallback when `CLAUDE_PLUGIN_ROOT` is not set)
2. Scan all applicable locations. Each subdirectory name is a template identifier. For bundled locations, the identifier is the subdirectory name within `_examples/` (e.g., `_examples/nda/` → identifier is `nda`).
3. When `CLAUDE_PLUGIN_ROOT` is set (plugin context), search `${CLAUDE_PLUGIN_ROOT}/templates/_examples/` for bundled templates and label them "(built-in)" when listing them to the user.
4. When `CLAUDE_PLUGIN_ROOT` is not set (Cowork context), fall back to `templates/_examples/` relative to the working directory.
5. If the user's request clearly maps to a template (e.g., "prepare an NDA" → `nda/`), select it automatically and tell the user which template you're using.
6. If ambiguous or no match, present all available templates (from all locations) and ask the user to choose.
7. Matching should be fuzzy and reasonable — "tenancy" matches `tenancy_agreement/`, "meeting" matches `meeting_notes/`.
8. If the same template name exists in both user `templates/` and a bundled location, prefer the user's copy.
9. If the template has `meta.display_name` in its manifest, use that when presenting to the user.
10. Note the user's exact opening request — the message that triggered this skill. Store it as `session_request` for use in the interview log (Phase 3d).

---

## Phase 2 — Analyze Template

Once a template is selected, run the **codraft-analyzer** skill on the template directory. It will:
- Detect the template format (docx or html)
- Check for a cached manifest (regenerate if template is newer or manifest is v1)
- Extract variables from `{{ }}` placeholders
- Detect conditional blocks (`{% if %}` / `{% else %}` / `{% endif %}`)
- Detect loop blocks (`{% for %}` / `{% endfor %}`)
- Merge overrides from `config.yaml` if present
- Save or reuse `manifest.yaml`

Load the resulting `manifest.yaml` and proceed. The manifest is the single source of truth for the interview — you never read `config.yaml` directly.

### Understanding the Manifest

The v2 manifest contains:

- **`schema_version`**: Always `2`. If you encounter a manifest without this field, re-run the analyzer.
- **`variables`**: Unconditional variables — always collected during the interview.
- **`conditionals`**: Variables gated by `{% if %}` / `{% else %}` blocks. Each entry has:
  - `condition`: The condition expression (e.g., `"include_ip_assignment"` or `"payment_method == 'bank_transfer'"`)
  - `gate_type`: `"boolean"` (truthiness) or `"equality"` (value match)
  - `gate_variable`: For equality conditions, which variable to check
  - `gate_value`: For equality conditions, what value triggers the if-branch
  - `if_variables`: Variables to collect when the condition is true
  - `else_variables`: Variables to collect when the condition is false
- **`loops`**: Repeating sections. Each entry has:
  - `collection`: The collection variable name (e.g., `"milestones"`)
  - `loop_var`: The iteration alias (e.g., `"milestone"`)
  - `label`: Human-readable label for the loop
  - `min_items`: Minimum items required (default 1)
  - `variables`: Sub-variables per item
- **`dependencies`**: Map of gate variable -> list of dependent variable names. Used for quick lookups.
- **`groups`**: Optional interview structure from `config.yaml`. If present, use it. If absent, auto-group.
- **`validation`**: Optional cross-field validation rules.
- **`meta`**: Optional display name, description, category.

---

## Phase 3 — Interview Plan (Internal)

Before asking any questions, create an internal interview plan. Do NOT show this plan to the user — it is your reasoning step to ensure the interview feels natural.

### Step 3a — Check for Groups

Read the manifest's `groups` section.

**If `groups` is present** (provided by the template developer via `config.yaml`):
- Use the groups as-is for your interview structure.
- Each group specifies its variables and may have:
  - `condition`: A conditional gate (the group is only asked if the condition is met)
  - `loop`: A loop collection name (the group collects a list of items)
- Ensure gate variables are asked before the groups they gate. Gate variables may appear in an earlier unconditional group.

**If `groups` is absent**, auto-group:
1. Separate unconditional variables into logical groups by affinity (same as v1):
   - Party details together (names, addresses, emails of the same entity)
   - Financial terms together
   - Related dates together
2. Identify gate variables (from `dependencies`) and ensure they are placed in groups that come **before** their dependent conditional groups.
3. Create one group per conditional block containing its `if_variables` (and `else_variables` if any).
4. Create one group per loop block, placed last.

### Step 3b — Determine Group Order

Order the groups for a natural conversational flow:

1. **Unconditional groups** first — parties, subject matter, terms, administrative details
2. **Conditional groups** interleaved after their gate variables have been collected
3. **Loop groups** last — these collect lists and are naturally the final step

### Step 3c — Plan Questions

For each group, draft natural questions:
- If the manifest provides a `question` for a variable, use it.
- Otherwise, consider the document type for context and phrase conversationally.
- For `choice` type variables: present the available options from `choices`.
- For `boolean` type variables: phrase as a yes/no question.
- For `date` type variables: include format guidance if `format_hint` is provided.
- For variables with a `default` value: mention the default (e.g., "When should this take effect? (defaults to today)").
- Add format guidance from `format_hint` where available.

If available, use the AskUserQuestion tool.

### Step 3d — Initialize Interview Log

Create an internal interview log — an ordered sequence of entries you will append to during
Phases 4 and 5. It is never shown to the user mid-interview. In Phase 7a you will serialize
it to `interview_log.json` in the job folder before invoking the codraft-transcriber skill.

Initialize the log with one entry:

  type: session_start
  request: <session_request captured in Phase 1 — user's verbatim opening message>
  template: <manifest meta.display_name, or title-cased template dir name>
  started_at: <current date/time, ISO 8601>

Entry types appended during Phases 4 and 5:
  prefill       — variable(s) extracted from the user's opening message or volunteered
                  out of order before being asked (list of {name, label, value})
  group_start   — begins a named group (include branch: "if"/"else"/"skipped" for conditionals)
  question      — the question(s) asked in one conversational turn (the effective final question)
  clarification — a user question + Claude's response that occurred between a question and
                  its answer (user_question, claude_response). Only log substantive
                  clarifications about document meaning — not pleasantries or re-phrasings.
  answer        — the effective final answer for the preceding question, near-verbatim
  validation_retry — a re-ask after failed validation, with brief reason
  skip          — a variable or group skipped because it was pre-filled or not applicable,
                  with human-readable reason
  loop_item     — one confirmed loop item (index, question, answer, values dict)
  correction    — a Phase 5 edit (field, label, old_value, new_value, optional note)

This log is scoped to ONE document assembly. Reset it at the start of Phase 3d whenever
you begin preparing a new document.

---

## Phase 4 — Interview Loop

Execute the interview plan, group by group.

**Before Phase 4a begins — pre-filled variables:**

If the user's opening message (Phase 1) or any early free-form response contained variable
values (e.g., "I need an NDA for TechCorp" provides `party_name = TechCorp`), append a
`prefill` entry before the first `group_start` with the list of pre-extracted variables.
When those variables come up in the interview plan, append a `skip` entry noting they were
pre-filled rather than asked.

### 4a — Unconditional Groups

For each unconditional group:
1. Present the group with your drafted question(s).
2. Parse the user's answers and map them to the correct variables.
3. Validate based on type:
   - `text` — any non-empty string
   - `date` — looks like a date in any reasonable format
   - `number` — is numeric (may include currency symbols, commas)
   - `email` — has basic email format (contains @)
   - `phone` — looks like a phone number
   - `boolean` — yes/no, true/false, or similar affirmative/negative
   - `choice` — matches one of the values in `choices`
4. If validation fails, ask again with clear guidance.
5. If the user gives a partial answer, acknowledge what you received and ask for the missing fields.
6. If a variable has a `default` and the user doesn't provide a value, use the default. Special default `"today"` resolves to the current date.
7. Store answers in the variable dictionary.
8. Append to the interview log:
   - A `group_start` entry once per group, before the first question in that group
   - A `question` entry for the effective question(s) asked
   - If the user asked a clarifying question before answering (e.g., "What does 'effective date'
     mean?"), append a `clarification` entry with the user's question and Claude's response,
     between the `question` and `answer` entries
   - An `answer` entry for the effective final answer, near-verbatim
   - If validation failed and you re-asked, prepend a `validation_retry` entry before the
     corrected `answer`
   - Log the **effective** exchange — the final question as asked and the final answer as given.
     Do not try to reconstruct every micro-turn; capture the substance.

### 4b — Conditional Groups

After collecting a gate variable's value, evaluate the condition:

**Boolean gate** (`gate_type: boolean`):
- `true` if the user answered yes/affirmative/true
- `false` otherwise

**Equality gate** (`gate_type: equality`):
- `true` if the collected value of `gate_variable` equals `gate_value`
- `false` otherwise

Then:
1. If condition is **true**: present the `if_variables` group and collect answers.
2. If condition is **false** and `else_variables` is non-empty: present the `else_variables` group and collect answers.
3. If condition is **false** and `else_variables` is empty: skip. Inform the user naturally (e.g., "Since you chose cheque, we'll skip the bank details section.").

When introducing a conditional group, provide context: "Since you indicated IP should be assigned, I'll need a few more details about that."

After handling the true/false/skip branch, append to the interview log:
- A `group_start` entry with the group name and `branch` field: `"if"`, `"else"`, or `"skipped"`
- If included (if or else-branch): `question` and `answer` entries for questions asked
- If skipped: a `skip` entry with gate variable name, value, and a readable reason
  (e.g., "Skipped 'IP Assignment' — include_ip_assignment was No")

### 4c — Loop Groups

For each loop group:

1. **Introduce**: Tell the user what you're collecting and that you'll ask one item at a time.
   - Example: "Now let's add the project milestones. I'll ask for each one individually."
2. **Collect first item**: Ask for all sub-variables as a group.
   - Example: "What's the description, due date, and amount for the first milestone?"
3. **Confirm the item**: Summarize what you captured.
   - Example: "Got it -- Milestone 1: 'Design phase', due 15 March 2026, $5,000."
3b. Append to the interview log:
    - A `group_start` entry with the loop group name (once, before item 1)
    - A `loop_item` entry per confirmed item: `item_index`, `question` (asked), `answer` (near-verbatim), `values` (parsed sub-variable dict)
4. **Prompt for more**: "Would you like to add another milestone?"
5. **Repeat** steps 2-4 for each additional item the user wants to add.
6. **Minimum check**: Ensure at least `min_items` (default 1) items are collected. If the user tries to stop before reaching the minimum, inform them: "At least [N] milestone(s) required. Let's add one more."
7. **Summary**: After the user finishes, summarize all items.
   - Example: "I have 3 milestones recorded: [numbered list]"

Store the collected data as a list of dictionaries under the collection name:

```
{
    "milestones": [
        {"description": "Design phase", "date": "2026-03-15", "amount": "5000"},
        {"description": "Development", "date": "2026-04-30", "amount": "10000"}
    ]
}
```

### 4d — Value Storage

Maintain a single variable dictionary throughout the interview. It contains:
- Flat key-value pairs for unconditional and conditional variables
- List-of-dicts values for loop collections
- Boolean variables stored as `true`/`false` (not "yes"/"no" strings)

---

## Phase 5 — Confirmation and Validation

### 5a — Summary Display

Present a clear summary of ALL collected values, organized by groups:

1. **Unconditional groups**: Show values as before.
2. **Conditional sections**: Show with gate status:
   - If the condition was **true** (section included): display the collected values under the group heading.
   - If the condition was **false** (section skipped): show the group name with "*Skipped (not applicable)*".
3. **Loop items**: Show as a numbered list under the group heading.

Example:

```
Meeting Details:
- Title: Q1 Sprint Retrospective
- Date: 28/02/2026
- Type: standup
- Facilitator: Sarah Chen
- Location: Room 3A

Attendees & Agenda:
- Attendees: Sarah Chen, James Wong, Lisa Park
- Agenda: Review sprint outcomes, discuss blockers

Discussion:
- Summary: Reviewed velocity trends and identified two recurring blockers.

Workshop Materials: *Skipped (meeting type is standup)*

Decisions:
- Decisions made: Yes
- Decisions: Move to two-week sprints starting March.

Action Items:
1. Update sprint board -- Assigned to: James Wong -- Due: 03/03/2026
2. Schedule planning session -- Assigned to: Lisa Park -- Due: 05/03/2026

Next Meeting: *Skipped (no follow-up scheduled)*
```

### 5b — Validation Rules

If the manifest includes `validation` rules, evaluate them after presenting the summary:

1. Parse each rule (e.g., `"end_date > effective_date"`).
2. Compare the collected values accordingly (dates compared chronologically, numbers numerically).
3. If any rule fails, report the error message from the manifest and ask the user to correct the relevant values.
4. Re-validate after corrections.
5. Do not proceed to rendering until all rules pass.

### 5c — User Edits

Ask the user to confirm or correct any values. The user can:

- **Edit any individual value**: Update it in the dictionary.
- **Change a gate answer**: This reveals or hides dependent sections.
  - If changing from false to true: ask the newly-required conditional questions before re-confirming.
  - If changing from true to false: remove the previously-collected conditional values and mark the section as skipped.
  - If changing a choice value that gates a conditional: re-evaluate which conditional sections apply.
- **Add loop items**: Re-enter the loop collection flow, appending to the existing list.
- **Edit a loop item**: Ask which item number to edit, then ask for updated values.
- **Remove a loop item**: Ask which item number to remove. Enforce `min_items` after removal.

After any edits, re-display the updated summary and re-validate. Continue until the user confirms.

After each change the user makes during confirmation, append a `correction` entry to the interview log:
  - `field`, `label`, `old_value`, `new_value`
  - optional `note` if the change triggered conditional re-evaluation (e.g., "Changing
    payment_method from bank_transfer to cheque removed Bank Details section")

If the user re-triggers conditional questions (false → true), also append `question` and
`answer` entries for those newly-asked questions.

---

## Phase 6 — Render and Validate

Once confirmed, run the **codraft-renderer** skill with:
- The template path
- The format (docx, html, or markdown)
- The complete variable dictionary (including boolean values as Python `True`/`False` and loop data as lists of dicts)
- The output directory (`output/`)

The renderer will:
1. Render the document (docx, or html + pdf)
2. Validate the output for any unfilled `{{ }}` placeholders or unrendered `{% %}` control tags
3. Return the output path(s) and validation status

If validation **fails** (unfilled placeholders or unrendered tags found):
- Report the issue to the user
- Offer to re-collect the missing values and re-render
- Do NOT deliver a document with unfilled placeholders

---

## Phase 7 — Post-Render

### Step 7a — Serialize Interview Log and Generate Transcript

**Step 7a-i:** Write the interview log to `interview_log.json` in the job folder.

The JSON file has this structure:
```json
{
  "schema_version": 1,
  "entries": [ ... all log entries in order ... ]
}
```

Entry shapes:
```
{ "type": "session_start", "request": "...", "template": "...", "started_at": "..." }
{ "type": "prefill", "variables": [{"name": "...", "label": "...", "value": "..."}] }
{ "type": "group_start", "name": "...", "branch": "if|else|skipped|null" }
{ "type": "question", "text": "..." }
{ "type": "clarification", "user_question": "...", "claude_response": "..." }
{ "type": "answer", "text": "..." }
{ "type": "validation_retry", "reason": "..." }
{ "type": "skip", "reason": "..." }
{ "type": "loop_item", "item_index": 1, "question": "...", "answer": "...", "values": {...} }
{ "type": "correction", "field": "...", "label": "...", "old_value": "...", "new_value": "...", "note": "..." }
```

Write using:
```python
import json, os
log_path = os.path.join(job_folder, "interview_log.json")
with open(log_path, "w", encoding="utf-8") as f:
    json.dump({"schema_version": 1, "entries": interview_log}, f, ensure_ascii=False, indent=2)
```

**Step 7a-ii:** Run the **codraft-transcriber** skill with:
  - The interview log path: `<job_folder>/interview_log.json`
  - The manifest path: `<template_dir>/manifest.yaml`
  - The job folder: `<job_folder>`
  - The rendered output filenames (comma-separated basenames)
  - The end date/time (current time, ISO 8601)

The transcriber will write `transcript.md` to the job folder and confirm success.

---

### Step 7b — Present Results

1. Present the completed document(s) to the user with links to the job folder.
   - For docx: if PDF was produced, link to both `.docx` and `.pdf`. If not, link to `.docx` only
     and relay the PDF warning (suggest converting manually via MS Word → Export or LibreOffice).
   - For HTML: link to both the `.html` and `.pdf` files.
   - For markdown: link to the `.md` file. If PDF was also produced, link to both.
     If PDF failed, mention it can be converted manually (e.g. via Pandoc or VS Code).
   - Mention: "A transcript of this session has been saved to `transcript.md` in the job folder."
2. Offer: "Would you like to prepare another document?"

If the user chooses to prepare another document, the next Phase 3d creates a fresh interview
log with a new `session_start` entry. Do not carry over log entries from the previous assembly.
Each `interview_log.json` and `transcript.md` is scoped to exactly one document.

---

## Important Notes

- **Never modify template files** — only read them.
- **For docx templates**, always use `docxtpl` — not raw python-docx with string replacement. `docxtpl` preserves formatting around placeholders.
- **PDF output for docx templates** is produced on demand using `docx2pdf` (requires Microsoft Word or LibreOffice) or LibreOffice headless. If neither is available, only `.docx` is delivered with a warning.
- **For HTML templates**, use `jinja2.Template` for rendering and `weasyprint` for PDF conversion.
- **For markdown templates**, use `jinja2.Template` for rendering, `markdown` library + `weasyprint` for optional PDF conversion. PDF is soft-fail — deliver `.md` always.
- **Use `uv`** for Python package management.
- **Format any Python code** in the style of black.
- **The manifest is a cache** — regenerate it if the template file is newer or if `schema_version` is missing/less than 2.
- **Boolean coercion** — when passing data to the renderer, ensure boolean variables are Python `True`/`False`, not strings like `"yes"` or `"no"`.
- You assist with legal workflows but do not provide legal advice. All documents should be reviewed by qualified legal professionals before being relied upon. Offer to read the documents, but remind the user to seek advice.

## Plugin Context Notes

When running as a Claude Code plugin (i.e., `CLAUDE_PLUGIN_ROOT` is set), sub-skills are namespaced. If bare skill names (`codraft-analyzer`, `codraft-renderer`, `codraft-transcriber`) do not resolve, use the namespaced forms: `codraft:codraft-analyzer`, `codraft:codraft-renderer`, and `codraft:codraft-transcriber`.
