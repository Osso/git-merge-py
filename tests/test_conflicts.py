from redbaron import RedBaron

from gitmergepy.applyier import apply_changes_safe
from gitmergepy.differ import compute_diff


def _test_merge_changes(base, current, other, expected):
    base_ast = RedBaron(base)
    current_ast = RedBaron(current)
    other_ast = RedBaron(other)
    assert base_ast.dumps() != current_ast.dumps()

    changes = compute_diff(base_ast, current_ast)
    print("======== changes from current ========")
    for change in changes:
        print(change)
    apply_changes_safe(other_ast, changes)
    print("======= changes applied to other =======")
    print(other_ast.dumps())
    print("=========")
    assert other_ast.dumps() == expected


def test_change_call_args():
    base = """
fun(arg1)
"""
    current = """
fun(arg1, arg2)
"""
    other = """
fun(new_arg1)
"""
    expected = """
# <<<<<<<<<<
# Reason Argument context has changed
# <AddCallArg arg='arg2' context='arg1'>
# fun(arg1, arg2)
# >>>>>>>>>>
fun(new_arg1)
"""
    _test_merge_changes(base, current, other, expected)


def test_change_fun():
    base = """
def fun(arg1):
    pass
"""
    current = """
def fun(arg1, arg2):
    pass
"""
    other = """
def fun(new_arg1):
    pass
"""
    expected = """
# <<<<<<<<<<
# Reason Argument context has changed
# <AddFunArg arg='arg2' context='arg1'>
# def fun(arg1, arg2):
# >>>>>>>>>>
def fun(new_arg1):
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_change_with():
    base = """
# stuff
with fun() as out:
    print('hello')
"""
    current = """
# stuff
print('hello')
"""
    other = """
# changed stuff
with fun() as out:
    print('hello')
with fun() as out:
    print('world')
"""
    expected = """
# <<<<<<<<<<
# Reason Multiple with nodes found
# <RemoveWith el="with fun() as out:" context='# stuff'>
# with fun() as out:
#     print('hello')
# >>>>>>>>>>
# changed stuff
with fun() as out:
    print('hello')
with fun() as out:
    print('world')
"""
    _test_merge_changes(base, current, other, expected)
