import logging

from redbaron import RedBaron, nodes

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
# Conflict: reason context not found
# <AddEls to_add="# added elements" context='None|# context'>
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
# Conflict: reason el not found
# <ChangeEl el="if cond:" context='None'> changes=
# .<ChangeValue el="if cond:" context='no context'> changes=
# ..<ChangeEl el="if cond:" context='None'> changes=
# ...<AddEls to_add="# added elements" context='None'>
# ...<SameEl el="pass">
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


# =============================================================================
# Both branches modify the same element differently
# =============================================================================


def test_both_modify_function_body():
    """Both branches change the same function body differently."""
    base = """
def fun():
    original()
"""
    current = """
def fun():
    changed_by_current()
"""
    other = """
def fun():
    changed_by_other()
"""
    # Both changes are applied (current's addition + other's existing)
    expected = """
def fun():
    changed_by_current()
    changed_by_other()
"""
    _test_merge_changes(base, current, other, expected)


def test_both_modify_same_line():
    """Both branches modify the same comment line differently."""
    base = """
# original line
"""
    current = """
# modified by current
"""
    other = """
# modified by other
"""
    # Both lines are kept
    expected = """
# modified by current
# modified by other
"""
    _test_merge_changes(base, current, other, expected)


def test_both_modify_call_arg():
    """Both branches modify the same call argument differently."""
    base = """
fun(original_arg)
"""
    current = """
fun(current_arg)
"""
    other = """
fun(other_arg)
"""
    # Both arguments are merged
    expected = """
fun(current_arg, other_arg)
"""
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# Conflicting renames
# =============================================================================


def test_conflicting_function_renames():
    """Both branches rename the same function to different names."""
    base = """
def original():
    body()
"""
    current = """
def renamed_by_current():
    body()
"""
    other = """
def renamed_by_other():
    body()
"""
    # Current's rename wins
    expected = """
def renamed_by_current():
    body()
"""
    _test_merge_changes(base, current, other, expected)


def test_conflicting_class_renames():
    """Both branches rename the same class differently."""
    base = """
class Original:
    pass
"""
    current = """
class RenamedByCurrent:
    pass
"""
    other = """
class RenamedByOther:
    pass
"""
    expected = """
class RenamedByCurrent:
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_conflicting_variable_renames():
    """Both branches rename a variable differently."""
    base = """
original = 1
"""
    current = """
renamed_current = 1
"""
    other = """
renamed_other = 1
"""
    # Both assignments are kept
    expected = """
renamed_current = 1
renamed_other = 1
"""
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# Delete vs modify conflicts
# =============================================================================


def test_delete_vs_modify_function():
    """One branch deletes function, other modifies it."""
    base = """
def anchor():
    pass

def target():
    original()

def after():
    pass
"""
    current = """
def anchor():
    pass

def target():
    modified_by_current()

def after():
    pass
"""
    other = """
def anchor():
    pass

def after():
    pass
"""
    # Current's modification should be applied, but target is deleted in other
    # This should result in a conflict or the modification being dropped
    expected = """
def anchor():
    pass

def after():
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_delete_vs_modify_comment():
    """One branch deletes comment, other modifies it."""
    base = """
# anchor
# target
# after
"""
    current = """
# anchor
# target modified
# after
"""
    other = """
# anchor
# after
"""
    # The modification is still applied even though other deleted the target
    expected = """
# anchor
# target modified
# after
"""
    _test_merge_changes(base, current, other, expected)


def test_modify_vs_delete_import():
    """One branch modifies import, other removes it entirely."""
    base = """
from module import fun1, fun2
"""
    current = """
from module import fun1, fun2, fun3
"""
    other = """
"""
    # Import was deleted in other, current added fun3
    expected = """
from module import fun3
"""
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# Both add at same location
# =============================================================================


