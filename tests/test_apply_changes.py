import logging

import pytest
from redbaron import RedBaron

from gitmergepy.applyier import apply_changes
from gitmergepy.differ import compute_diff
from gitmergepy.tree import (ChangeImport,
                             MoveImport)


def _test_apply_changes(base, current):
    base_ast = RedBaron(base)
    current_ast = RedBaron(current)
    assert base_ast.dumps() != current_ast.dumps()

    changes = compute_diff(base_ast, current_ast)
    logging.debug("applying changes")
    base_ast_patched = RedBaron(base)
    conflicts = apply_changes(base_ast_patched, changes)
    logging.debug("======= new_ast =======\n%s", base_ast_patched.dumps())
    assert not conflicts
    assert base_ast_patched.dumps() == current_ast.dumps()


def test_change_first_line():
    base = """
def fun():
    call('hello')
"""
    current = """
def fun():
    call('hello world')
"""
    _test_apply_changes(base, current)


def test_change_fun_arg():
    base = """
def fun(arg):
    pass
"""
    current = """
def fun(new_arg):
    pass
"""
    _test_apply_changes(base, current)


def test_change_fun_arg_middle():
    base = """
def fun(arg1=1, arg2=2, arg3=3):
    pass
"""
    current = """
def fun(arg1=1, new_arg2=2, arg3=3):
    pass
"""
    _test_apply_changes(base, current)


def test_change_fun_arg_last():
    base = """
def fun(arg1=1, arg2=2, arg3=3):
    pass
"""
    current = """
def fun(arg1=1, arg2=2, new_arg3=3):
    pass
"""
    _test_apply_changes(base, current)


def test_change_fun_default():
    base = """
def fun(arg=1):
    pass
"""
    current = """
def fun(arg=2):
    pass
"""
    _test_apply_changes(base, current)


def test_change_line_with_context():
    base = """
def fun():
    # calling hello
    call('hello')
"""
    current = """
def fun():
    # calling hello
    call('hello world')
"""
    _test_apply_changes(base, current)


def test_change_line_middle():
    base = """
# line 1
# line 2
# line 3
"""
    current = """
# line 1
# line 2 modified
# line 3
"""
    _test_apply_changes(base, current)


def test_move_function():
    base = """def fun1():
    call('fun1')

def fun2():
    call('fun2')
"""
    current = """def fun2():
    call('fun2')

def fun1():
    call('fun1')
"""
    _test_apply_changes(base, current)


def test_move_function_with_empty_lines():
    base = """def fun1():
    call('fun1')

def fun2():
    call('fun2')

# end
"""
    current = """def fun2():
    call('fun2')

def fun1():
    call('fun1')

# end
"""
    _test_apply_changes(base, current)
    changes = compute_diff(RedBaron(base), RedBaron(current))
    assert len(changes) == 1


def test_add_import():
    base = """
from module1 import fun1
"""
    current = """
from module1 import fun1, fun2
"""
    _test_apply_changes(base, current)


def test_add_import_brackets():
    base = """
from module1 import fun1
"""
    current = """
from module1 import (fun1, fun2)
"""
    _test_apply_changes(base, current)


def test_add_import_as():
    base = """
from module1 import fun1 as f1
"""
    current = """
from module1 import fun1 as f1, fun2
"""
    _test_apply_changes(base, current)


def test_add_import_module():
    base = """
import module1
"""
    current = """
import module1
import module2
"""
    _test_apply_changes(base, current)


def test_add_import_multiline():
    base = """
from module1 import fun1
"""
    current = """
from module1 import (fun1,
                     fun2)
"""
    _test_apply_changes(base, current)


def test_add_import_multiline_first():
    base = """
from module1 import fun2
"""
    current = """
from module1 import (fun1,
                     fun2)
"""
    _test_apply_changes(base, current)


def test_add_import_multiline_last():
    base = """
from module1 import (fun1,
                     fun2)
"""
    current = """
from module1 import (fun1,
                     fun2,
                     fun3)
"""
    _test_apply_changes(base, current)


