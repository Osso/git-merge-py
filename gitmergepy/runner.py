import logging
import pdb
import traceback

from redbaron import RedBaron

from gitmergepy.applyier import apply_changes
from gitmergepy.conflicts import add_conflicts
from gitmergepy.differ import compute_diff_iterables


def parse_file(filename):
    with open(filename, 'r') as f:
        return RedBaron(f.read())


def main(args):
    logging.basicConfig(level=logging.DEBUG, format='%(message)s')
    logging.debug(" ".join(args))
    base_file = args[0]
    current_file = args[1]
    other_file = args[2]

    try:
        r = merge_files(base_file, current_file, other_file)
    except Exception as e:
        traceback.print_exc()
        pdb.post_mortem(e.__traceback__)
    else:
        return 0 if r else 1


def merge_files(base_file, current_file, other_file):
    base_ast = parse_file(base_file)
    current_ast = parse_file(current_file)
    other_ast = parse_file(other_file)
    merge_ast(base_ast, current_ast, other_ast)
    output = current_ast.dumps()
    with open(current_file, 'w') as out:
        out.write(output)
    return ">>>>>>>>>>>>>>>>>>>" not in output


def merge_ast(base_ast, current_ast, other_ast):
    changes = compute_diff_iterables(base_ast, other_ast)
    logging.info("=========== applying changes")
    conflicts = apply_changes(current_ast, changes)
    add_conflicts(current_ast, conflicts)
