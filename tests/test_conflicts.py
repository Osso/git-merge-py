import logging

from redbaron import RedBaron

from gitmergepy.applyier import apply_changes
from gitmergepy.differ import compute_diff


def _test_merge_changes(base, current, other, expected):
    base_ast = RedBaron(base)
    current_ast = RedBaron(current)
    other_ast = RedBaron(other)
    assert base_ast.dumps() != current_ast.dumps()

    changes = compute_diff(base_ast, current_ast)
    logging.debug("======== changes from current ========")
    for change in changes:
        logging.debug(change)
    apply_changes(other_ast, changes)
    logging.debug("======= changes applied to other =======")
    logging.debug(other_ast.dumps())
    logging.debug("=========")
    assert other_ast.dumps() == expected


def test_change_with():
    base = """# stuff
with fun() as out:
    call('hello')
# more stuff
"""
    current = """# stuff
call('hello')
# more stuff
"""
    other = """# changed stuff
with fun() as out:
    call('hello')
with fun() as out:
    call('world')
# more stuff
"""
    expected = """# <<<<<<<<<<
# Reason Multiple with nodes found
# <RemoveWith el="with fun() as out:" context='# stuff'>
# with fun() as out:
#     call('hello')
# # more stuff
# >>>>>>>>>>
# changed stuff
with fun() as out:
    call('hello')
with fun() as out:
    call('world')
# more stuff
"""
    _test_merge_changes(base, current, other, expected)