def test_add_import_as_is():
    base = """
# comment
"""
    current = """
from module1 import (fun1,
                     fun2)
"""
    _test_apply_changes(base, current)


def test_remove_import_first():
    base = """
from module1 import fun1, fun2
"""
    current = """
from module1 import fun1
"""
    _test_apply_changes(base, current)


def test_remove_import_last():
    base = """
from module1 import fun1, fun2
"""
    current = """
from module1 import fun2
"""
    _test_apply_changes(base, current)


def test_remove_import_middle():
    base = """
from module1 import fun1, fun2, fun3
"""
    current = """
from module1 import fun1, fun3
"""
    _test_apply_changes(base, current)


def test_remove_import_brackets():
    base = """
from module1 import (fun1, fun2)
"""
    current = """
from module1 import fun1
"""
    _test_apply_changes(base, current)


def test_remove_import_two():
    base = """
from module1 import (fun1, fun2, fun3)
"""
    current = """
from module1 import fun1
"""
    _test_apply_changes(base, current)


def test_remove_with():
    base = """
with fun():
    call('hello')
"""
    current = """
call('hello')
"""
    _test_apply_changes(base, current)


def test_change_with():
    base = """
with fun():
    call('hello')
"""
    current = """
with fun2():
    call('hello')
"""
    _test_apply_changes(base, current)


def test_change_with_double():
    base = """
with fun() as f, fun2() as f2:
    call('hello')
"""
    current = """
with fun3() as f3:
    call('hello')
"""
    _test_apply_changes(base, current)


def test_change_with_content():
    base = """
with fun():
    call('hello')
"""
    current = """
with fun():
    call('hello world')
"""
    _test_apply_changes(base, current)


def test_rename_function():
    base = """
def fun1():
    call('fun1')
"""
    current = """
def renamed_function():
    call('fun1')
"""
    _test_apply_changes(base, current)


def test_new_function():
    base = """
def fun1():
    call('fun1')

def fun2():
    call('fun2')
"""
    current = """
def fun1():
    call('fun1')

def new_fun():
    call('new fun')

def fun2():
    call('fun2')
"""
    _test_apply_changes(base, current)


def test_remove_function():
    base = """
def fun1():
    call('fun1')

def old_fun():
    call('old fun')

def fun2():
    call('fun2')

def fun3():
    call('fun3')
"""
    current = """
def fun1():
    call('fun1')

def fun2():
    call('fun2')

def fun3():
    call('fun3')
"""
    _test_apply_changes(base, current)


def test_first_line_changed():
    base = """
def fun():
    # line1
    pass
    # line3
"""
    current = """
def fun():
    # line1 changed
    pass
    # line3 changed
"""
    _test_apply_changes(base, current)


def test_func_call_add_arg():
    base = """
fun1(arg1)
"""
    current = """
fun1(arg1, arg2)
"""
    _test_apply_changes(base, current)


def test_add_block():
    base = """
# line 1
# line 2
# line 3
"""
    current = """
# line 1
# line 2 changed
# line 3 changed
"""
    _test_apply_changes(base, current)


def test_change_call_arg():
    base = """
fun(arg)
"""
    current = """
fun(new_arg)
"""
    _test_apply_changes(base, current)


def test_change_call_arg_middle():
    base = """
fun(arg1, arg2, arg3)
"""
    current = """
fun(arg1, new_arg2, arg3)
"""
    _test_apply_changes(base, current)


def test_change_call_arg_last():
    base = """
fun(arg1, arg2, arg3)
"""
    current = """
fun(arg1, arg2, new_arg3)
"""
    _test_apply_changes(base, current)


def test_change_call_default():
    base = """
fun(arg=1)
"""
    current = """
fun(arg=2)
"""
    _test_apply_changes(base, current)


def test_change_call_arg_equal():
    base = """
a = fun(arg)
"""
    current = """
a = fun(new_arg)
"""
    _test_apply_changes(base, current)


def test_add_decorator():
    base = """
def fun():
    pass
"""
    current = """
@decorator
def fun():
    pass
"""
    _test_apply_changes(base, current)


