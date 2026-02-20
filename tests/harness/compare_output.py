"""Output comparison utilities for Codraft test harness."""

from pathlib import Path


def read_html_text(path: Path) -> str:
    """Read text content from an HTML file (returns raw HTML as string)."""
    return path.read_text(encoding="utf-8")


def check_contains_text(path: Path, text: str) -> tuple[bool, str]:
    """Check that the output file contains the given text string.

    Returns (passed, message).
    """
    if not path.exists():
        return False, f"File not found: {path}"

    content = read_html_text(path)
    if text in content:
        return True, f"✓ Contains: {text!r}"
    else:
        return False, f"✗ Expected to contain: {text!r}"


def check_not_contains_text(path: Path, text: str) -> tuple[bool, str]:
    """Check that the output file does NOT contain the given text string.

    Returns (passed, message).
    """
    if not path.exists():
        return False, f"File not found: {path}"

    content = read_html_text(path)
    if text not in content:
        return True, f"✓ Does not contain: {text!r}"
    else:
        return False, f"✗ Expected NOT to contain: {text!r}"


def check_file_exists(path: Path) -> tuple[bool, str]:
    """Check that a file exists at the given path.

    Returns (passed, message).
    """
    if path.exists():
        return True, f"✓ File exists: {path}"
    else:
        return False, f"✗ File not found: {path}"
