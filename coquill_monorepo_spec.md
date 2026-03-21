# CoQuill Monorepo Migration Spec

## Status

| Field        | Value                     |
|-------------|---------------------------|
| Author      | —                         |
| Date        | 2026-02-20                |
| Status      | Draft                     |
| Supersedes  | Single-repo structure     |

---

## 1. Goals

1. **Keep the Cowork download lean.** Users who download CoQuill to use with Claude Cowork must receive only the files Cowork needs — no docs source, no test fixtures, no CI config.
2. **Add a documentation website.** A professional, lawyer-friendly site (Astro + Tailwind, deployed to GitHub Pages) that lives alongside the core project and can be updated atomically with features.
3. **Add a test/benchmark suite.** A harness for validating that CoQuill features work correctly across Cowork, Claude Code, and other coding agents.
4. **One repo, atomic commits.** A feature, its documentation, and its tests land in a single PR. No cross-repo synchronisation overhead.

---

## 2. Current Repo Structure

```
coquill/
├── .claude/
│   └── skills/
│       └── coquill/
│           └── SKILL.md
├── .gitignore
├── CLAUDE.md
├── README.md
├── LICENSE
├── coquill_mvp_spec.md
├── docs/
│   └── logo.png
├── templates/
│   ├── _examples/
│   │   └── nda/
│   │       └── nda.docx
│   └── <user_templates>/        # gitignored
│       ├── <name>.docx|.html
│       └── manifest.yaml        # auto-generated, gitignored
└── output/                      # gitignored
```

Everything in this repo is currently shipped to every user who clicks "Download ZIP".

---

## 3. Proposed Monorepo Structure

```
coquill/
│
│  ── Core (shipped to Cowork users) ──────────────────────
│
├── .claude/
│   └── skills/
│       └── coquill/
│           └── SKILL.md                # Orchestrator skill
├── templates/
│   ├── _examples/
│   │   └── nda/
│   │       └── nda.docx
│   └── <user_templates>/               # gitignored
├── output/                              # gitignored
├── CLAUDE.md                            # Project instructions for Claude
├── README.md                            # Project overview + install guide
├── LICENSE
│
│  ── Documentation site ──────────────────────────────────
│
├── docs/
│   ├── public/
│   │   ├── favicon.svg
│   │   └── images/
│   │       ├── logo.png                # moved from docs/logo.png
│   │       └── og-image.png
│   ├── src/
│   │   ├── content/
│   │   │   └── docs/                   # MDX content pages
│   │   │       ├── index.mdx
│   │   │       ├── getting-started.mdx
│   │   │       ├── template-authoring.mdx
│   │   │       ├── examples/
│   │   │       │   └── nda-walkthrough.mdx
│   │   │       └── reference/
│   │   │           ├── project-structure.mdx
│   │   │           └── variable-naming.mdx
│   │   ├── components/                 # Custom Astro/React components
│   │   ├── layouts/
│   │   └── pages/
│   ├── astro.config.mjs
│   ├── tailwind.config.mjs
│   ├── tsconfig.json
│   └── package.json
│
│  ── Test / benchmark suite ──────────────────────────────
│
├── tests/
│   ├── README.md                       # How to run benchmarks
│   ├── fixtures/
│   │   ├── templates/                  # Test-only templates
│   │   │   ├── simple_text/
│   │   │   │   └── simple_text.docx
│   │   │   ├── all_field_types/
│   │   │   │   └── all_field_types.html
│   │   │   └── ...
│   │   └── expected/                   # Expected output snapshots
│   │       ├── simple_text/
│   │       │   └── simple_text.docx
│   │       └── ...
│   ├── scenarios/                      # Test scenario definitions
│   │   ├── scenario_schema.yaml        # Schema for scenario files
│   │   ├── 01_simple_substitution.yaml
│   │   ├── 02_all_field_types.yaml
│   │   ├── 03_multiple_occurrences.yaml
│   │   └── ...
│   ├── harness/                        # Runner scripts
│   │   ├── run_tests.py                # Main test runner
│   │   └── compare_output.py           # Output comparison utility
│   └── results/                        # gitignored, test run output
│
│  ── Build and CI ────────────────────────────────────────
│
├── .github/
│   └── workflows/
│       ├── release.yml                 # Builds slim Cowork ZIP on tag
│       └── deploy-docs.yml             # Builds + deploys docs to GH Pages
├── release-manifest.txt                # Files to include in Cowork ZIP
│
│  ── Project-level config ────────────────────────────────
│
├── coquill_mvp_spec.md                 # Full MVP specification
└── .gitignore                          # Updated for monorepo
```

