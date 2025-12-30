import logging

from redbaron import RedBaron

from gitmergepy.applier import apply_changes
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

    base_ast_patched = RedBaron(base)
    apply_changes(base_ast_patched, changes)
    logging.debug("======= changes applied to base =======")
    logging.debug(base_ast_patched.dumps())
    logging.debug("=========")
    assert base_ast_patched.dumps() == current_ast.dumps()

    apply_changes(other_ast, changes)
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


def test_add_import_not_existing():
    base = """
from module1 import fun1
"""
    current = """
from module1 import (fun1,
                     fun2)
"""
    other = """
"""
    expected = """
from module1 import fun2
"""
    _test_merge_changes(base, current, other, expected)


def test_remove_import():
    base = """
from module1 import (fun1, fun2, fun3)
"""
    current = """
from module1 import fun3
"""
    other = """
from module1 import fun1
"""
    expected = """
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
    # line 1
    # line 2
    call('hello')
"""
    current = """
# line 1
# line 2
call('hello')
"""
    other = """
with fun():
    # line 1
    # line 2
    call('hello world')
"""
    expected = """
# line 1
# line 2
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


def test_change_with_2():
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
    call('hello')
with fun():
    call('world')
"""
    expected = """
with fun2():
    call('hello')
with fun():
    call('world')
"""
    _test_merge_changes(base, current, other, expected)


def test_change_with_content():
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
with fun() as out2:
    call('hello')
with fun() as out2:
    call('hello world')
# more stuff
"""
    expected = """# changed stuff
call('hello')
with fun() as out2:
    call('hello world')
# more stuff
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


def test_change_fun_args_append_on_miss():
    base = """
def fun1(arg1):
    pass
"""
    current = """
def fun1(arg1, arg2):
    pass
"""
    other = """
def fun1(new_arg1, arg3):
    pass
"""
    expected = """
def fun1(new_arg1, arg3, arg2):
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


def test_change_call_args_append_on_miss():
    base = """
fun(arg1)
"""
    current = """
fun(arg1, arg2)
"""
    other = """
fun(new_arg1, arg3)
"""
    expected = """
fun(new_arg1, arg3, arg2)
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
    # comment
    pass
"""
    current = """
if cond:
    # comment
    call('hello')
"""
    other = """
if cond2:
    # comment
    pass
"""
    expected = """
if cond2:
    # comment
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


def test_change_call_args_indented():
    base = """
    fun(arg1)
"""
    current = """
    fun(arg1, arg2)
"""
    other = """
    fun(new_arg1, arg3)
"""
    expected = """
    fun(new_arg1, arg3, arg2)
"""
    _test_merge_changes(base, current, other, expected)


def test_insert_after_inline_comment():
    base = """
call()
"""
    current = """
call()  # comment
"""
    other = """
call()
stuff
"""
    expected = """
call()  # comment
stuff
"""
    _test_merge_changes(base, current, other, expected)


def test_insert_inline_comment():
    base = """
call()
"""
    current = """
call()
stuff
"""
    other = """
call()  # comment
"""
    expected = """
call()  # comment
stuff
"""
    _test_merge_changes(base, current, other, expected)


def test_comments_for_def():
    base = """
def anchor():
    pass
def target():
    pass
"""
    current = """
def anchor():
    pass
# comment
def target():
    pass
"""
    other = """
def anchor():
    pass
def new_def():
    pass
def target():
    pass
"""
    expected = """
def anchor():
    pass
def new_def():
    pass
# comment
def target():
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_two_comments_for_def():
    base = """
def anchor():
    pass
def target():
    pass
"""
    current = """
def anchor():
    pass
# comment 1
# comment 2
# comment 3
def target():
    pass
"""
    other = """
def anchor():
    pass
def new_def():
    pass
def target():
    pass
"""
    expected = """
def anchor():
    pass
def new_def():
    pass
# comment 1
# comment 2
# comment 3
def target():
    pass
"""
    _test_merge_changes(base, current, other, expected)


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
    other = """
call(
  arg1, arg2,
  arg3, arg4)
"""
    expected = """
call(
  arg1, arg2,
  arg3,
  arg4)
"""
    _test_merge_changes(base, current, other, expected)


def test_add_blank_line_def_args():
    base = """
def fun(arg1, arg2,
        arg3, arg4):
    pass
"""
    current = """
