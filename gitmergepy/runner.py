"""CLI entry point for gitmergepy merge conflict resolver."""

from __future__ import annotations

import logging

from redbaron import RedBaron

from gitmergepy.applier import apply_changes
from gitmergepy.conflicts import add_conflicts
from gitmergepy.differ import compute_diff_iterables


def parse_file(filename: str) -> RedBaron:
    """Parse a Python file and return its AST as a RedBaron tree."""
    with open(filename) as f:
        return RedBaron(f.read())


def main(args: list[str]) -> int:
    """Main entry point for the merge tool.

    Args:
        args: List of [base_file, current_file, other_file]

    Returns:
        0 if merge succeeded without conflicts,
        1 if merge completed but has conflicts,
        2 if merge failed due to syntax/value error,
        130 if interrupted by user.
    """
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")
    logging.debug(" ".join(args))
    base_file = args[0]
    current_file = args[1]
    other_file = args[2]

    try:
        r = merge_files(base_file, current_file, other_file)
    except (SyntaxError, ValueError) as e:
        logging.error("Failed to merge: %s", e)
        return 2
    except KeyboardInterrupt:
        return 130
    else:
        return 0 if r else 1


def merge_files(base_file: str, current_file: str, other_file: str) -> bool:
    """Perform a three-way merge of Python files.

    Args:
        base_file: Path to the common ancestor file
        current_file: Path to the current version (will be modified in place)
        other_file: Path to the other version to merge

    Returns:
        True if merge succeeded without conflicts, False if conflicts remain.
    """
    base_ast = parse_file(base_file)
    current_ast = parse_file(current_file)
    other_ast = parse_file(other_file)
    merge_ast(base_ast, current_ast, other_ast)
    output = current_ast.dumps()
    with open(current_file, "w") as out:
        out.write(output)
    return ">>>>>>>>>>>>>>>>>>>" not in output


def merge_ast(base_ast: RedBaron, current_ast: RedBaron, other_ast: RedBaron) -> None:
    """Merge changes from other_ast into current_ast using base_ast as reference.

    Args:
        base_ast: The common ancestor AST
        current_ast: The current version AST (modified in place)
        other_ast: The other version AST to merge from
    """
    changes = compute_diff_iterables(base_ast, other_ast)
    logging.info("=========== applying changes")
    conflicts = apply_changes(current_ast, changes)
    add_conflicts(current_ast, conflicts)
