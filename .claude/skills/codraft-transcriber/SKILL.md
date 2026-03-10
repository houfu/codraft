---
name: codraft-transcriber
description: "Transcript generator for Codraft. Reads an interview_log.json and manifest.yaml,
  then writes a human-readable transcript.md to the job folder. Called by the codraft
  orchestrator — not triggered directly by the user."
---

# Codraft — Transcript Generator

You generate a transcript from a completed interview session. The heavy lifting
is handled by `scripts/transcribe.py`; your job is to invoke it and relay the result.

## Inputs from Orchestrator

- **`interview_log_path`** — path to `interview_log.json` in the job folder
- **`manifest_path`** — path to `manifest.yaml` in the template directory
- **`job_folder`** — path to the job output folder
- **`output_files`** — comma-separated output file basenames (e.g., `agreement.docx, agreement.pdf`)
- **`ended_at`** — ISO 8601 timestamp for when the document was rendered

## Key Principle

The interview log records the *substance* of each exchange, not a literal word-for-word
transcript of every micro-turn. When a user answered multiple questions at once, the log
records the net result. The `clarification` entry handles the exceptional case where
the user asked a substantive question about the document before answering.

## Run the Script

Resolve the script path relative to the project root and invoke it:

```bash
python scripts/transcribe.py \
  --interview-log <interview_log_path> \
  --manifest <manifest_path> \
  --job-folder <job_folder> \
  --output-files "<output_files>" \
  --ended-at "<ended_at>"
```

The script reads both files, builds the four transcript sections (header, interview,
confirmed values, footer), writes `transcript.md` to the job folder, and prints a
JSON result to stdout.

## Interpret Results

The script prints JSON: `{"transcript_path": "...", "success": true}` on success,
or `{"transcript_path": null, "success": false, "error": "..."}` on failure.

- On **success**: report the transcript path back to the Orchestrator.
- On **failure**: relay the error message. Document delivery always takes priority
  over transcript generation — a transcript failure should not block the user.