def fun(
  arg1, arg2,
  arg3,
  arg4):
    pass
"""
    other = """
def fun(
  arg1, arg2,
  arg3, arg4):
    pass
"""
    expected = """
def fun(
  arg1, arg2,
  arg3,
  arg4):
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_dict_add_already_existing():
    base = "{'key2': v2, 'key3': v3}"
    current = "{'key': v, 'key2': v2, 'key3': v3}"
    other = "{'key': v, 'key2': v2, 'key3': v3}"
    expected = "{'key': v, 'key2': v2, 'key3': v3}"
    _test_merge_changes(base, current, other, expected)


def test_remove_with_bug_1():
    base = """
msisdn = "0600000001"

for key, value in NAPSTER_TEST_DATA.items():
    # base
    # anchor
    pass
"""
    current = """
for key, value in NAPSTER_TEST_DATA.items():
    # anchor
    pass
"""
    other = """
msisdn = "0600000001"

for key, value in NAPSTER_TEST_DATA.items():
    # base
    # current
    # anchor
    pass
"""
    expected = """
for key, value in NAPSTER_TEST_DATA.items():
    # current
    # anchor
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_context_bug_1():
    base = """
 def fun(self):
    p1, p2 = two()
    # deleted
    with f():
        self.set_main_loop()
        f1("stuff", s=s)
"""
    current = """
def fun(self):
    p1, p2 = two()
    # new line 1
    # new line 2
    # deleted
    with f():
        # self.set_main_loop()
        f1("stuff", s=s)
"""
    other = """
 def fun(self):
    p1, p2 = two()
    with f():
        # comment
        self.set_main_loop()
        f1("stuff", s=s)
"""
    expected = """
def fun(self):
    p1, p2 = two()
    # new line 1
    # new line 2
    with f():
        # comment
        # self.set_main_loop()
        f1("stuff", s=s)
"""
    _test_merge_changes(base, current, other, expected)


def test_rename_function_same_body():
    base = """
def fun(self):
    # body 1
    # body 2
    # body 3
    # body 4
    pass
"""
    current = """
def renamed_fun(self):
    # body 1
    # body 2
    # body 3
    # body 4
    pass
"""
    other = """
def fun(self):
    # body 1
    # body 2
    # body 3
    # body 4
    # changed body
    pass
"""
    expected = """
def renamed_fun(self):
    # body 1
    # body 2
    # body 3
    # body 4
    # changed body
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_rename_class_same_body():
    base = """
class C(self):
    # body 1
    # body 2
    # body 3
    # body 4
    pass
"""
    current = """
class RenamedClass(self):
    # body 1
    # body 2
    # body 3
    # body 4
    pass
"""
    other = """
class C(self):
    # body 1
    # body 2
    # body 3
    # body 4
    # changed body
    pass
"""
    expected = """
class RenamedClass(self):
    # body 1
    # body 2
    # body 3
    # body 4
    # changed body
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_if_else_3():
    base = """
if cond:
    pass
else:
    old_call()
    # unchanged comment
    pass
"""
    current = """
if cond:
    pass
else:
    new_call()
    # unchanged comment
    pass
"""
    other = """
if cond:
    pass
else:
    # new comment
    old_call()
    # unchanged comment
    pass
"""
    expected = """
if cond:
    pass
else:
    # new comment
    new_call()
    # unchanged comment
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_if_elif():
    base = """
if cond:
    pass
elif a == 2:
    original
    # more stuff
"""
    current = """
if cond:
    pass
elif a == 2:
    changed
    # more stuff
"""
    other = """
if cond:
    pass
elif a == 2:
    original
    # more stuff changed
"""
    expected = """
if cond:
    pass
elif a == 2:
    changed
    # more stuff changed
"""
    _test_merge_changes(base, current, other, expected)


def test_change_with_3():
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
with fun() as out2:
    call('hello')
with fun() as out2:
    call('hello')
# more stuff
"""
    expected = """# changed stuff
call('hello')
with fun() as out2:
    call('hello')
# more stuff
"""
    _test_merge_changes(base, current, other, expected)


def test_replace_with_new_comment():
    base = """
# body 1
# body 2
call()
call2()
"""
    current = """
# body 1
# body 2
# body 3
stuff()
more_stuff()
"""
    other = """
# body 1
# body 2
call()  # useless comment
call2()
"""
    expected = """