def test_remove_decorator():
    base = """
@decorator
def fun():
    pass
"""
    current = """
def fun():
    pass
"""
    _test_apply_changes(base, current)


def test_remove_decorator_first():
    base = """
@decorator1
@decorator2
def fun():
    pass
"""
    current = """
@decorator2
def fun():
    pass
"""
    _test_apply_changes(base, current)


def test_add_decorator_first():
    base = """
@decorator2
def fun():
    pass
"""
    current = """
@decorator1
@decorator2
def fun():
    pass
"""
    _test_apply_changes(base, current)


def test_add_decorator_last():
    base = """
@decorator1
def fun():
    pass
"""
    current = """
@decorator1
@decorator2
def fun():
    pass
"""
    _test_apply_changes(base, current)


def test_add_decorator_middle():
    base = """
@decorator1
@decorator3
def fun():
    pass
"""
    current = """
@decorator1
@decorator2
@decorator3
def fun():
    pass
"""
    _test_apply_changes(base, current)


def test_decorator_args():
    base = """
def fun():
    pass
"""
    current = """
@decorator(arg1, arg2)
def fun():
    pass
"""
    _test_apply_changes(base, current)


def test_call_replace_call():
    base = """
fun(sub1())
"""
    current = """
fun(sub2())
"""
    _test_apply_changes(base, current)


def test_call_change_call():
    base = """
fun(arg=sub1())
"""
    current = """
fun(arg=sub2())
"""
    _test_apply_changes(base, current)


def test_call_change_call_arg():
    base = """
fun(arg=sub(arg1))
"""
    current = """
fun(arg=sub(arg2))
"""
    _test_apply_changes(base, current)


def test_class():
    base = """
class A:
    pass
"""
    current = """
class A:
    call('hello')
"""
    _test_apply_changes(base, current)


def test_class_def():
    base = """
class A:
    def fun():
        pass
"""
    current = """
class A:
    def fun():
        call('hello')
"""
    _test_apply_changes(base, current)


def test_class_decorator():
    base = """
class A:
    pass
"""
    current = """
@decorator
class A:
    pass
"""
    _test_apply_changes(base, current)


def test_class_name():
    base = """class A:
    pass
"""
    current = """class B:
    pass
"""
    _test_apply_changes(base, current)


def test_def_multiline():
    base = """
def fun(arg1):
    pass
"""
    current = """
def fun(arg1,
        arg2):
    pass
"""
    _test_apply_changes(base, current)


def test_def_multiline_three():
    base = """
def fun(arg1,
        arg2):
    pass
"""
    current = """
def fun(arg1,
        arg2,
        arg3):
    pass
"""
    _test_apply_changes(base, current)


def test_call_multiline():
    base = """
fun(arg1,
    arg2)
"""
    current = """
fun(arg1,
    arg2,
    arg3)
"""
    _test_apply_changes(base, current)


def test_multi_call():
    base = """
fun1().fun2()
"""
    current = """
fun1(arg1).fun2(arg2)
"""
    _test_apply_changes(base, current)


def test_line_with_comment():
    base = """
# comment
"""
    current = """
# comment
a = 1  # assignment
"""
    _test_apply_changes(base, current)


def test_star_args():
    base = """
fun(arg1, *args, **kwargs)
"""
    current = """
fun(arg1, arg2, *args, **kwargs)
"""
    _test_apply_changes(base, current)


def test_if():
    base = """
if cond:
    pass
"""
    current = """
if cond:
    call('hello')
"""
    _test_apply_changes(base, current)


def test_class_def_decorator():
    base = """
class A:
    def fun():
        pass
"""
    current = """
class A:
    @decorator
    def fun():
        pass
"""
    _test_apply_changes(base, current)


def test_with_removal_keeps_indentation():
    base = """
    def fun1():
        with f:
            if cond:
                pass

    def fun2():
        pass
"""
    current = """
    def fun1():
        if cond:
            pass

    def fun2():
        pass
"""
    _test_apply_changes(base, current)


