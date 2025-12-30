from redbaron import RedBaron, node, nodes

from gitmergepy.actions import (
    AddEls,
    ChangeAssignment,
    ChangeEl,
    RemoveEls,
    Replace,
    ReplaceAttr,
)
from gitmergepy.differ import (
    changed_el,
    compare_formatting,
    compute_diff,
    look_ahead,
    simplify_to_add_to_remove,
    simplify_white_lines,
)
from gitmergepy.matcher import same_el_guess


def test_simplify_white_lines():
    diff = [
        AddEls([nodes.EmptyLineNode()], context=[None]),
        RemoveEls([node("stuff")], context=[]),
        RemoveEls([node("stuff")], context=[]),
        RemoveEls([nodes.EmptyLineNode()], context=[]),
    ]
    simplify_white_lines(diff, indent="")
    assert len(diff) == 2


def test_compute_diff_identical():
    """Identical nodes should produce empty diff."""
    left = RedBaron("x = 1")[0]
    right = RedBaron("x = 1")[0]
    diff = compute_diff(left, right)
    assert diff == []


def test_compute_diff_assignment_value_change():
    """Changed assignment value should produce ChangeAssignment action."""
    left = RedBaron("x = 1")[0]
    right = RedBaron("x = 2")[0]
    diff = compute_diff(left, right)
    assert len(diff) == 1
    assert isinstance(diff[0], ChangeAssignment)


def test_compute_diff_type_mismatch():
    """Type mismatch should produce Replace action."""
    left = RedBaron("x = 1")[0]
    right = RedBaron("return 1")[0]
    diff = compute_diff(left, right)
    assert len(diff) == 1
    assert isinstance(diff[0], Replace)


def test_compute_diff_function():
    """Changed function body should produce proper diff."""
    left = RedBaron("def foo(): pass")[0]
    right = RedBaron("def foo(): return 1")[0]
    diff = compute_diff(left, right)
    assert len(diff) > 0


def test_compare_formatting_identical():
    """Identical formatting should produce empty diff."""
    left = RedBaron("x = 1")[0]
    right = RedBaron("x = 1")[0]
    diff = compare_formatting(left, right)
    assert diff == []


def test_compare_formatting_different_spacing():
    """Different formatting should produce ReplaceAttr actions."""
    left = RedBaron("x=1")[0]
    right = RedBaron("x = 1")[0]
    diff = compare_formatting(left, right)
    assert len(diff) > 0
    assert any(isinstance(d, ReplaceAttr) for d in diff)


def test_changed_el():
    """changed_el should detect changes between elements."""
    left = RedBaron("x = 1")[0]
    right = RedBaron("x = 2")[0]
    stack_left = [left]
    diff = changed_el(right, stack_left, indent="", change_class=ChangeEl)
    # Stack should be empty after popping
    assert len(stack_left) == 0
    # Should have a change
    assert len(diff) == 1
    assert isinstance(diff[0], ChangeEl)


def test_changed_el_no_change():
    """Identical elements should produce no changes."""
    left = RedBaron("x = 1")[0]
    right = RedBaron("x = 1")[0]
    stack_left = [left]
    diff = changed_el(right, stack_left, indent="", change_class=ChangeEl)
    assert len(stack_left) == 0
    assert len(diff) == 0


def test_simplify_to_add_to_remove():
    """Should remove matching elements from both lists."""
    a1 = RedBaron("x = 1")[0]
    a2 = RedBaron("x = 1")[0]
    b1 = RedBaron("y = 2")[0]

    to_add = [a1, b1]
    to_remove = [a2]
    simplify_to_add_to_remove(to_add, to_remove)
    # First elements match and should be removed
    assert len(to_add) == 1
    assert to_add[0] is b1
    assert len(to_remove) == 0


def test_simplify_to_add_to_remove_no_match():
    """Non-matching elements should not be removed."""
    a1 = RedBaron("x = 1")[0]
    b1 = RedBaron("y = 2")[0]

    to_add = [a1]
    to_remove = [b1]
    simplify_to_add_to_remove(to_add, to_remove)
    assert len(to_add) == 1
    assert len(to_remove) == 1


def test_look_ahead_finds_function():
    """look_ahead should find matching function in stack."""
    code = RedBaron("def foo(): pass\ndef bar(): pass\ndef baz(): pass")
    stack = list(code)
    target = RedBaron("def bar(): pass")[0]
    result = look_ahead(stack, target, max_ahead=5)
    assert result is not None
    assert result.name == "bar"


def test_look_ahead_not_found():
    """look_ahead should return None if not found."""
    code = RedBaron("def foo(): pass\ndef bar(): pass")
    stack = list(code)
    target = RedBaron("def baz(): pass")[0]
    result = look_ahead(stack, target, max_ahead=5)
    assert result is None


def test_look_ahead_respects_limit():
    """look_ahead should respect max_ahead limit."""
    code = RedBaron("def a(): pass\ndef b(): pass\ndef c(): pass\ndef d(): pass\ndef e(): pass")
    stack = list(code)
    target = RedBaron("def e(): pass")[0]
    # Should not find it with limit of 2
    result = look_ahead(stack, target, max_ahead=2)
    assert result is None


def test_same_el_guess_functions():
    """same_el_guess should match functions by name."""
    left = RedBaron("def foo(): pass")[0]
    right = RedBaron("def foo(): return 1")[0]
    assert same_el_guess(left, right) is True


def test_same_el_guess_different_functions():
    """same_el_guess should not match functions with different names."""
    left = RedBaron("def foo(): pass")[0]
    right = RedBaron("def bar(): pass")[0]
    assert same_el_guess(left, right) is False
