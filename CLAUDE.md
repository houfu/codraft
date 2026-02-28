# Codraft -- Project Instructions

Codraft is a document assembly tool built as Claude Cowork skills.

## Project Structure

| Directory | Purpose |
|---|---|
| `.claude/skills/` | Skill definitions (Orchestrator, Analyzer, Renderer) -- **source of truth** |
| `plugin/` | Plugin metadata for Claude Code distribution (checked in) |
| `.claude-plugin/` | Marketplace manifest (checked in) |
| `templates/_examples/` | Bundled example templates (tracked in git) |
| `templates/<name>/` | User templates (gitignored) |
| `output/` | Rendered documents (gitignored) |
| `docs/` | Documentation site (Astro Starlight) |

## Distribution

| Channel | How to get it | Target user |
|---|---|---|
| **Cowork zip** | Download from GitHub Releases (`codraft-v*.zip`) | Claude Cowork users |
| **Claude Code plugin** | `/plugin marketplace add houfu/codraft` | Claude Code users |

**Source of truth:** `.claude/skills/` -- never edit SKILL.md files in `plugin/` or `build/`.

**Plugin metadata:**
- `plugin/.claude-plugin/plugin.json` -- name, version (`0.0.0` placeholder overwritten at release), author
- `.claude-plugin/marketplace.json` -- marketplace manifest pointing to `./plugin`
- GitHub Action assembles plugin in `build/plugin/` (gitignored) and publishes alongside Cowork zip

## Skills

| Skill | Location | Purpose |
|---|---|---|
| **Orchestrator** | `.claude/skills/codraft/SKILL.md` | Entry point. Discovery, interview, confirmation, post-render. |
| **Analyzer** | `.claude/skills/codraft-analyzer/SKILL.md` | Template parsing, variable extraction, manifest generation. |
| **Renderer** | `.claude/skills/codraft-renderer/SKILL.md` | Docx/HTML/Markdown rendering, output validation. |

The Orchestrator is the only user-facing skill. It invokes the Analyzer and Renderer via prompt-level instructions.

## Python Environment

- Use `uv` for all Python environment and package management
- Format Python code in the style of `black`
- Key dependencies: `docxtpl`, `pyyaml`, `jinja2`, `weasyprint`, `markdown`

## When Working on This Project

- Read `codraft_v2_spec.md` for the full v2 specification
- Read `codraft_mvp_spec.md` for the original MVP specification
- Read `.claude/skills/codraft/SKILL.md` for the Orchestrator skill
- Read `.claude/skills/codraft-analyzer/SKILL.md` for the Analyzer skill
- Read `.claude/skills/codraft-renderer/SKILL.md` for the Renderer skill
- The Orchestrator is the user-facing entry point; it invokes the Analyzer and Renderer
- Test templates should be placed in `templates/` with their own subdirectory
- All rendered output goes to `output/` -- never overwrite templates