def test_both_add_function_after_anchor():
    """Both branches add different functions after the same anchor."""
    base = """
def anchor():
    pass
"""
    current = """
def anchor():
    pass

def added_by_current():
    pass
"""
    other = """
def anchor():
    pass

def added_by_other():
    pass
"""
    # Both additions should be preserved
    expected = """
def anchor():
    pass

def added_by_current():
    pass

def added_by_other():
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_both_add_import_to_same_module():
    """Both branches add different imports from same module."""
    base = """
from module import fun1
"""
    current = """
from module import fun1, added_by_current
"""
    other = """
from module import fun1, added_by_other
"""
    # Both imports are merged (alphabetically sorted)
    expected = """
from module import added_by_current, added_by_other, fun1
"""
    _test_merge_changes(base, current, other, expected)


def test_both_add_comment_same_location():
    """Both branches add different comments at the same location."""
    base = """
# anchor
# after
"""
    current = """
# anchor
# added by current
# after
"""
    other = """
# anchor
# added by other
# after
"""
    expected = """
# anchor
# added by current
# added by other
# after
"""
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# Conflicting decorator changes
# =============================================================================


def test_both_add_different_decorators():
    """Both branches add different decorators to same function."""
    base = """
def fun():
    pass
"""
    current = """
@decorator_from_current
def fun():
    pass
"""
    other = """
@decorator_from_other
def fun():
    pass
"""
    # Both decorators should be applied
    expected = """
@decorator_from_current
@decorator_from_other
def fun():
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_both_modify_decorator_args():
    """Both branches modify the same decorator's arguments."""
    base = """
@decorator(original_arg)
def fun():
    pass
"""
    current = """
@decorator(current_arg)
def fun():
    pass
"""
    other = """
@decorator(other_arg)
def fun():
    pass
"""
    # Both arguments are merged
    expected = """
@decorator(current_arg, other_arg)
def fun():
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_one_removes_one_adds_decorator():
    """One branch removes decorator, other adds new one."""
    base = """
@original_decorator
def fun():
    pass
"""
    current = """
@original_decorator
@new_decorator
def fun():
    pass
"""
    other = """
def fun():
    pass
"""
    # Original removed in other, current added new
    expected = """
@new_decorator
def fun():
    pass
"""
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# Conflicting class inheritance
# =============================================================================


def test_conflicting_base_class():
    """Both branches change the base class differently."""
    base = """
class Child(OriginalBase):
    pass
"""
    current = """
class Child(CurrentBase):
    pass
"""
    other = """
class Child(OtherBase):
    pass
"""
    # Both base classes are kept
    expected = """
class Child(CurrentBase, OtherBase):
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_both_add_different_base_classes():
    """Both branches add different additional base classes."""
    base = """
class Child(Base):
    pass
"""
    current = """
class Child(Base, MixinA):
    pass
"""
    other = """
class Child(Base, MixinB):
    pass
"""
    # Both mixins are added (MixinA appended after existing bases)
    expected = """
class Child(Base, MixinB, MixinA):
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_one_removes_one_changes_base():
    """One removes base class, other changes it."""
    base = """
class Child(Base):
    pass
"""
    current = """
class Child(NewBase):
    pass
"""
    other = """
class Child:
    pass
"""
    # NewBase is added even though other removed the base class
    expected = """
class Child(NewBase):
    pass
"""
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# Conflicting default argument values
# =============================================================================


def test_conflicting_default_values():
    """Both branches change the same default argument value."""
    base = """
def fun(arg=1):
    pass
"""
    current = """
def fun(arg=2):
    pass
"""
    other = """
def fun(arg=3):
    pass
"""
    expected = """
def fun(arg=2):
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_both_add_different_defaults():
    """Both branches add default values to different args."""
    base = """
def fun(arg1, arg2):
    pass
"""
    current = """
def fun(arg1=1, arg2):
    pass
"""
    other = """
def fun(arg1, arg2=2):
    pass
"""
    expected = """
def fun(arg1=1, arg2=2):
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_one_adds_one_removes_default():
    """One adds default, other removes existing default."""
    base = """
def fun(arg1, arg2=2):
    pass
"""
    current = """
def fun(arg1=1, arg2=2):
    pass
