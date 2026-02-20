"""Codraft test runner.

Usage:
    uv run harness/run_tests.py                        # run all scenarios
    uv run harness/run_tests.py scenarios/01_*.yaml    # run specific scenarios
"""

import sys
import glob
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, Undefined

sys.path.insert(0, str(Path(__file__).parent))

from compare_output import check_contains_text, check_not_contains_text, check_file_exists

TESTS_DIR = Path(__file__).parent.parent
FIXTURES_DIR = TESTS_DIR / "fixtures" / "templates"
RESULTS_DIR = TESTS_DIR / "results"
SCENARIOS_DIR = TESTS_DIR / "scenarios"


class KeepUndefined(Undefined):
    """Keep unfilled placeholders as-is instead of raising an error."""

    def __str__(self):
        return "{{ " + self._undefined_name + " }}"


def render_html_template(template_path: Path, variables: dict, output_path: Path) -> None:
    """Render an HTML template with jinja2 and write to output_path."""
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        undefined=KeepUndefined,
        keep_trailing_newline=True,
    )
    template = env.get_template(template_path.name)
    rendered = template.render(**variables)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")


def run_scenario(scenario_path: Path) -> dict:
    """Run a single scenario and return results."""
    with open(scenario_path, encoding="utf-8") as f:
        scenario = yaml.safe_load(f)

    name = scenario["name"]
    print(f"\n{'='*60}")
    print(f"Scenario: {name}")
    print(f"  {scenario.get('description', '').strip()}")
    print(f"{'='*60}")

    # Locate template
    template_rel = scenario["template"]
    template_path = FIXTURES_DIR / template_rel
    if not template_path.exists():
        print(f"  ERROR: Template not found: {template_path}")
        return {"name": name, "passed": False, "checks": []}

    # Set up output path
    expected_output_rel = scenario["expected_output"]
    output_path = RESULTS_DIR / expected_output_rel
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Render template
    variables = scenario.get("variables", {})
    suffix = template_path.suffix.lower()
    if suffix == ".html":
        render_html_template(template_path, variables, output_path)
    else:
        print(f"  ERROR: Unsupported template type: {suffix}")
        return {"name": name, "passed": False, "checks": []}

    print(f"  Rendered → {output_path.relative_to(TESTS_DIR)}")

    # Run checks
    check_results = []
    checks = scenario.get("checks", [])
    for check in checks:
        check_type = check["type"]
        if check_type == "contains_text":
            passed, msg = check_contains_text(output_path, check["value"])
        elif check_type == "not_contains_text":
            passed, msg = check_not_contains_text(output_path, check["value"])
        elif check_type == "file_exists":
            check_path = RESULTS_DIR / check["path"]
            passed, msg = check_file_exists(check_path)
        else:
            passed, msg = False, f"Unknown check type: {check_type}"

        check_results.append({"passed": passed, "message": msg})
        print(f"  {msg}")

    all_passed = all(r["passed"] for r in check_results)
    status = "PASS" if all_passed else "FAIL"
    print(f"\n  Result: {status}")
    return {"name": name, "passed": all_passed, "checks": check_results}


def main():
    # Determine which scenario files to run
    if len(sys.argv) > 1:
        # Expand glob patterns from command line
        scenario_paths = []
        for pattern in sys.argv[1:]:
            expanded = glob.glob(pattern)
            if expanded:
                scenario_paths.extend([Path(p) for p in expanded])
            else:
                scenario_paths.append(Path(pattern))
    else:
        scenario_paths = sorted(SCENARIOS_DIR.glob("*.yaml"))
        # Exclude schema file
        scenario_paths = [p for p in scenario_paths if p.name != "scenario_schema.yaml"]

    if not scenario_paths:
        print("No scenario files found.")
        sys.exit(1)

    print(f"Running {len(scenario_paths)} scenario(s)...")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for path in scenario_paths:
        result = run_scenario(path)
        results.append(result)

    # Summary
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed}/{total} scenarios passed")
    print(f"{'='*60}")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['name']}")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
