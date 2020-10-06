import logging

from redbaron import RedBaron

from gitmergepy.applyier import apply_changes_safe
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
    logging.debug("=========")
    base_ast_patched = base_ast.copy()
    apply_changes_safe(base_ast_patched, changes)
    logging.debug("======= changes applied to base =======")
    logging.debug(base_ast_patched.dumps())
    logging.debug("=========")
    assert base_ast_patched.dumps() == current_ast.dumps()
    apply_changes_safe(other_ast, changes)
    logging.debug("======= changes applied to other =======")
    logging.debug(other_ast.dumps())
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
    base = """def fun1():
    call('hello')

def fun2():
    pass
"""
    current = """def fun2():
    pass

def fun1():
    call('hello')
"""
    other = """def fun1():
    call('hello world')

def fun2():
    pass
"""
    expected = """def fun2():
    pass

def fun1():
    call('hello world')
"""
    _test_merge_changes(base, current, other, expected)


def test_move_function_without_context():
    base = """def fun1():
    call('hello')

def fun2():
    pass
"""
    current = """def fun2():
    pass

def fun1():
    call('hello')
"""
    other = """def fun1():
    call('hello world')
"""
    expected = """def fun1():
    call('hello world')
"""
    _test_merge_changes(base, current, other, expected)


def test_remove_with():
    base = """
with fun():
    call('hello')
"""
    current = """
call('hello')
"""
    other = """
with fun():
    call('hello world')
"""
    expected = """
call('hello world')
"""
    _test_merge_changes(base, current, other, expected)


def test_change_with():
    base = """
with fun():
    call('hello')
"""
    current = """
with fun2():
    call('hello')
"""
    other = """
with fun():
    call('hello world')
"""
    expected = """
with fun2():
    call('hello world')
"""
    _test_merge_changes(base, current, other, expected)


def test_rename_function():
    base = """
def fun1():
    call('hello')

def fun2():
    pass
"""
    current = """
def renamed_fun():
    call('hello')

def fun2():
    pass
"""
    other = """
def fun1():
    call('hello world')

def fun2():
    pass
"""
    expected = """
def renamed_fun():
    call('hello world')

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


def test_already_removed_el():
    base = """
# el 1
# el 2
# el 3
"""
    current = """
# el 1
# el 3
"""
    other = """
# el 3
"""
    expected = """
# el 3
"""
    _test_merge_changes(base, current, other, expected)


def test_if():
    base = """
if cond:
    pass
"""
    current = """
if cond:
    call('hello')
"""
    other = """
if cond2:
    pass
"""
    expected = """
if cond2:
    call('hello')
"""
    _test_merge_changes(base, current, other, expected)


def test_if_else():
    base = """
if cond:
    pass
else:
    pass
"""
    current = """
if cond:
    pass
else:
    call('hello')
"""
    other = """
if cond:
    pass
else:
    # passing here
    pass
"""
    expected = """
if cond:
    pass
else:
    # passing here
    call('hello')
"""
    _test_merge_changes(base, current, other, expected)


def test_if_else_2():
    base = """
if cond:
    pass
else:
    pass
"""
    current = """
if cond:
    pass
else:
    pass
    call('hello')
"""
    other = """
if cond:
    pass
else:
    # passing here
    pass
"""
    expected = """
if cond:
    pass
else:
    # passing here
    pass
    call('hello')
"""
    _test_merge_changes(base, current, other, expected)