def test_with_remove_multiline_args():
    base = """
with f:
    a = klass.method(arg1=1,
                     arg2=2)
"""
    current = """
a = klass.method(arg1=1,
                 arg2=2)
"""
    _test_apply_changes(base, current)


def test_if_match_cond():
    base = """
    if cond1:
        pass
    if cond2:
        pass
"""
    current = """
    if cond1:
        pass
    if cond2:
        call('hello')
"""
    _test_apply_changes(base, current)


def test_change_indentation():
    base = """
    call('hello')
"""
    current = """
        call('hello')
"""
    _test_apply_changes(base, current)


def test_argument_annotation():
    base = """
def fun(arg):
    pass
"""
    current = """
def fun(arg: my_type):
    pass
"""
    _test_apply_changes(base, current)


def test_argument_annotation_add():
    base = """
def fun(arg):
    pass
"""
    current = """
def fun(arg, arg2: my_type):
    pass
"""
    _test_apply_changes(base, current)


def test_argument_annotation_remove():
    base = """
def fun(arg: my_type):
    pass
"""
    current = """
def fun(arg):
    pass
"""
    _test_apply_changes(base, current)


def test_change_fun_arg_new_line():
    base = """
def fun(arg1, arg2):
    pass
"""
    current = """
def fun(arg1,
        arg2):
    pass
"""
    _test_apply_changes(base, current)


def test_change_fun_arg_new_line_kwargs():
    base = """
def fun(arg1, **arg2):
    pass
"""
    current = """
def fun(arg1,
        **arg2):
    pass
"""
    _test_apply_changes(base, current)


def test_change_fun_arg_new_line_star_args_indent():
    base = """
def fun(arg1,
        *arg2):
    pass
"""
    current = """
def fun(arg1,
          *arg2):
    pass
"""
    _test_apply_changes(base, current)


def test_change_fun_arg_new_line_kwargs_indent():
    base = """
def fun(arg1,
        **arg2):
    pass
"""
    current = """
def fun(arg1,
          **arg2):
    pass
"""
    _test_apply_changes(base, current)


def test_put_on_new_line():
    base = """
def fun(session: SQLSession, service="JOYN",
        pta_code=None, price_range=None,
        category=None, csu_state=None):
   pass
"""
    current = """
def fun(session: SQLSession,
        service="JOYN",
        pta_code=None,
        price_range=None,
        category=None,
        csu_state=None):
   pass
"""
    _test_apply_changes(base, current)


def test_if_change_indent():
    base = """
    if cond:
        pass
    elif cond:
        pass
"""
    current = """
if cond:
        pass
elif cond:
    pass
"""
    _test_apply_changes(base, current)


def test_dict_add():
    base = """
    {'key': 'value'}
"""
    current = """
    {'key': 'value', 'new_key': 'value'}
"""
    _test_apply_changes(base, current)


def test_dict_add_multiline():
    base = """
    {'key': 'value'}
"""
    current = """
    {'key': 'value',
     'new_key': 'value'}
"""
    _test_apply_changes(base, current)


def test_dict_add_multiline2():
    base = """
    a = {
        'key': 'value'
    }
"""
    current = """
    a = {
        'key': 'value',
        'new_key': 'value',
    }
"""
    _test_apply_changes(base, current)


def test_dict_remove():
    base = """
    {'key': 'value', 'new_key': 'value'}
"""
    current = """
    {'key': 'value'}
"""
    _test_apply_changes(base, current)


def test_dict_change():
    base = """
    {'key': 'value'}
"""
    current = """
    {'key': 'value2'}
"""
    _test_apply_changes(base, current)


def test_add_inline_comment():
    base = """
    fun()
"""
    current = """
    fun()  # inline comment
"""
    _test_apply_changes(base, current)


def test_remove_inline_comment():
    base = """
    fun()  # inline comment
    more()
"""
    current = """
    fun()
    more()
"""
    _test_apply_changes(base, current)


def test_remove_inline_comment_2():
    base = """
call(value1)  # comment
fun()

call(value2)  # comment
fun()
"""
    current = """
call(value1)  # comment

call(value2)  # comment
"""
    _test_apply_changes(base, current)