"""
    other = """
def fun(arg1, arg2):
    pass
"""
    expected = """
def fun(arg1=1, arg2):
    pass
"""
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# Type annotation conflicts
# =============================================================================


def test_conflicting_type_annotations():
    """Both branches add different type annotations to same argument."""
    base = """
def fun(arg):
    pass
"""
    current = """
def fun(arg: int):
    pass
"""
    other = """
def fun(arg: str):
    pass
"""
    expected = """
def fun(arg: int):
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_conflicting_return_annotations():
    """Both branches add different return type annotations."""
    base = """
def fun():
    pass
"""
    current = """
def fun() -> int:
    pass
"""
    other = """
def fun() -> str:
    pass
"""
    # Other's annotation is kept (str), current's annotation (int) not applied
    expected = """
def fun() -> str:
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_one_adds_annotation_other_modifies_body():
    """One adds type annotation, other modifies function body."""
    base = """
def fun(arg):
    original()
"""
    current = """
def fun(arg: int):
    original()
"""
    other = """
def fun(arg):
    modified()
"""
    expected = """
def fun(arg: int):
    modified()
"""
    _test_merge_changes(base, current, other, expected)


def test_both_add_different_annotations_different_args():
    """Both branches annotate different arguments."""
    base = """
def fun(arg1, arg2):
    pass
"""
    current = """
def fun(arg1: int, arg2):
    pass
"""
    other = """
def fun(arg1, arg2: str):
    pass
"""
    expected = """
def fun(arg1: int, arg2: str):
    pass
"""
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# Async/await conflicts
# =============================================================================


def test_make_async_vs_modify_body():
    """One makes function async, other modifies body."""
    base = """
def fun():
    original()
"""
    current = """
async def fun():
    original()
"""
    other = """
def fun():
    modified()
"""
    # Async IS added, and body modification is applied
    expected = """
async def fun():
    modified()
"""
    _test_merge_changes(base, current, other, expected)


def test_both_add_await_differently():
    """Both branches add await to different calls."""
    base = """
async def fun():
    call1()
    call2()
"""
    current = """
async def fun():
    await call1()
    call2()
"""
    other = """
async def fun():
    call1()
    await call2()
"""
    expected = """
async def fun():
    await call1()
    await call2()
"""
    _test_merge_changes(base, current, other, expected)


def test_remove_async_vs_modify():
    """One removes async, other modifies body."""
    base = """
async def fun():
    await original()
"""
    current = """
def fun():
    original()
"""
    other = """
async def fun():
    await modified()
"""
    # Async is removed, body changes from current applied
    # Note: This may produce invalid Python (await in non-async function)
    # if other's changes include await expressions
    expected = """
def fun():
    original()
    await modified()
"""
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# Lambda and comprehension conflicts
# =============================================================================


def test_conflicting_lambda_body():
    """Both branches modify the same lambda body differently."""
    base = """
f = lambda x: x
"""
    current = """
f = lambda x: x + 1
"""
    other = """
f = lambda x: x * 2
"""
    # Conflict marker is generated for conflicting lambda changes
    expected = """
# <<<<<<<<<<
# Conflict: reason Different from old value 'lambda x: x'
# <Replace new_value='lambda x: x + 1'>
# lambda x: x * 2
# >>>>>>>>>>
f = lambda x: x * 2
"""
    _test_merge_changes(base, current, other, expected)


def test_conflicting_lambda_args():
    """Both branches modify lambda arguments differently."""
    base = """
f = lambda x: x
"""
    current = """
f = lambda x, y: x
"""
    other = """
f = lambda x, z: x
"""
    # Conflict marker is generated for lambda argument changes
    expected = """
# <<<<<<<<<<
# Conflict: reason Different from old value 'lambda x: x'
# <Replace new_value='lambda x, y: x'>
# lambda x, z: x
# >>>>>>>>>>
f = lambda x, z: x
"""
    _test_merge_changes(base, current, other, expected)


def test_conflicting_list_comprehension_filter():
    """Both branches add different filters to comprehension."""
    base = """
