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
    print("=========")
    apply_changes_safe(base_ast, changes)
    print("======= changes applied to base =======")
    print(base_ast.dumps())
    print("=========")
    assert base_ast.dumps() == current_ast.dumps()
    apply_changes_safe(other_ast, changes)
    print("======= changes applied to other =======")
    print(other_ast.dumps())
    assert other_ast.dumps() == expected


def test_add_import():
    base = """
from module1 import fun1
"""
    current = """
from module1 import (fun1,
                     fun2)
"""
    other = """
from module1 import fun3
"""
    expected = """
from module1 import (fun2,
                     fun3)
"""
    _test_merge_changes(base, current, other, expected)


def test_add_import_2():
    base = """
from module1 import fun1
"""
    current = """
from module1 import (fun1,
                     fun3)
"""
    other = """
from module1 import fun2
"""
    expected = """
from module1 import (fun2,
                     fun3)
"""
    _test_merge_changes(base, current, other, expected)


def test_move_function():
    base = """
def fun1():
    print('hello')

def fun2():
    pass
"""
    current = """
def fun2():
    pass

def fun1():
    print('hello')
"""
    other = """
def fun1():
    print('hello world')

def fun2():
    pass
"""
    expected = """
def fun2():
    pass

def fun1():
    print('hello world')
"""
    _test_merge_changes(base, current, other, expected)


def test_move_function_without_context():
    base = """
def fun1():
    print('hello')

def fun2():
    pass
"""
    current = """
def fun2():
    pass

def fun1():
    print('hello')
"""
    other = """
def fun1():
    print('hello world')
"""
    expected = """
def fun1():
    print('hello world')
"""
    _test_merge_changes(base, current, other, expected)


def test_remove_with():
    base = """
with fun():
    print('hello')
"""
    current = """
print('hello')
"""
    other = """
with fun():
    print('hello world')
"""
    expected = """
print('hello world')
"""
    _test_merge_changes(base, current, other, expected)


def test_change_with():
    base = """
with fun():
    print('hello')
"""
    current = """
with fun2():
    print('hello')
"""
    other = """
with fun():
    print('hello world')
"""
    expected = """
with fun2():
    print('hello world')
"""
    _test_merge_changes(base, current, other, expected)


def test_rename_function():
    base = """
def fun1():
    print('hello')

def fun2():
    pass
"""
    current = """
def renamed_fun():
    print('hello')

def fun2():
    pass
"""
    other = """
def fun1():
    print('hello world')

def fun2():
    pass
"""
    expected = """
def renamed_fun():
    print('hello world')

def fun2():
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_change_fun_args():
    base = """
def fun1(arg1, arg2, arg3):
    pass
"""
    current = """
def fun1(arg1, new_arg2, arg3):
    pass
"""
    other = """
def fun1(arg1, arg2, new_arg3):
    pass
"""
    expected = """
def fun1(arg1, new_arg2, new_arg3):
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_already_removed_arg():
    base = """
def fun1(arg):
    pass
"""
    current = """
def fun1():
    pass
"""
    other = """
def fun1():
    pass
"""
    expected = """
def fun1():
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_change_call_args():
    base = """
fun(arg1, arg2, arg3)
"""
    current = """
fun(arg1, new_arg2, arg3)
"""
    other = """
fun(arg1, arg2, new_arg3)
"""
    expected = """
fun(arg1, new_arg2, new_arg3)
"""
    _test_merge_changes(base, current, other, expected)


def test_change_call_args_assignment():
    base = """
a = fun(arg1, arg2, arg3)
"""
    current = """
a = fun(arg1, new_arg2, arg3)
"""
    other = """
a = fun(arg1, arg2, new_arg3)
"""
    expected = """
a = fun(arg1, new_arg2, new_arg3)
"""
    _test_merge_changes(base, current, other, expected)


def test_change_call_fun_arg():
    base = """
fun(sub(arg1, arg2))
"""
    current = """
fun(sub(arg1=1, arg2))
"""
    other = """
fun(sub(arg1, arg2=2))
"""
    expected = """
fun(sub(arg1=1, arg2=2))
"""
    _test_merge_changes(base, current, other, expected)


# def test_tmp():
#     with open('base.py') as f:
#         base = f.read()
#     with open('current.py') as f:
#         current = f.read()
#     other = base
#     expected = current
#     _test_merge_changes(base, current, other, expected)
