# Codraft -- Project Instructions

Codraft is a document assembly tool built as Claude Cowork skills.

## Project Structure

| Directory | Purpose |
|---|---|
| `.claude/skills/` | Skill definitions (Orchestrator, Analyzer, Renderer, Transcriber) -- **source of truth** |
| `scripts/` | Python scripts that skills delegate to (`analyze.py`, `render.py`, `transcribe.py`) |
| `plugin/` | Plugin metadata for Claude Code distribution (checked in) |
| `.claude-plugin/` | Marketplace manifest (checked in) |
| `templates/_examples/` | Bundled example templates (tracked in git) |
| `templates/<name>/` | User templates (gitignored) |
| `output/` | Rendered documents (gitignored) |
| `docs/` | Documentation site (Astro Starlight) |

## Distribution

**Source of truth:** `.claude/skills/` -- never edit SKILL.md files in `plugin/` or `build/`.

| Channel | How to get it | Target user |
|---|---|---|
| **Cowork zip** | GitHub Releases (`codraft-v*.zip`) | Claude Cowork users |
| **Claude Code plugin** | `/plugin marketplace add houfu/codraft` | Claude Code users |

Plugin metadata: `plugin/.claude-plugin/plugin.json` (version `0.0.0`, overwritten at release). Marketplace manifest: `.claude-plugin/marketplace.json`. GitHub Action assembles `build/plugin/` (gitignored).

## Skills

| Skill | Location | Purpose |
|---|---|---|
| **Orchestrator** | `.claude/skills/codraft/SKILL.md` | User-facing entry point. Discovery, interview, confirmation, post-render. |
| **Analyzer** | `.claude/skills/codraft-analyzer/SKILL.md` | Delegates to `scripts/analyze.py`. Template parsing, manifest generation. |
| **Renderer** | `.claude/skills/codraft-renderer/SKILL.md` | Delegates to `scripts/render.py`. Docx/HTML/Markdown rendering, validation. |
| **Transcriber** | `.claude/skills/codraft-transcriber/SKILL.md` | Delegates to `scripts/transcribe.py`. Interview transcript generation. |

The Orchestrator invokes sub-skills via prompt-level instructions. Analyzer, Renderer, and Transcriber are thin wrappers that delegate procedural logic to Python scripts.

## Python Environment

- Use `uv` for all Python environment and package management
- Format Python code in the style of `black`
- Key dependencies: `docxtpl`, `pyyaml`, `jinja2`, `weasyprint`, `markdown`

## When Working on This Project

- Specs: `codraft_v2_spec.md` (v2), `codraft_mvp_spec.md` (original MVP)
- Test templates go in `templates/` subdirectories; rendered output goes to `output/`
- Never overwrite template files
