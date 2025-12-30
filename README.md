# gitmergepy

AST-based merge conflict resolver for Python files.

Unlike text-based merge tools, gitmergepy parses Python code into an Abstract Syntax Tree (AST) using [RedBaron](https://github.com/Osso/redbaron) and applies semantic changes. This allows it to intelligently handle:

- Function and class renames/moves
- Import reorganization
- Argument reordering
- Decorator changes
- And more...

## Installation

Requires Python 3.12+.

```bash
# Using uv (recommended)
uv add gitmergepy

# Or with pip
pip install gitmergepy
```

## Usage

### Command Line

```bash
gitmergepy <base_file> <current_file> <other_file>
```

- `base_file`: The common ancestor file
- `current_file`: Your current version (modified in place)
- `other_file`: The other version to merge

Exit codes:
- `0`: Merge succeeded without conflicts
- `1`: Merge completed but has conflicts (marked in file)
- `2`: Merge failed due to syntax error

### As a Library

```python
from gitmergepy.runner import merge_files, merge_ast
from redbaron import RedBaron

# Merge files directly
success = merge_files("base.py", "current.py", "other.py")

# Or work with ASTs
base_ast = RedBaron(open("base.py").read())
current_ast = RedBaron(open("current.py").read())
other_ast = RedBaron(open("other.py").read())
merge_ast(base_ast, current_ast, other_ast)
print(current_ast.dumps())
```

### Git Merge Driver

To use as a git merge driver, add to your `.gitattributes`:

```
*.py merge=gitmergepy
```

And configure git:

```bash
git config merge.gitmergepy.driver "gitmergepy %O %A %B"
```

## How It Works

1. **Parse**: All three files (base, current, other) are parsed into ASTs
2. **Diff**: Compute semantic differences between base and other
3. **Apply**: Apply those changes to current
4. **Conflict**: Mark unresolvable conflicts as comments

The diff algorithm identifies:
- Added/removed elements (functions, classes, imports)
- Changed elements (modified function bodies, renamed items)
- Moved elements (reordered arguments, reorganized imports)

## Development

```bash
# Clone and install
git clone https://github.com/Osso/git-merge-py
cd git-merge-py
uv sync --dev

# Run tests
uv run pytest

# Type check
uv run pyright
```

## Dependencies

- [baron](https://github.com/Osso/baron) - Python AST parser
- [redbaron](https://github.com/Osso/redbaron) - Full Syntax Tree manipulation
- [python-Levenshtein](https://github.com/maxbachmann/python-Levenshtein) - String similarity
- [diff-match-patch](https://github.com/google/diff-match-patch) - Text diffing

## License

MIT