result = [x for x in items]
"""
    current = """
result = [x for x in items if x > 0]
"""
    other = """
result = [x for x in items if x < 100]
"""
    # Conflict marker for comprehension filter changes
    expected = """
# <<<<<<<<<<
# Conflict: reason Different from old value '[x for x in items]'
# <Replace new_value='[x for x in items if x > 0]'>
# [x for x in items if x < 100]
# >>>>>>>>>>
result = [x for x in items if x < 100]
"""
    _test_merge_changes(base, current, other, expected)


def test_conflicting_list_comprehension_expr():
    """Both branches modify the comprehension expression differently."""
    base = """
result = [x for x in items]
"""
    current = """
result = [x + 1 for x in items]
"""
    other = """
result = [x * 2 for x in items]
"""
    # Conflict marker for comprehension expression changes
    expected = """
# <<<<<<<<<<
# Conflict: reason Different from old value '[x for x in items]'
# <Replace new_value='[x + 1 for x in items]'>
# [x * 2 for x in items]
# >>>>>>>>>>
result = [x * 2 for x in items]
"""
    _test_merge_changes(base, current, other, expected)


def test_conflicting_dict_comprehension():
    """Both branches modify dict comprehension differently."""
    base = """
result = {k: v for k, v in items}
"""
    current = """
result = {k: v + 1 for k, v in items}
"""
    other = """
result = {k: v * 2 for k, v in items}
"""
    # Conflict marker for dict comprehension changes
    expected = """
# <<<<<<<<<<
# Conflict: reason Different from old value '{k: v for k, v in items}'
# <Replace new_value='{k: v + 1 for k, v in items}'>
# {k: v * 2 for k, v in items}
# >>>>>>>>>>
result = {k: v * 2 for k, v in items}
"""
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# Docstring conflicts
# =============================================================================


def test_conflicting_docstrings():
    """Both branches modify the same docstring differently."""
    base = '''
def fun():
    """Original docstring."""
    pass
'''
    current = '''
def fun():
    """Modified by current."""
    pass
'''
    other = '''
def fun():
    """Modified by other."""
    pass
'''
    # Both docstrings are kept
    expected = '''
def fun():
    """Modified by current."""
    """Modified by other."""
    pass
'''
    _test_merge_changes(base, current, other, expected)


def test_add_vs_modify_docstring():
    """One adds docstring, other modifies function body."""
    base = '''
def fun():
    original()
'''
    current = '''
def fun():
    """New docstring."""
    original()
'''
    other = '''
def fun():
    modified()
'''
    expected = '''
def fun():
    """New docstring."""
    modified()
'''
    _test_merge_changes(base, current, other, expected)


def test_remove_vs_modify_docstring():
    """One removes docstring, other modifies it."""
    base = '''
def fun():
    """Original docstring."""
    pass
'''
    current = '''
def fun():
    pass
'''
    other = '''
def fun():
    """Changed docstring."""
    pass
'''
    # The removal doesn't happen, other's docstring is kept
    expected = '''
def fun():
    """Changed docstring."""
    pass
'''
    _test_merge_changes(base, current, other, expected)


def test_conflicting_class_docstrings():
    """Both branches modify class docstring differently."""
    base = '''
class C:
    """Original class doc."""
    pass
'''
    current = '''
class C:
    """Modified by current."""
    pass
'''
    other = '''
class C:
    """Modified by other."""
    pass
'''
    # Both docstrings are kept
    expected = '''
class C:
    """Modified by current."""
    """Modified by other."""
    pass
'''
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# F-string conflicts
# =============================================================================


def test_conflicting_fstring_text():
    """Both branches modify the text part of f-string differently."""
    base = """
msg = f"Hello {name}"
"""
    current = """
msg = f"Hi {name}"
"""
    other = """
msg = f"Greetings {name}"
"""
    # Conflict marker for f-string changes
    expected = """