# body 1
# body 2
# body 3
stuff()
more_stuff()
"""
    _test_merge_changes(base, current, other, expected)


def test_call_with_integer_arg():
    base = """
call(1)
"""
    current = """
call(2)
"""
    other = """
call(3)
"""
    expected = """
call(2)
"""
    _test_merge_changes(base, current, other, expected)


def test_call_with_float_arg():
    base = """
call(1)
"""
    current = """
call(0.5)
"""
    other = """
call(3)
"""
    expected = """
call(0.5)
"""
    _test_merge_changes(base, current, other, expected)


def test_change_with_best_block():
    base = """
with fun():
    # 1
    # 2
    # 3
    # 4 first
    call(1)
# context
with fun():
    # 1
    # 2
    # 3
    # 4 second
    call(2)
"""
    current = """
with fun():
    # 1
    # 2
    # 3
    # 4 first
    call(1)
# context
with fun():
    # 1
    # 2
    # 3
    # 4 second
    call("changed")
"""
    other = """
with fun():
    # 1
    # 2
    # 3
    # 4 first
    call(1)
# changed context
with fun():
    # 1
    # 2
    # 3
    # 4 changed
    call(2)
"""
    expected = """
with fun():
    # 1
    # 2
    # 3
    # 4 first
    call(1)
# changed context
with fun():
    # 1
    # 2
    # 3
    # 4 changed
    call("changed")
"""
    _test_merge_changes(base, current, other, expected)


def test_fun_add_arg_already_existsing():
    base = """
def fun1(arg):
    pass
"""
    current = """
def fun1(arg, new_arg):
    pass
"""
    other = """
def fun1(arg, new_arg):
    pass
"""
    expected = """
def fun1(arg, new_arg):
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_fun_add_arg_already_existsing_2():
    base = """
def fun1(arg):
    pass
"""
    current = """
def fun1(arg, new_arg=new_arg):
    pass
"""
    other = """
def fun1(arg, new_arg=new_arg):
    pass
"""
    expected = """
def fun1(arg, new_arg=new_arg):
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_rename_and_add_function_after_context():
    base = """def context(): context()
def fun():
    call()
"""
    current = """def context(): context()
def fun():
    pass

def fun_renamed():
    call()
"""
    other = """
def changed_context(): context()

def fun():
    call()
"""
    expected = """
def changed_context(): context()
def fun():
    pass

def fun_renamed():
    call()
"""
    _test_merge_changes(base, current, other, expected)


def test_delete_out_of_order():
    base = """def fun():
        super().fun()
        reset_db()
        CACHE.flush_all()
        clear_all_event_stats()
        self.secret_base = ""
        self.secret_iv = ""
        self.client = stuff()
        self.proc = load()
        reset_mockups()
"""
    current = """def fun():
        super().fun()
        self.secret_base = ""
        self.secret_iv = ""
        self.client = stuff()
        self.proc = load()
"""
    other = """def fun():
        super().fun()
        reset_db()
        reset_mockups()
        CACHE.flush_all()
        clear_all_event_stats()
        self.secret_base = ""
"""
    expected = """def fun():
        super().fun()
        self.secret_base = ""
"""
    _test_merge_changes(base, current, other, expected)


def test_double_list():
    base = """
        a = sorted([
            'VAL1',
            'VAL2',
            'VAL3',
        ], [
            'VALUE1',
            'VALUE2',
        ])
"""
    current = """
        a = sorted([
            'VAL1',
            'VAL3',
        ], [
            'VALUE1',
            'VALUE2',
        ])
"""
    other = """
        a = sorted([
            'VAL2',
            'VAL3',
        ], [
            'VALUE1',
            'VALUE2',
        ])
"""
    expected = """
        a = sorted([
            'VAL3',
        ], [
            'VALUE1',
            'VALUE2',
        ])
"""
    _test_merge_changes(base, current, other, expected)


def test_assert():
    base = """assert stuff == set("A B C D")"""
    current = """assert stuff == set("A B C")"""
    other = """assert stuff == set("A B D")"""
    expected = """assert stuff == set("A B ")"""
    _test_merge_changes(base, current, other, expected)


def test_fun_becomes_empty():
    base = """
def fun():
    # comment
    pass
    more_stuff
"""
    current = """
def fun():
    more_stuff
"""
    other = """
def fun():
    # comment
    pass
"""
    expected = """
"""
    _test_merge_changes(base, current, other, expected)
