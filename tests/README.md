# Codraft Test Suite

Scenario-based tests that validate Codraft's rendering pipeline.

## Running Tests

```bash
cd tests
uv run harness/run_tests.py                          # run all scenarios
uv run harness/run_tests.py scenarios/01_*.yaml      # run one scenario
```

## Requirements

Create a virtual environment and install dependencies:

```bash
cd tests
uv venv .venv
uv pip install --python .venv jinja2 pyyaml
```

## Scenario Format

Each scenario is a YAML file in `scenarios/`. See `scenarios/scenario_schema.yaml` for the full schema.

## Directory Structure

- `fixtures/templates/` — minimal test-only templates (HTML)
- `fixtures/expected/` — text snapshots of expected output content
- `scenarios/` — YAML scenario definitions
- `harness/` — test runner and comparison utilities
- `results/` — test run output (gitignored)