# <<<<<<<<<<
# Conflict: reason Different from old value 'f"Hello {name}"'
# <Replace new_value='f"Hi {name}"'>
# f"Greetings {name}"
# >>>>>>>>>>
msg = f"Greetings {name}"
"""
    _test_merge_changes(base, current, other, expected)


def test_conflicting_fstring_expr():
    """Both branches modify the expression in f-string differently."""
    base = """
msg = f"Value: {value}"
"""
    current = """
msg = f"Value: {value + 1}"
"""
    other = """
msg = f"Value: {value * 2}"
"""
    # Conflict marker for f-string expression changes
    expected = """
# <<<<<<<<<<
# Conflict: reason Different from old value 'f"Value: {value}"'
# <Replace new_value='f"Value: {value + 1}"'>
# f"Value: {value * 2}"
# >>>>>>>>>>
msg = f"Value: {value * 2}"
"""
    _test_merge_changes(base, current, other, expected)


def test_conflicting_fstring_variable():
    """Both branches change which variable is used in f-string."""
    base = """
msg = f"Hello {name}"
"""
    current = """
msg = f"Hello {user}"
"""
    other = """
msg = f"Hello {person}"
"""
    # Conflict marker for f-string variable changes
    expected = """
# <<<<<<<<<<
# Conflict: reason Different from old value 'f"Hello {name}"'
# <Replace new_value='f"Hello {user}"'>
# f"Hello {person}"
# >>>>>>>>>>
msg = f"Hello {person}"
"""
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# Exception handling conflicts
# =============================================================================


def test_conflicting_except_type():
    """Both branches change exception type differently."""
    base = """
try:
    pass
except ValueError:
    pass
"""
    current = """
try:
    pass
except TypeError:
    pass
"""
    other = """
try:
    pass
except KeyError:
    pass
"""
    # Current's change to TypeError is applied to other
    expected = """
try:
    pass
except TypeError:
    pass
"""
    _test_merge_changes(base, current, other, expected)


def test_one_adds_exception_alias():
    """One adds exception alias, other modifies handler body."""
    base = """
try:
    pass
except ValueError:
    original()
"""
    current = """
try:
    pass
except ValueError as e:
    original()
"""
    other = """
try:
    pass
except ValueError:
    modified()
"""
    # The alias IS added, and other's body modification is applied
    expected = """
try:
    pass
except ValueError as e:
    modified()
"""
    _test_merge_changes(base, current, other, expected)


def test_one_adds_except_other_modifies():
    """One adds new except clause, other modifies existing."""
    base = """
try:
    pass
except ValueError:
    original()
"""
    current = """
try:
    pass
except ValueError:
    original()
except TypeError:
    handle_type_error()
"""
    other = """
try:
    pass
except ValueError:
    modified()
"""
    # The new except clause IS added (additive change merged)
    expected = """
try:
    pass
except ValueError:
    modified()
except TypeError:
    handle_type_error()
"""
    _test_merge_changes(base, current, other, expected)


def test_conflicting_exception_handlers():
    """Both branches modify the same exception handler differently."""
    base = """
try:
    risky()
except Exception:
    log_error()
"""
    current = """
try:
    risky()
except Exception:
    log_error()
    retry()
"""
    other = """
try:
    risky()
except Exception:
    log_error()
    raise
"""
    # Both additions are made
    expected = """
try:
    risky()
except Exception:
    log_error()
    retry()
    raise
"""
    _test_merge_changes(base, current, other, expected)


def test_add_finally_vs_modify_except():
    """One adds finally, other modifies except body."""
    base = """
try:
    pass
except:
    original()
"""
    current = """
try:
    pass
except:
    original()
finally:
    cleanup()
"""
    other = """
try:
    pass
except:
    modified()
"""
    # The finally IS added (additive change merged)
    expected = """
try:
    pass
except:
    modified()
finally:
    cleanup()
"""
    _test_merge_changes(base, current, other, expected)


def test_remove_except_clause():
    """One removes an except clause, other modifies try body."""
    base = """
try:
    original()
except ValueError:
    handle_value()
