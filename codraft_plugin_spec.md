# Codraft — Claude Code Plugin Distribution Specification

**Version:** 0.1
**Date:** 2026-02-21
**Extends:** `codraft_v2_spec.md` (v0.2)

---

## 1. Overview

This specification adds Claude Code plugin distribution to Codraft. Currently, Codraft is distributed as a zip file for Claude Cowork users. This spec introduces a second distribution channel via the Claude Code plugin marketplace, built from the same source SKILL.md files.

### 1.1 Goals

- **Plugin distribution** — Claude Code users can install Codraft via `/plugin marketplace add` and `/plugin install` without downloading a zip
- **Cowork-at-root** — The existing Cowork project structure (`.claude/skills/`) remains the source of truth; the plugin is a derived artifact
- **Bundled example templates** — The plugin ships with `templates/_examples/` so users get a working demo immediately after install
- **Dual-environment dependencies** — Dependency installation works in both Claude Code (which has `uv`) and Cowork (which only has `pip`)
- **Automated release** — A GitHub Action builds both the Cowork zip and the plugin package from a single tag push

### 1.2 Non-Goals

- Submitting to the official Anthropic marketplace (can be done later manually)
- Supporting Claude Code agents, hooks, or MCP servers (skills only for now)
- Changing the SKILL.md content beyond what's needed for dual-environment compatibility

---

## 2. Architecture

### 2.1 Approach: Cowork-at-Root

The repo root continues to use the Cowork layout. The Claude Code plugin is assembled at release time by copying skills and templates into a plugin directory structure.

```
codraft/                              # Repo root = Cowork project
├── .claude/
│   └── skills/                       # SOURCE OF TRUTH
│       ├── codraft/
│       │   └── SKILL.md
│       ├── codraft-analyzer/
│       │   └── SKILL.md
│       └── codraft-renderer/
│           └── SKILL.md
├── plugin/                           # Plugin metadata (checked in)
│   ├── .claude-plugin/
│   │   └── plugin.json
│   └── README.md
├── .claude-plugin/                   # Marketplace manifest (checked in)
│   └── marketplace.json
├── templates/_examples/              # Bundled with both distributions
├── .github/workflows/release.yml     # Builds both zip and plugin
└── ...
```

### 2.2 Plugin Structure (Built at Release)

The GitHub Action assembles this structure into a release artifact:

```
codraft-plugin/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   ├── codraft/
│   │   └── SKILL.md
│   ├── codraft-analyzer/
│   │   └── SKILL.md
│   └── codraft-renderer/
│       └── SKILL.md
├── templates/
│   └── _examples/
│       ├── Bonterms_Mutual_NDA/
│       │   └── Bonterms-Mutual-NDA.docx
│       ├── invoice/
│       │   └── invoice.html
│       ├── consulting_agreement/
│       │   ├── Consulting-Agreement.docx
│       │   └── config.yaml
│       └── event_invitation/
│           ├── event-invitation.html
│           └── config.yaml
└── README.md
```

### 2.3 Self-Referencing Marketplace

The repo itself serves as the marketplace. Users add the repo directly:

```
/plugin marketplace add houfu/codraft
/plugin install codraft@codraft
```

This is achieved by placing `.claude-plugin/marketplace.json` at the repo root, pointing to the plugin source within the same repo.

---

## 3. New Files

### 3.1 `plugin/.claude-plugin/plugin.json`

Static metadata file, checked into git. The version field is overwritten by the GitHub Action at release time.

```json
{
  "name": "codraft",
  "description": "Document assembly tool. Interview users and render completed documents from docx/HTML templates with conditional logic, loops, and developer configuration.",
  "version": "0.0.0",
  "author": {
    "name": "houfu"
  }
}
```

### 3.2 `.claude-plugin/marketplace.json`

Marketplace manifest at the repo root. Points to the plugin source within the same repo.

```json
{
  "name": "codraft",
  "owner": {
    "name": "houfu"
  },
  "plugins": [
    {
      "name": "codraft",
      "source": "./plugin",
      "description": "Document assembly tool with conditional logic, loops, and developer configuration."
    }
  ]
}
```

**Note:** The `source` field uses a relative path (`./plugin`). This works for local development and testing. For marketplace distribution via GitHub, the source may need to reference the repo directly — verify during testing whether `./plugin` resolves correctly when the marketplace is added via `houfu/codraft`. If not, switch to:

```json
"source": {
  "source": "github",
  "repo": "houfu/codraft",
  "path": "plugin"
}
```

### 3.3 `plugin/README.md`

Plugin-specific README with install instructions for Claude Code users. Separate from the project root `README.md` which targets Cowork users.

---

## 4. SKILL.md Changes

### 4.1 Dependency Installation (All Three Skills)

**Current:** Skills hardcode `uv pip install`.

**Change:** Replace with a fallback one-liner that works in both environments:

```bash
command -v uv > /dev/null 2>&1 && uv pip install docxtpl pyyaml jinja2 weasyprint || pip install docxtpl pyyaml jinja2 weasyprint
```

This tries `uv` first (available in Claude Code and on user machines), falls back to `pip` (available in Cowork's container).

**Where:** Update the prerequisites / dependency install section in each SKILL.md that contains an install command. The Orchestrator skill triggers the install; the Analyzer and Renderer may also have their own install references — update all occurrences.

### 4.2 Template Discovery (Orchestrator Skill)

**Current:** The Orchestrator searches `templates/` relative to the working directory.

**Change:** Search two locations, in priority order:

1. **User templates** — `templates/` in the current working directory (existing behaviour, unchanged)
2. **Bundled templates** — `${CLAUDE_PLUGIN_ROOT}/templates/_examples/` (new fallback for plugin installs)

**Discovery rules:**

- If user templates exist, list them first
- Append bundled templates that aren't shadowed by a user template with the same directory name
- When listing templates to the user, label bundled templates as "(built-in)" so the user knows the source
- If no user templates exist and no `${CLAUDE_PLUGIN_ROOT}` is set (i.e., Cowork context), fall back to `templates/_examples/` relative to the working directory (current behaviour for bundled examples)

**Detection logic for environment:**

- If `${CLAUDE_PLUGIN_ROOT}` is set → plugin context, use it for bundled templates
- If `${CLAUDE_PLUGIN_ROOT}` is not set → Cowork context, use `templates/_examples/` relative to working directory

### 4.3 Output Location

No change. Output always goes to `output/` in the current working directory, regardless of where the template came from.

### 4.4 Skill Namespacing

When installed as a plugin, skills are namespaced as `codraft:codraft`, `codraft:codraft-analyzer`, `codraft:codraft-renderer`.

**Change:** Update the Orchestrator's instructions where it references the Analyzer and Renderer skills. Currently the Orchestrator says things like "Run the codraft-analyzer skill". Update to handle both forms:

- In plugin context: `codraft:codraft-analyzer`
- In Cowork context: `codraft-analyzer`

**Approach:** The Orchestrator should reference the sub-skills by their bare name (`codraft-analyzer`, `codraft-renderer`). Test during development whether Claude resolves these correctly in the plugin context. If not, add a note in the Orchestrator instructions:

> "If running as a plugin, these skills are namespaced: use `codraft:codraft-analyzer` and `codraft:codraft-renderer`."

---

## 5. GitHub Action Changes

### 5.1 Updated `release.yml`

The existing release workflow builds a Cowork zip from `release-manifest.txt`. Extend it to also build the plugin package.

**New steps added after the existing zip build:**

1. **Assemble plugin directory:**
   - Copy `.claude/skills/codraft/`, `.claude/skills/codraft-analyzer/`, `.claude/skills/codraft-renderer/` → `build/plugin/skills/`
   - Copy `templates/_examples/` → `build/plugin/templates/_examples/`
   - Copy `plugin/.claude-plugin/plugin.json` → `build/plugin/.claude-plugin/plugin.json`
   - Copy `plugin/README.md` → `build/plugin/README.md`

2. **Inject version into `plugin.json`:**
   - Read version from the git tag (e.g., `v2.1.0` → `2.1.0`)
   - Replace the `"version"` field in `build/plugin/.claude-plugin/plugin.json`

3. **Package plugin zip:**
   - Zip `build/plugin/` as `codraft-plugin-v${VERSION}.zip`

4. **Attach to release:**
   - The GitHub Release now has two artifacts:
     - `codraft-v${VERSION}.zip` (Cowork)
     - `codraft-plugin-v${VERSION}.zip` (Claude Code)

### 5.2 `build/` Directory

The `build/` directory is used as a staging area for assembling the plugin. Add `build/` to `.gitignore`.

---

## 6. .gitignore Changes

Add:

```
# Plugin build output
build/
```

The `plugin/` directory itself is tracked (it contains `plugin.json` and `README.md`). Only the assembled output in `build/` is ignored.

---

## 7. Documentation Updates

### 7.1 Root `README.md`

Add a "Claude Code Installation" section alongside the existing Cowork installation instructions:

```markdown
### Claude Code

From within Claude Code:

1. Add the marketplace: `/plugin marketplace add houfu/codraft`
2. Install the plugin: `/plugin install codraft@codraft`
3. Say "prepare an NDA" to try it out with a built-in template
```

### 7.2 `CLAUDE.md`

Add a section noting the dual distribution:

- Plugin metadata lives in `plugin/`
- Marketplace manifest lives in `.claude-plugin/marketplace.json`
- The GitHub Action builds both artifacts
- `.claude/skills/` remains the source of truth — never edit skills in `plugin/` or `build/`

### 7.3 `plugin/README.md`

Plugin-specific README covering:

- What Codraft does (brief)
- Install instructions for Claude Code
- How to add your own templates (create `templates/` in your project directory)
- Link to the full README for template authoring docs

---

## 8. Testing Plan

### 8.1 Local Plugin Testing

1. Assemble the plugin directory manually (or with a local script)
2. Start Claude Code in a test directory
3. Add the local marketplace: `/plugin marketplace add ./path/to/codraft`
4. Install: `/plugin install codraft@codraft`
5. Verify:
   - `/codraft` or "prepare an NDA" triggers the orchestrator
   - Bundled templates are discovered from `${CLAUDE_PLUGIN_ROOT}/templates/_examples/`
   - Dependencies install via `uv` (or `pip` if `uv` is absent)
   - Output renders to `./output/` in the test directory
   - Analyzer and Renderer skills are invoked correctly (with or without namespace prefix)

### 8.2 Cowork Regression Testing

1. Open the repo root in Cowork
2. Verify the existing flow still works:
   - "Prepare an NDA" finds `templates/_examples/Bonterms_Mutual_NDA/`
   - Dependencies install via `pip` (Cowork container)
   - Full interview and render cycle completes
   - The `uv`-with-fallback install command doesn't break anything

### 8.3 User Template Shadowing

1. In the Claude Code test directory, create `templates/Bonterms_Mutual_NDA/` with a custom template
2. Say "prepare an NDA"
3. Verify the user's template is selected, not the bundled one

### 8.4 GitHub Action Testing

1. Push a test tag (e.g., `v2.1.0-rc1`)
2. Verify the release has both zip artifacts
3. Download `codraft-plugin-v*.zip` and verify its structure matches section 2.2
4. Verify `plugin.json` has the correct version

---

## 9. Migration Notes

### 9.1 Breaking Changes

None. This is purely additive. Existing Cowork users are unaffected.

### 9.2 New Files to Create

| File | Purpose | Tracked |
|---|---|---|
| `plugin/.claude-plugin/plugin.json` | Plugin metadata | Yes |
| `plugin/README.md` | Plugin install instructions | Yes |
| `.claude-plugin/marketplace.json` | Self-referencing marketplace manifest | Yes |

### 9.3 Files to Modify

| File | Change |
|---|---|
| `.claude/skills/codraft/SKILL.md` | Template discovery (dual-path), dependency install fallback, namespace note |
| `.claude/skills/codraft-analyzer/SKILL.md` | Dependency install fallback |
| `.claude/skills/codraft-renderer/SKILL.md` | Dependency install fallback |
| `.github/workflows/release.yml` | Add plugin build and packaging steps |
| `.gitignore` | Add `build/` |
| `README.md` | Add Claude Code install instructions |
| `CLAUDE.md` | Add plugin distribution notes |

### 9.4 Implementation Order

1. Create `plugin/.claude-plugin/plugin.json`
2. Create `.claude-plugin/marketplace.json`
3. Create `plugin/README.md`
4. Update `.gitignore` (add `build/`)
5. Update all three SKILL.md files — dependency install fallback
6. Update Orchestrator SKILL.md — template discovery dual-path logic
7. Update Orchestrator SKILL.md — namespace awareness note
8. Update `.github/workflows/release.yml` — add plugin build steps
9. Update `README.md` — add Claude Code install section
10. Update `CLAUDE.md` — add plugin distribution notes
11. Test locally with Claude Code plugin install
12. Test Cowork regression
13. Tag a release and verify both artifacts
