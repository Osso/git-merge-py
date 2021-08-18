import logging

from redbaron import (RedBaron,
                      nodes)

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
    return other_ast


def test_if_else():
    base = """
if cond:
    # context
    pass
"""
    current = """
if cond:
    # context
    # text
    pass
"""
    other = """
if cond:
    # changed context
    pass
"""
    expected = """
# <<<<<<<<<<
# Reason context not found
# <AddEls to_add="    # text" context='    # context'>
#     # text
# >>>>>>>>>>
if cond:
    # changed context
    pass
"""
    ast = _test_merge_changes(base, current, other, expected)
    assert isinstance(ast[0], nodes.CommentNode)
