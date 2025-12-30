"""gitmergepy - AST-based merge conflict resolver for Python files."""

from .runner import main, merge_ast, merge_files

__all__ = ["main", "merge_ast", "merge_files"]
__version__ = "0.1.0"
