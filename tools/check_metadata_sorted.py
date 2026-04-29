"""
check_metadata_sorted.py
------------------------
Pre-commit linter that verifies codegen/inputs/Metadata.yaml lists all
operator entries in strict alphabetical order by operator_name.

Sorting rules
-------------
- Standard Python / ASCII lexicographic order on the operator_name string.
- Underscore ('_') has ASCII value 95, which is less than any lowercase
  letter (97–122), so names like _softmax sort BEFORE abs.
- Comparison is case-insensitive to avoid surprises if upper-case names
  are ever added (e.g. "Abs" and "abs" would be treated as equal).

Exit codes
----------
0  All operator_name entries are in sorted order. No issues found.
1  One or more entries are out of order. Violations are printed to stderr.

Usage
-----
    # Run directly:
    python tools/check_metadata_sorted.py

    # Run against an explicit path (e.g. in CI or for testing):
    python tools/check_metadata_sorted.py codegen/inputs/Metadata.yaml

    # Run via pre-commit (path injected automatically by the framework):
    #   see .pre-commit-config.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

import regex as re


_DEFAULT_YAML = Path(__file__).parent.parent / "codegen" / "inputs" / "Metadata.yaml"


def _parse_operator_names(path: Path) -> List[Tuple[int, str]]:
    """
    Return a list of (line_number, operator_name) for every *active*
    (non-commented-out) ``- operator_name:`` entry in the YAML file.

    We parse with a regex rather than a full YAML parser so that:
    - The file does not need to be importable as a Python dependency.
    - We preserve exact line numbers for error messages.
    - We avoid any YAML-library version dependencies.

    Only lines that match the pattern ``^- operator_name: <name>`` (with
    optional leading whitespace) are collected.  Lines that start with one
    or more ``#`` characters before the dash are explicitly skipped so that
    commented-out operators (e.g. ``embedding``) do not affect the check.
    """
    pattern = re.compile(r"^-\s+operator_name:\s+(\S+)")
    entries: List[Tuple[int, str]] = []

    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            stripped = line.lstrip()
            # Skip comment lines regardless of indentation.
            if stripped.startswith("#"):
                continue
            m = pattern.match(line)
            if m:
                entries.append((lineno, m.group(1)))

    return entries


def _sort_key(name: str) -> str:
    """
    Case-insensitive sort key.
    Preserving underscore-first ordering: '_' (ASCII 95) < 'a' (ASCII 97)
    is already correct in Python's default string comparison, so we only
    need to lower-case the name to make the check case-insensitive.
    """
    return name.lower()


def check_sorted(path: Path) -> bool:
    """
    Check that all active operator_name entries in *path* are in sorted order.
    Returns True if sorted, False if any violation is found.
    """
    entries = _parse_operator_names(path)

    if not entries:
        # File exists but contains no active operator entries — treat as OK
        # so the check does not block an empty or comment-only file.
        print(f"check_metadata_sorted: {path}: no active operator entries found.")
        return True

    violations: List[str] = []

    for i in range(1, len(entries)):
        prev_lineno, prev_name = entries[i - 1]
        curr_lineno, curr_name = entries[i]

        if _sort_key(curr_name) < _sort_key(prev_name):
            violations.append(
                f"  line {curr_lineno}: '{curr_name}' should come before "
                f"'{prev_name}' (line {prev_lineno})"
            )

    if violations:
        print(
            f"check_metadata_sorted: {path}: operator_name entries are NOT "
            f"in alphabetical order. Found {len(violations)} violation(s):",
            file=sys.stderr,
        )
        for v in violations:
            print(v, file=sys.stderr)
        print(
            "\nTo fix: re-order the entries in the file alphabetically by "
            "operator_name.  Underscore-prefixed names (e.g. '_softmax') "
            "sort before regular letters.",
            file=sys.stderr,
        )
        return False

    return True


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify that codegen/inputs/Metadata.yaml lists operator entries "
            "in strict alphabetical order by operator_name."
        )
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help=(
            "Path(s) to Metadata.yaml file(s) to check. "
            "When omitted, defaults to codegen/inputs/Metadata.yaml "
            "relative to the repository root."
        ),
    )
    args = parser.parse_args(argv)

    # pre-commit passes the matched filenames as positional arguments.
    # If none are given (direct invocation), fall back to the default path.
    targets = [Path(f) for f in args.files] if args.files else [_DEFAULT_YAML]

    all_ok = True
    for target in targets:
        if not target.exists():
            print(
                f"check_metadata_sorted: {target}: file not found.",
                file=sys.stderr,
            )
            all_ok = False
            continue
        if not check_sorted(target):
            all_ok = False

    if all_ok:
        # Quiet on success — consistent with standard linter conventions.
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