except TypeError:
    handle_type()
"""
    current = """
try:
    original()
except ValueError:
    handle_value()
"""
    other = """
try:
    modified()
except ValueError:
    handle_value()
except TypeError:
    handle_type()
"""
    # The except TypeError should be removed
    expected = """
try:
    modified()
except ValueError:
    handle_value()
"""
    _test_merge_changes(base, current, other, expected)


def test_change_exception_type():
    """One changes the exception type."""
    base = """
try:
    pass
except ValueError:
    handle()
"""
    current = """
try:
    pass
except TypeError:
    handle()
"""
    other = """
try:
    pass
except ValueError:
    handle()
"""
    # The exception type should change to TypeError
    expected = """
try:
    pass
except TypeError:
    handle()
"""
    _test_merge_changes(base, current, other, expected)


def test_add_exception_alias():
    """One adds an exception alias (as e)."""
    base = """
try:
    pass
except ValueError:
    handle()
"""
    current = """
try:
    pass
except ValueError as e:
    handle()
"""
    other = """
try:
    pass
except ValueError:
    handle()
"""
    # The alias should be added
    expected = """
try:
    pass
except ValueError as e:
    handle()
"""
    _test_merge_changes(base, current, other, expected)


def test_remove_exception_alias():
    """One removes an exception alias."""
    base = """
try:
    pass
except ValueError as e:
    handle(e)
"""
    current = """
try:
    pass
except ValueError:
    handle(e)
"""
    other = """
try:
    pass
except ValueError as e:
    handle(e)
"""
    # The alias should be removed
    expected = """
try:
    pass
except ValueError:
    handle(e)
"""
    _test_merge_changes(base, current, other, expected)


def test_remove_finally_block():
    """One removes the finally block."""
    base = """
try:
    pass
except:
    handle()
finally:
    cleanup()
"""
    current = """
try:
    pass
except:
    handle()
"""
    other = """
try:
    pass
except:
    handle()
finally:
    cleanup()
"""
    # The finally should be removed
    expected = """
try:
    pass
except:
    handle()
"""
    _test_merge_changes(base, current, other, expected)


def test_modify_finally_block():
    """One modifies the finally block body."""
    base = """
try:
    pass
except:
    handle()
finally:
    original()
"""
    current = """
try:
    pass
except:
    handle()
finally:
    modified()
"""
    other = """
try:
    pass
except:
    handle()
finally:
    original()
"""
    # The finally body should be modified
    expected = """
try:
    pass
except:
    handle()
finally:
    modified()
"""
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# Nested structure conflicts
# =============================================================================


def test_nested_if_conflict():
    """Both modify deeply nested if body differently."""
    base = """
if outer:
    if inner:
        original()
"""
    current = """
if outer:
    if inner:
        changed_by_current()
"""
    other = """
if outer:
    if inner:
        changed_by_other()
"""
    # Both changes are added
    expected = """
if outer:
    if inner:
        changed_by_current()
        changed_by_other()
"""
    _test_merge_changes(base, current, other, expected)


def test_nested_with_conflict():
    """Both modify nested with statement body differently."""
    base = """
with outer():
    with inner():
        original()
"""
    current = """
with outer():
    with inner():
        changed_by_current()
"""
    other = """
with outer():
    with inner():
        changed_by_other()
"""
    # Both changes are added
    expected = """
with outer():
    with inner():
        changed_by_current()
        changed_by_other()
"""
    _test_merge_changes(base, current, other, expected)


def test_nested_class_method_conflict():
    """Both modify method in nested class differently."""
    base = """
class Outer:
    class Inner:
        def method(self):
            original()
"""
    current = """
class Outer:
    class Inner:
        def method(self):
            changed_by_current()
"""
    other = """
class Outer:
    class Inner:
        def method(self):
            changed_by_other()
"""
    # Both changes are added
    expected = """
class Outer:
    class Inner:
        def method(self):
            changed_by_current()
            changed_by_other()
