---
name: codraft-transcriber
description: "Transcript generator for Codraft. Reads an interview_log.json and manifest.yaml,
  then writes a human-readable transcript.md to the job folder. Called by the codraft
  orchestrator — not triggered directly by the user."
---

# Codraft — Transcript Generator

You are running the Codraft transcript generation skill. You read the interview log from a
completed document assembly session and produce a human-readable `transcript.md` in the job folder.

## Inputs

You receive the following from the Orchestrator:
- **`interview_log_path`** — path to `interview_log.json` in the job folder
- **`manifest_path`** — path to `manifest.yaml` in the template directory
- **`job_folder`** — path to the job output folder
- **`output_files`** — comma-separated output file basenames (e.g., `agreement.docx, agreement.pdf`)
- **`ended_at`** — ISO 8601 timestamp for when the document was rendered

## Key Principle

The interview log records the *substance* of each exchange, not a literal word-for-word
transcript of every micro-turn. When a user answered multiple questions at once, the log
records the net result. When a user changed their mind mid-answer, the `answer` entry
captures the final answer. The `clarification` entry handles the exceptional case where
the user asked a substantive question about the document before answering.

---

## Step 1 — Read Inputs

Read `interview_log.json`:

```python
import json
with open(interview_log_path, "r", encoding="utf-8") as f:
    log = json.load(f)
entries = log["entries"]
```

Read `manifest.yaml`:

```python
import yaml
with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = yaml.safe_load(f)
```

Extract:
- `session_start` entry (first entry) for header metadata
- All other entries in order for the Interview section
- `manifest.variables`, `manifest.conditionals`, `manifest.loops`, `manifest.groups` for
  the Confirmed Values section (variable labels and conditional metadata)

---

## Step 2 — Build the Transcript

Construct all four sections in order.

---

### Section 1 — Header

```
# Document Assembly Transcript
**Template:** <session_start.template>
**Request:** <session_start.request>
**Start date/time:** <session_start.started_at>
**End date/time:** <ended_at parameter>
**Output:** <output_files parameter>

---
```

---

### Section 2 — Interview

```
## Interview
```

Walk through the entries in order after the `session_start`. Render each entry type as follows:

**`prefill` entry** — render before the first group section:
```
> *The following values were provided by the user before the interview began:*
> - **<label>:** <value>
> - ...
```

**`group_start` entry** — opens a new `###` sub-section:

| branch value | heading format |
|---|---|
| `null` or absent | `### <name>` |
| `"if"` | `### <name> *(included)*` |
| `"else"` | `### <name> *(alternative)*` |
| `"skipped"` | `### <name> *(skipped)*` |

**`question` entry** — within the current group:
```
**Q:** <text>
```

**`clarification` entry** — between question and answer:
```
> **User:** <user_question>
> **Codraft:** <claude_response>
```

**`validation_retry` entry** — before the corrected answer:
```
**Q (retry — <reason>):** *(re-asked)*
```

**`answer` entry**:
```
**A:** <text>
```

**`skip` entry** — if it follows a `group_start` with `branch: "skipped"`, it's already
represented by the heading. If it appears inline (pre-filled variable), render as:
```
*<reason>*
```

**`loop_item` entry** — within a loop group:
```
**Item <item_index>**
**Q:** <question>
**A:** <answer>
```

**`correction` entries** — if any exist, add a final sub-section:
```
### Corrections
- **<label>** changed from `<old_value>` to `<new_value>`
```
If the entry has a `note` field: append ` *(Note: <note>)*`

---

### Section 3 — Confirmed Values

```
## Confirmed Values
```

Derive the confirmed values from the interview log entries:
- Use `answer` entries mapped to their preceding `question` and `group_start` context
- Use `loop_item` entries for loop variable values (use the `values` dict)
- Use `correction` entries to get the final (post-correction) value for any corrected field
- Use `prefill` entries for pre-filled variables

For variable labels, use `variable.label` from the manifest. If absent, title-case the
variable name (`bank_name` → `Bank Name`).

Structure this section by group (in the same order as the `group_start` entries in the log).
Apply the same `*(included)*` / `*(skipped — not applicable)*` / `*(alternative)*` annotations
as the Interview section for conditional groups — but only when `manifest.conditionals` is
non-empty. Suppress all conditional annotations for simple templates with no conditionals.

**Standard table format per group:**
```
### <Group Name>

| Field | Value |
|---|---|
| <label> | <value> |
```

**Skipped conditional group:**
```
### <Group Name> *(skipped — not applicable)*
```
Heading only, no table.

**Loop group — one sub-block per item:**
```
### <Group Name>

**Item 1**

| Field | Value |
|---|---|
| <sub-label> | <value> |

**Item 2**
...
```

**Value formatting rules:**
- `True` / `true` → `Yes`
- `False` / `false` → `No`
- Empty string, `None`, or `null` → `—`
- All other values: display as-is

---

### Section 4 — Footer

```
---

*Generated by Codraft on <YYYY-MM-DD>*
```

Use today's date (from `ended_at` or the current date).

---

## Step 3 — Write the File

```python
import os
transcript_path = os.path.join(job_folder, "transcript.md")
with open(transcript_path, "w", encoding="utf-8") as f:
    f.write(transcript_content)
```

If writing fails, log the error and report it back to the Orchestrator, which will relay
the failure to the user. Document delivery always takes priority over transcript generation.

---

## Step 4 — Report Success

After writing, report back to the Orchestrator:
- The path to `transcript.md`
- A brief confirmation (e.g., "Transcript written to `<path>`.")
