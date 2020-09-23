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
<<<<<<<<<<
# <ChangeEl el="fun(arg1)" changes=[<ChangeAtomtrailersCall el="(arg1)" changes=[<AddCallArg arg='arg2' context='arg1'>] context='no context'>] context='first'>
>>>>>>>>>>
fun(new_arg1)
"""
    _test_merge_changes(base, current, other, expected)