---

## 4. Release Artifact (Slim Cowork ZIP)

### 4.1 Problem

GitHub's "Download ZIP" button ships the entire repo. Cowork users would receive `docs/`, `tests/`, `.github/`, and other files they do not need. This adds confusion and bloat to what should be a simple "download and open" experience.

### 4.2 Solution

A **release-manifest.txt** defines exactly which files and directories are included in the Cowork download. A GitHub Actions workflow builds this ZIP on every tagged release and attaches it to the GitHub Release.

### 4.3 release-manifest.txt

```
.claude/
templates/_examples/
CLAUDE.md
README.md
LICENSE
coquill_mvp_spec.md
.gitignore
```

**Excluded from the ZIP:**

- `docs/` — documentation site source
- `tests/` — benchmark suite
- `.github/` — CI workflows
- `release-manifest.txt` — build config
- Any dotfiles not in the manifest (e.g. `.prettierrc`)

### 4.4 GitHub Actions: release.yml

Trigger: push of a version tag (`v*`).

Steps:

1. Checkout the repo.
2. Read `release-manifest.txt`.
3. Create a ZIP containing only the listed files and directories, named `coquill-v{version}.zip`.
4. Create a GitHub Release for the tag.
5. Attach the ZIP as a release asset.

### 4.5 Install instructions update

The README install section changes from:

> Click the green **Code** button, then click **Download ZIP**

To:

> Go to the [Releases](https://github.com/{owner}/coquill/releases) page and download the latest `coquill-v*.zip`

---

## 5. Documentation Site

### 5.1 Framework

Astro 5 + Tailwind 4 + shadcn/ui, using the shadcnblocks **Plasma** template (or equivalent) as the starting point. This provides:

- A marketing-style landing page (hero, features, how-it-works, CTA)
- A docs section with sidebar navigation, ⌘K search, and MDX rendering
- A changelog page
- Light/dark theme toggle (default to light)

### 5.2 Design Direction

The visual language is informed by three reference sites:

- **Harvey.ai** — confidence, whitespace, authority (borrow the emotional register)
- **LawNet 4.0** — functional clarity, scannability, institutional trust (borrow the docs-section UX)
- **Claude Docs (platform.claude.com/docs)** — warm tones, single-font discipline, content restraint (borrow the colour warmth and typography)

Key design tokens:

| Token           | Value                              |
|----------------|------------------------------------|
| Background     | Warm off-white `#faf9f5`           |
| Text           | Warm dark `#2a2a28`                |
| Primary accent | Deep navy `#1a2332`                |
| Secondary      | Muted accent for links/interactive |
| Font family    | Inter (or DM Sans), single family  |
| Font weights   | 400 body, 600–700 headings         |

### 5.3 Initial Page Structure

**Landing page (homepage):**

- Hero: tagline + one-sentence description + "Get Started" CTA
- "How it works" 3-step visual (template → interview → document)
- Feature highlights (docx/html support, type inference, manifest caching)
- Footer

**Docs section:**

| Page                        | Source content                     |
|----------------------------|------------------------------------|
| Getting Started            | README install + quick start       |
| Template Authoring Guide   | README template authoring section  |
| Variable Naming Reference  | README naming conventions table    |
| NDA Walkthrough (example)  | New content, end-to-end demo       |
| Project Structure          | README + CLAUDE.md structure docs  |
| MVP Scope & Roadmap        | coquill_mvp_spec.md                |

**Changelog:**

- MDX-based, one entry per version.

### 5.4 Deployment

GitHub Actions workflow (`deploy-docs.yml`):

- Trigger: push to `main` that touches `docs/**`.
- Steps: install Node deps, build Astro site, deploy to `gh-pages` branch.
- GitHub Pages serves from the `gh-pages` branch.
- Custom domain (optional, future): `docs.coquill.dev` or similar.

### 5.5 Local Development

```bash
cd docs
npm install
npm run dev        # starts dev server at localhost:4321
npm run build      # production build
npm run preview    # preview production build locally
```

---

## 6. Test / Benchmark Suite

### 6.1 Purpose

Validate that CoQuill's core features work correctly when driven by different coding agents (Cowork, Claude Code, and potentially others). This is not a unit test suite for a Python library — it is a **scenario-based benchmark** that tests the end-to-end flow: template → variable extraction → rendering → output comparison.

### 6.2 Test Scenario Format

Each scenario is a YAML file that describes:

```yaml
# tests/scenarios/01_simple_substitution.yaml

name: Simple text substitution
description: >
  All variables are plain text fields. Verifies basic
  placeholder replacement in a docx template.

template: simple_text/simple_text.docx

variables:
  party_name: "Acme Pte Ltd"
  counterparty_name: "Beta Corp"
  governing_law: "Singapore"

expected_output: simple_text/simple_text.docx

checks:
  - type: contains_text
    value: "Acme Pte Ltd"
  - type: contains_text
    value: "Beta Corp"
  - type: not_contains_text
    value: "{{ party_name }}"
  - type: not_contains_text
    value: "{{ counterparty_name }}"
```

### 6.3 What Gets Tested

| Scenario category          | What it validates                                     |
|---------------------------|-------------------------------------------------------|
| Simple substitution        | All `{{ var }}` placeholders are replaced              |
| All field types            | Date, email, number, phone, text fields render correctly |
| Multiple occurrences       | Same variable used N times → all N replaced with one value |
| HTML template              | HTML rendering produces valid HTML + PDF output        |
| Manifest caching           | Manifest is generated on first run, reused on second   |
| Missing variables          | Graceful handling when a variable is left empty        |

### 6.4 Test Fixtures

- `tests/fixtures/templates/` — contains small, purpose-built templates for each scenario. These are not user-facing example templates; they are minimal test cases.
- `tests/fixtures/expected/` — contains expected output files (or text snapshots) for comparison.

### 6.5 Test Runner

A Python script (`tests/harness/run_tests.py`) that:

1. Reads a scenario YAML file.
2. Copies the fixture template into a temporary working directory.
3. Runs the CoQuill rendering pipeline (calls the same Python code the skill invokes) with the provided variable values.
4. Compares the output against the expected checks (contains_text, file exists, etc.).
5. Reports pass/fail per scenario.

Environment: uses `uv` for Python dependency management, consistent with the main project.

```bash
cd tests
uv run harness/run_tests.py                         # run all scenarios
uv run harness/run_tests.py scenarios/01_*.yaml      # run one scenario
```

### 6.6 Agent-Specific Testing (Future)

The scenario YAML format is designed to be agent-agnostic. In future, an extended harness could:

- Feed the scenario to Cowork via its interface and verify the output.
- Feed the scenario to Claude Code as a prompt and verify the output.
- Compare timing, token usage, and correctness across agents.

This is out of scope for the initial migration but the scenario format should support it without structural changes.

---

## 7. .gitignore Updates

The monorepo `.gitignore` needs to cover all three areas:

```gitignore
# ── Core ──
output/
templates/*/manifest.yaml
templates/*
!templates/_examples/
!templates/_examples/**

# ── Docs ──
docs/node_modules/
docs/dist/
docs/.astro/

# ── Tests ──
tests/results/

# ── General ──
.DS_Store
*.pyc
__pycache__/
.env
```

---

## 8. Migration Steps

This section describes the ordered steps to port the current single-purpose repo to the monorepo structure.

### Phase 1: Restructure the repo

1. **Create `docs/` directory** with Astro project scaffolding.
   - Install the Plasma template (or chosen alternative).
   - Configure Tailwind with the CoQuill design tokens (palette, font).
   - Set default theme to light.
   - Remove demo content pages.

2. **Create `tests/` directory** with the harness skeleton.
   - Create `fixtures/`, `scenarios/`, `harness/`, `results/` subdirectories.
   - Write `tests/README.md` explaining the scenario format and how to run tests.
   - Create `scenario_schema.yaml` defining the YAML format.

3. **Create `.github/workflows/`** with two workflow files.
   - `release.yml` — slim ZIP builder (triggered on version tags).
   - `deploy-docs.yml` — docs site builder (triggered on push to main, filtered to `docs/**`).

4. **Create `release-manifest.txt`** listing the files for the Cowork ZIP.

5. **Move `docs/logo.png`** to `docs/public/images/logo.png`.

6. **Update `.gitignore`** for the monorepo layout.

7. **Update `README.md`** install instructions to point to GitHub Releases instead of "Download ZIP".

### Phase 2: Populate the docs site

8. **Port existing content** from README.md and coquill_mvp_spec.md into MDX pages:
   - `getting-started.mdx` ← README quick start + install
   - `template-authoring.mdx` ← README template authoring + placeholders
   - `variable-naming.mdx` ← README naming conventions table
   - `project-structure.mdx` ← README + CLAUDE.md structure sections
   - `mvp-scope.mdx` ← coquill_mvp_spec.md (summarised)

9. **Write new content:**
   - `index.mdx` — docs landing page (card grid linking to guides)
   - `nda-walkthrough.mdx` — end-to-end NDA example with screenshots

10. **Design the landing page** — replace Plasma demo hero/features/CTA with CoQuill content.

11. **Test local build** — `cd docs && npm run build` succeeds, all pages render.

### Phase 3: Populate the test suite

12. **Create 3–5 initial fixture templates** covering the core scenario categories (simple substitution, all field types, HTML template).

13. **Write corresponding scenario YAML files.**

14. **Implement `run_tests.py`** — the minimal test runner that reads scenarios, runs the rendering pipeline, and checks output.

15. **Verify all scenarios pass locally.**

### Phase 4: CI and release

16. **Test the release workflow** — push a `v0.1.0` tag and verify the slim ZIP is built correctly and attached to the GitHub Release.

17. **Test the docs deployment workflow** — push a change to `docs/` on main and verify the site builds and deploys to GitHub Pages.

18. **Verify the slim ZIP** — download it, extract it, open in Cowork, and confirm the skill works with zero extra files.

---

## 9. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Users still click "Download ZIP" instead of Releases | High | Medium — they get extra files | Add a prominent note at the top of README. Consider adding a `COWORK_USERS_READ_THIS.md` to the repo root. |
| Docs framework (Astro) adds Node.js as a dev dependency | Low | Low — only affects docs contributors | Docs build is isolated in `docs/`. Core CoQuill users never touch Node. |
| Template purchase (Plasma, $79) is a sunk cost if it doesn't fit | Low | Low | The template is a starting point, not a lock-in. shadcn/ui components are standard React; everything is portable. |
| Test harness needs access to rendering pipeline code | Medium | Medium — tight coupling | The harness should call the same Python functions the skill calls, imported from a shared location. If the skill is refactored later to extract a library, the harness imports shift but the scenarios stay the same. |
| GitHub Pages deployment conflicts with existing repo settings | Low | Low | Use a dedicated `gh-pages` branch. This is the standard Astro deployment pattern and does not affect the main branch. |

---

## 10. Out of Scope

The following are explicitly not part of this migration:

- Changing the CoQuill skill logic or rendering pipeline.
- Adding new template features (conditionals, loops, computed fields).
- Multi-agent automated testing (the scenario format supports it, but the automated harness is future work).
- Custom domain setup for the docs site.
- Internationalisation (i18n) for the docs site.
- CMS integration for docs content editing.

---

## 11. Success Criteria

The migration is complete when:

1. A tagged release produces a slim ZIP that contains only core CoQuill files.
2. That ZIP, when opened in Cowork, works identically to the current repo.
3. The docs site is live on GitHub Pages with at least 5 content pages.
4. The test suite has at least 3 passing scenarios covering simple substitution, multiple field types, and HTML rendering.
5. Both CI workflows (release + docs deploy) run successfully on their respective triggers.