def test_with_remove_arg():
    base = """
# context
with f(arg):
    pass

with another_one:
    pass
"""
    current = """
# context
with f():
    call()

with another_one:
    pass
"""
    _test_apply_changes(base, current)


def test_remove_blank_line_fun_args():
    base = """
call(
     value1)
"""
    current = """
call(value1)
"""
    _test_apply_changes(base, current)


def test_add_blank_line_fun_args():
    base = """
call(arg1, arg2,
     arg3, arg4)
"""
    current = """
call(
  arg1, arg2,
  arg3,
  arg4)
"""
    _test_apply_changes(base, current)


def test_embedded_dict():
    base = """
d = {
    "key1": {
        'sub_key1': {
            'queue': 'value1',
        },
        'sub_key3': {
            'queue': 'value3',
        },
    }
}
"""
    current = """
d = {
    "key1": {
        'sub_key1': {
            'queue': 'value1',
        },
        'sub_key2': {
            'queue': 'value2',
        },
        'sub_key3': {
            'queue': 'value3',
        },
    }
}
"""
    _test_apply_changes(base, current)


def test_class_bases():
    base = """
class C(BaseA):
    pass
"""
    current = """
class C(BaseB):
    pass
"""
    _test_apply_changes(base, current)


def test_add_2_blocks():
    """Test for last_added bug in add_to_diff.
    The bug resulting the 2 blocks being merged."""
    base = """
# not changed
"""
    current = """
# line 1
# line 2
# not changed
# line 3
# line 4
"""
    _test_apply_changes(base, current)


def test_context_repeated_replace():
    base = """
# context 1
# context repeated
# line 1
# context 2
# context repeated
# line 1
"""
    current = """
# context 1
# context repeated
# line 1
# context 2
# context repeated
# line 1 changed
"""
    _test_apply_changes(base, current)


def test_context_repeated_remove():
    base = """
# context 1
# context repeated
# line 1
# context 2
# context repeated
# line 1
"""
    current = """
# context 1
# context repeated
# line 1
# context 2
# context repeated
"""
    _test_apply_changes(base, current)


def test_context_changed_replace():
    base = """
# context 1
# context repeated
# line 1
# context 2
# context repeated
# line 1
"""
    current = """
# context changed
# context repeated
# line 1 changed
"""
    _test_apply_changes(base, current)


def test_context_changed_remove():
    base = """
# context 1
# context repeated
# line 1
# context 2
# context repeated
# line 1
"""
    current = """
# context changed
# context repeated
"""
    _test_apply_changes(base, current)


def test_double_rename_class():
    base = """
class A: a()
class B: b()
"""
    current = """
class C: a()
class A: b()
"""
    _test_apply_changes(base, current)


def test_double_rename_def():
    base = """
def A(): a()
def B(): b()
"""
    current = """
def C(): a()
def A(): b()
"""
    _test_apply_changes(base, current)


def test_def_move_arg():
    base = """
def fun(arg1, arg2):
    pass
"""
    current = """
def fun(arg2, arg1):
    pass
"""
    _test_apply_changes(base, current)


def test_move_import():
    base = """
from module1 import fun1
from module2 import fun2
from module3 import fun3
"""
    current = """
from module1 import fun1
from module3 import fun3
from module2 import fun2
"""
    _test_apply_changes(base, current)
    changes = compute_diff(RedBaron(base), RedBaron(current))
    assert len(changes) == 1
    assert isinstance(changes[0], ChangeImport)
    assert len(changes[0].changes) == 1
    assert isinstance(changes[0].changes[0], MoveImport)


@pytest.mark.skip
def test_old_new_tree_separation():
    """the comment is deleted twice and separated by a moved element"""
    base = """
# comment
from module1 import fun1
from module2 import fun2
# comment
from module3 import fun3
# comment
"""
    current = """
from module3 import fun3
# comment
from module2 import fun2
from module1 import fun1
"""
    _test_apply_changes(base, current)