"""
    _test_merge_changes(base, current, other, expected)


def test_nested_for_in_function():
    """Both modify nested for loop body differently."""
    base = """
def fun():
    for item in items:
        original(item)
"""
    current = """
def fun():
    for item in items:
        current_change(item)
"""
    other = """
def fun():
    for item in items:
        other_change(item)
"""
    # Both changes are added
    expected = """
def fun():
    for item in items:
        current_change(item)
        other_change(item)
"""
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# Global/nonlocal conflicts
# =============================================================================


def test_add_global_vs_modify():
    """One adds global declaration, other modifies variable usage."""
    base = """
def fun():
    x = 1
"""
    current = """
def fun():
    global x
    x = 1
"""
    other = """
def fun():
    x = 2
"""
    expected = """
def fun():
    global x
    x = 2
"""
    _test_merge_changes(base, current, other, expected)


def test_add_nonlocal_vs_modify():
    """One adds nonlocal declaration, other modifies variable."""
    base = """
def outer():
    x = 0
    def inner():
        x = 1
"""
    current = """
def outer():
    x = 0
    def inner():
        nonlocal x
        x = 1
"""
    other = """
def outer():
    x = 0
    def inner():
        x = 2
"""
    expected = """
def outer():
    x = 0
    def inner():
        nonlocal x
        x = 2
"""
    _test_merge_changes(base, current, other, expected)


def test_conflicting_global_lists():
    """Both branches add different globals."""
    base = """
def fun():
    pass
"""
    current = """
def fun():
    global a
    pass
"""
    other = """
def fun():
    global b
    pass
"""
    expected = """
def fun():
    global a
    global b
    pass
"""
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# Property/setter conflicts
# =============================================================================


def test_conflicting_property_getter():
    """Both branches modify property getter differently."""
    base = """
class C:
    @property
    def value(self):
        return self._original
"""
    current = """
class C:
    @property
    def value(self):
        return self._current
"""
    other = """
class C:
    @property
    def value(self):
        return self._other
"""
    # Conflict marker for property name changes
    expected = """
class C:
    @property
    def value(self):
        # <<<<<<<<<<
    # Conflict: reason Different from old value '_original'
    # <Replace new_value='_current'>
    # _other
    # >>>>>>>>>>
        return self._other
"""
    _test_merge_changes(base, current, other, expected)


def test_add_setter_vs_modify_getter():
    """One adds setter, other modifies getter."""
    base = """
class C:
    @property
    def value(self):
        return self._value
"""
    current = """
class C:
    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = v
"""
    other = """
class C:
    @property
    def value(self):
        return self._modified_value
"""
    expected = """
class C:
    @property
    def value(self):
        return self._modified_value

    @value.setter
    def value(self, v):
        self._value = v
"""
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# Multiline string conflicts
# =============================================================================


def test_conflicting_multiline_string():
    """Both branches modify multiline string differently."""
    base = '''
text = """
line 1
line 2
line 3
"""
'''
    current = '''
text = """
line 1 modified
line 2
line 3
"""
'''
    other = '''
text = """
line 1
line 2 modified
line 3
"""
'''
    expected = '''
text = """
line 1 modified
line 2 modified
line 3
"""
'''
    _test_merge_changes(base, current, other, expected)


# =============================================================================
# Tuple unpacking conflicts
# =============================================================================


def test_conflicting_tuple_unpack():
    """Both branches modify tuple unpacking differently."""
    base = """
a, b = get_values()
"""
    current = """
a, b, c = get_values()
"""
    other = """
x, y = get_values()
"""
    # Both assignments are kept
    expected = """
a, b, c = get_values()
x, y = get_values()
"""
    _test_merge_changes(base, current, other, expected)


def test_conflicting_tuple_rhs():
    """Both branches modify the right-hand side of tuple assignment."""
    base = """
a, b = 1, 2
"""
    current = """
a, b = 10, 2
"""
    other = """
a, b = 1, 20
"""
    expected = """
a, b = 10, 20
"""
    _test_merge_changes(base, current, other, expected)
