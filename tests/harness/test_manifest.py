"""CoQuill Analyzer manifest tests.

Usage:
    uv run harness/test_manifest.py
"""

import sys
import subprocess
import os
from pathlib import Path

import yaml

TESTS_DIR = Path(__file__).parent.parent
FIXTURES_DIR = TESTS_DIR / "fixtures" / "templates"
REPO_ROOT = TESTS_DIR.parent
ANALYZE_PY = REPO_ROOT / "scripts" / "analyze.py"


def run_analyzer(template_dir: Path) -> None:
    """Delete cached manifest and run analyze.py."""
    manifest = template_dir / "manifest.yaml"
    if manifest.exists():
        manifest.unlink()
    result = subprocess.run(
        ["uv", "run", str(ANALYZE_PY), str(template_dir)],
        capture_output=True,
        text=True,
        cwd=str(TESTS_DIR),
    )
    if result.returncode != 0:
        raise RuntimeError(f"analyze.py failed:\n{result.stderr}\n{result.stdout}")


def load_manifest(template_dir: Path) -> dict:
    manifest_path = template_dir / "manifest.yaml"
    with open(manifest_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_var(variables: list, name: str) -> dict | None:
    for v in variables:
        if v["name"] == name:
            return v
    return None


def assert_eq(label: str, actual, expected) -> bool:
    if actual == expected:
        print(f"  PASS  {label}: {actual!r}")
        return True
    else:
        print(f"  FAIL  {label}: expected {expected!r}, got {actual!r}")
        return False


def test_type_inference() -> bool:
    """Test that type inference works correctly for all suffix patterns."""
    print("\n=== Test: type_inference ===")
    fixture_dir = FIXTURES_DIR / "type_inference"
    run_analyzer(fixture_dir)
    manifest = load_manifest(fixture_dir)

    ok = True

    # Schema version
    ok &= assert_eq("schema_version", manifest["schema_version"], 2)

    # Unconditional vars — all in manifest["variables"]
    top_vars = manifest["variables"]

    for name, expected_type in [
        ("client_name", "text"),
        ("client_address", "text"),
        ("effective_date", "date"),
        ("client_email", "email"),
        ("service_fee", "number"),
        ("contact_phone", "phone"),
        ("governing_law", "text"),
    ]:
        v = find_var(top_vars, name)
        if v is None:
            print(f"  FAIL  {name}: variable not found in manifest['variables']")
            ok = False
        else:
            ok &= assert_eq(f"{name}.type", v["type"], expected_type)

    # Boolean inference: include_warranty appears only as a gate -> boolean
    v = find_var(top_vars, "include_warranty")
    if v is None:
        print("  FAIL  include_warranty: not found in manifest['variables']")
        ok = False
    else:
        ok &= assert_eq("include_warranty.type", v["type"], "boolean")

    # warranty_terms is in conditionals[0].if_variables
    conds = manifest.get("conditionals", [])
    if not conds:
        print("  FAIL  conditionals: expected at least one conditional block")
        ok = False
    else:
        cond = conds[0]
        ok &= assert_eq("conditionals[0].condition", cond["condition"], "include_warranty")
        ok &= assert_eq("conditionals[0].gate_type", cond["gate_type"], "boolean")
        wt = find_var(cond["if_variables"], "warranty_terms")
        if wt is None:
            print("  FAIL  warranty_terms: not in conditionals[0].if_variables")
            ok = False
        else:
            ok &= assert_eq("warranty_terms.type", wt["type"], "text")

    # Loop sub-variables
    loops = manifest.get("loops", [])
    if not loops:
        print("  FAIL  loops: expected at least one loop block")
        ok = False
    else:
        loop = loops[0]
        ok &= assert_eq("loops[0].collection", loop["collection"], "line_items")
        ok &= assert_eq("loops[0].loop_var", loop["loop_var"], "item")
        desc = find_var(loop["variables"], "description")
        amount = find_var(loop["variables"], "amount")
        if desc is None:
            print("  FAIL  loop description: not found")
            ok = False
        else:
            ok &= assert_eq("loop.description.type", desc["type"], "text")
        if amount is None:
            print("  FAIL  loop amount: not found")
            ok = False
        else:
            ok &= assert_eq("loop.amount.type", amount["type"], "number")

    return ok


def test_config_merge() -> bool:
    """Test that config.yaml merges correctly into the manifest."""
    print("\n=== Test: config_merge ===")
    fixture_dir = FIXTURES_DIR / "config_merge"
    run_analyzer(fixture_dir)
    manifest = load_manifest(fixture_dir)

    ok = True

    ok &= assert_eq("schema_version", manifest["schema_version"], 2)

    # Meta
    meta = manifest.get("meta")
    if meta is None:
        print("  FAIL  meta: section missing from manifest")
        ok = False
    else:
        ok &= assert_eq("meta.display_name", meta.get("display_name"), "Config Merge Test")
        ok &= assert_eq("meta.description", meta.get("description"), "Tests that all config sections merge correctly")

    top_vars = manifest["variables"]

    # client_name overrides: label, question, required, format_hint
    cn = find_var(top_vars, "client_name")
    if cn is None:
        print("  FAIL  client_name: not found")
        ok = False
    else:
        ok &= assert_eq("client_name.label", cn.get("label"), "Client's Full Legal Name")
        ok &= assert_eq("client_name.question", cn.get("question"), "What is the client's full legal name?")
        ok &= assert_eq("client_name.required", cn.get("required"), True)
        ok &= assert_eq("client_name.format_hint", cn.get("format_hint"), "Full legal name as registered")

    # payment_method: type choice, choices, default
    pm = find_var(top_vars, "payment_method")
    if pm is None:
        print("  FAIL  payment_method: not found")
        ok = False
    else:
        ok &= assert_eq("payment_method.type", pm.get("type"), "choice")
        ok &= assert_eq("payment_method.choices", pm.get("choices"), ["bank_transfer", "cheque", "crypto"])
        ok &= assert_eq("payment_method.default", pm.get("default"), "bank_transfer")

    # include_nda: type boolean, question, default
    gate_var = find_var(top_vars, "include_nda")
    if gate_var is None:
        print("  FAIL  include_nda: not found in top-level variables")
        ok = False
    else:
        ok &= assert_eq("include_nda.type", gate_var.get("type"), "boolean")
        ok &= assert_eq("include_nda.question", gate_var.get("question"), "Does this engagement require an NDA?")
        ok &= assert_eq("include_nda.default", gate_var.get("default"), False)

    # start_date: type date, default "today"
    sd = find_var(top_vars, "start_date")
    if sd is None:
        print("  FAIL  start_date: not found")
        ok = False
    else:
        ok &= assert_eq("start_date.type", sd.get("type"), "date")
        ok &= assert_eq("start_date.default", sd.get("default"), "today")

    # Groups
    groups = manifest.get("groups")
    if groups is None:
        print("  FAIL  groups: section missing from manifest")
        ok = False
    else:
        ok &= assert_eq("groups count", len(groups), 3)
        ok &= assert_eq("groups[0].name", groups[0].get("name"), "Client Details")
        ok &= assert_eq("groups[1].name", groups[1].get("name"), "NDA")
        ok &= assert_eq("groups[1].condition", groups[1].get("condition"), "include_nda")
        ok &= assert_eq("groups[2].name", groups[2].get("name"), "Tasks")
        ok &= assert_eq("groups[2].loop", groups[2].get("loop"), "tasks")

    # Validation
    validation = manifest.get("validation")
    if validation is None:
        print("  FAIL  validation: section missing from manifest")
        ok = False
    else:
        ok &= assert_eq("validation count", len(validation), 1)
        ok &= assert_eq("validation[0].rule", validation[0].get("rule"), "start_date is not None")
        ok &= assert_eq("validation[0].message", validation[0].get("message"), "Start date is required")

    return ok


def main():
    results = []
    results.append(("type_inference", test_type_inference()))
    results.append(("config_merge", test_config_merge()))

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    passed = 0
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if ok:
            passed += 1

    print(f"\n{passed}/{len(results)} test suites passed")
    if passed < len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
