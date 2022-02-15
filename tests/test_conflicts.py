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


def test_added_elements_different_context():
    base = """
if cond:
    # context
    pass
"""
    current = """
if cond:
    # context
    # added elements
    pass
"""
    other = """
if cond:
    # changed context
    changed_too
"""
    expected = """
# <<<<<<<<<<
# Reason context not found
# <AddEls to_add="    # added elements" context='None|    # context'>
#     # added elements
# >>>>>>>>>>
if cond:
    # changed context
    changed_too
"""
    ast = _test_merge_changes(base, current, other, expected)
    assert isinstance(ast[0], nodes.CommentNode)


def test_if_else():
    base = """
if cond:
    pass
"""
    current = """
if cond:
    # added elements
    pass
"""
    other = """
# different context
if cond:
    # changed context 1
    # changed context 2
    pass
if cond:
    # changed context 1
    # changed context 2
    pass
"""
    expected = """
# <<<<<<<<<<
# Reason el not found
# <ChangeEl el="if cond:" context='None'> changes=
# .<ChangeValue el="if cond:" context='no context'> changes=
# ..<ChangeEl el="if cond:" context='None'> changes=
# ...<AddEls to_add="    # added elements" context='None'>
# ...<SameEl el="    pass">
# if cond:
#     pass
# >>>>>>>>>>
# different context
if cond:
    # changed context 1
    # changed context 2
    pass
if cond:
    # changed context 1
    # changed context 2
    pass
"""
    ast = _test_merge_changes(base, current, other, expected)
    assert isinstance(ast[0], nodes.CommentNode)
