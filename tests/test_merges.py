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
 def populate_amazon_table_for_extract(self):
    _, to_dt = self.compute_dates_for_extract()
    p1, p3, p4, p5, p6, p10 = "AMAZON_PRIME", "1", "AMAZON_M", "PAYANT", "SFR", "AMZ1|PRM1"
    # MSISDN_GOOD_MSISDN = "0617180391"
    with sql_session() as session:
        self.set_main_loop()
        kpsa_create(service_type="SVA68", msisdn=MSISDN_GOOD_MSISDN, p1=p1, p3=p3, p4=p4, p5=p5, p6=p6, p10=p10)
        self._processoro.process_pending_commands(session=session)
        user = get_user_object(session=session, msisdn=MSISDN_GOOD_MSISDN)
"""
    current = """
def populate_amazon_table_for_extract(self):
    _, to_dt = self.compute_dates_for_extract()
    p1, p3, p4, p5, p6, p10 = "AMAZON_PRIME", "1", "AMAZON_M", "PAYANT", "SFR", "AMZ1|PRM1"
    proc = ProcessingServiceOrian()
    amazon = AmazonProvisioningMobile()
    proc.register_service(amazon)
    # MSISDN_GOOD_MSISDN = "0617180391"
    with sql_session() as session:
        # self.set_main_loop()
        kpsa_create(service_type="SVA68", msisdn=MSISDN_GOOD_MSISDN, p1=p1, p3=p3, p4=p4, p5=p5, p6=p6, p10=p10)
        proc.process_pending_commands(session=session)
        user = get_user_object(session=session, msisdn=MSISDN_GOOD_MSISDN)
"""
    other = """
 def populate_amazon_table_for_extract(self):
    _, to_dt = self.compute_dates_for_extract()
    p1, p3, p4, p5, p6, p10 = "AMAZON_PRIME", "1", "AMAZON_M", "PAYANT", "SFR", "AMZ1|PRM1"
    with sql_session() as session:
        # MSISDN_GOOD_MSISDN = "0617180391" ==> CR + ACTIVATE
        self.set_main_loop()
        kpsa_create(service_type="SVA68", msisdn=MSISDN_GOOD_MSISDN, p1=p1, p3=p3, p4=p4, p5=p5, p6=p6, p10=p10)
        self._main_loop(session=session)
        user = get_user_object(session=session, msisdn=MSISDN_GOOD_MSISDN)
"""
    expected = """
def populate_amazon_table_for_extract(self):
    _, to_dt = self.compute_dates_for_extract()
    p1, p3, p4, p5, p6, p10 = "AMAZON_PRIME", "1", "AMAZON_M", "PAYANT", "SFR", "AMZ1|PRM1"
    proc = ProcessingServiceOrian()
    amazon = AmazonProvisioningMobile()
    proc.register_service(amazon)
    # MSISDN_GOOD_MSISDN = "0617180391"
    with sql_session() as session:
        # self.set_main_loop()
        kpsa_create(service_type="SVA68", msisdn=MSISDN_GOOD_MSISDN, p1=p1, p3=p3, p4=p4, p5=p5, p6=p6, p10=p10)
        proc.process_pending_commands(session=session)
        user = get_user_object(session=session, msisdn=MSISDN_GOOD_MSISDN)
"""
    _test_merge_changes(base, current, other, expected)
