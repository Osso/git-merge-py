from redbaron import RedBaron, node, nodes

from gitmergepy.tools import (
    apply_diff_to_list,
    changed_in_list,
    diff_list,
    empty_lines,
    get_args_names,
    id_from_arg,
    id_from_el,
    same_el,
    short_context,
    short_display_el,
    short_display_list,
)


def test_id_from_fun():
    def_node = node("def a():\n   pass")
    assert id_from_el(def_node) == "a"


def test_id_from_class():
    def_node = node("class A:\n   pass")
    assert id_from_el(def_node) == "A"


def test_id_from_el_import():
    """id_from_el should return module name for imports."""
    import_node = RedBaron("from os import path")[0]
    assert id_from_el(import_node) == "os"


def test_id_from_el_assignment():
    """id_from_el for assignment returns the full dumps."""
    assign_node = node("x = 1")
    result = id_from_el(assign_node)
    assert "x" in result


def test_id_from_el_decorator():
    """id_from_el should return decorator name."""
    func = node("@staticmethod\ndef foo(): pass")
    decorator = func.decorators[0]
    assert id_from_el(decorator) == "staticmethod"


def test_id_from_arg_simple():
    """id_from_arg should return argument name."""
    func = node("def foo(x, y, z): pass")
    args = list(func.arguments)
    assert id_from_arg(args[0]) == "x"
    assert id_from_arg(args[1]) == "y"
    assert id_from_arg(args[2]) == "z"


def test_id_from_arg_with_default():
    """id_from_arg should handle arguments with defaults."""
    func = node("def foo(x=1, y=2): pass")
    args = list(func.arguments)
    result_x = id_from_arg(args[0])
    result_y = id_from_arg(args[1])
    assert "x" in result_x
    assert "y" in result_y


def test_short_display_el():
    """short_display_el should format elements nicely."""
    short_node = node("x = 1")
    result = short_display_el(short_node)
    assert "x = 1" in result


def test_short_display_el_none():
    """short_display_el should handle None."""
    assert short_display_el(None) == "None"


def test_short_display_list():
    """short_display_list should format list of nodes."""
    code = RedBaron("x = 1\ny = 2")
    result = short_display_list(list(code))
    assert "x = 1" in result
    assert "y = 2" in result


def test_short_context():
    """short_context should format context nicely."""
    from gitmergepy.context import BeforeContext
    ctx = BeforeContext([None])
    result = short_context(ctx)
    assert "None" in result


def test_same_el_identical():
    """same_el should return True for identical elements."""
    left = node("x = 1")
    right = node("x = 1")
    assert same_el(left, right) is True


def test_same_el_different():
    """same_el should return False for different elements."""
    left = node("x = 1")
    right = node("x = 2")
    assert same_el(left, right) is False


def test_same_el_none():
    """same_el should handle None values."""
    left = node("x = 1")
    assert same_el(None, None) is True
    assert same_el(left, None) is False
    assert same_el(None, left) is False


def test_same_el_ignores_indentation():
    """same_el should ignore indentation by default."""
    left = node("x = 1")
    # Create indented version by parsing inside a function
    func = node("def foo():\n    x = 1")
    right = func.value[0]
    assert same_el(left, right, discard_indentation=True) is True


def test_empty_lines_true():
    """empty_lines should return True for empty line nodes."""
    els = [nodes.EmptyLineNode(), nodes.EmptyLineNode()]
    assert empty_lines(els) is True


def test_empty_lines_false():
    """empty_lines should return False for non-empty elements."""
    els = [node("x = 1")]
    assert empty_lines(els) is False


def test_empty_lines_mixed():
    """empty_lines should return False for mixed elements."""
    els = [nodes.EmptyLineNode(), node("x = 1")]
    assert empty_lines(els) is False


def test_get_args_names():
    """get_args_names should return list of argument names."""
    func = node("def foo(a, b, c): pass")
    names = get_args_names(func.arguments)
    assert names == ["a", "b", "c"]


def test_get_args_names_with_kwargs():
    """get_args_names should handle *args and **kwargs."""
    func = node("def foo(a, *args, **kwargs): pass")
    names = get_args_names(func.arguments)
    assert "a" in names
    assert "*args" in names
    assert "**kwargs" in names


def test_diff_list_empty():
    """diff_list with identical nodes should produce no changes."""
    code = RedBaron("from foo import a, b, c")
    left = list(code[0].targets)
    right = list(code[0].targets)  # Same elements
    to_add, to_remove = diff_list(left, right)
    assert to_add == []
    assert to_remove == []


def test_diff_list_add():
    """diff_list should detect additions."""
    left_code = RedBaron("from foo import a, b")
    right_code = RedBaron("from foo import a, b, c")
    left = list(left_code[0].targets)
    right = list(right_code[0].targets)
    to_add, to_remove = diff_list(left, right)
    assert len(to_add) == 1
    assert to_add[0].value == "c"
    assert to_remove == []


def test_diff_list_remove():
    """diff_list should detect removals."""
    left_code = RedBaron("from foo import a, b, c")
    right_code = RedBaron("from foo import a, b")
    left = list(left_code[0].targets)
    right = list(right_code[0].targets)
    to_add, to_remove = diff_list(left, right)
    assert to_add == []
    assert len(to_remove) == 1
    assert to_remove[0].value == "c"


def test_changed_in_list_no_change():
    """changed_in_list should return empty when no changes."""
    code = RedBaron("from foo import a, b, c")
    left = list(code[0].targets)
    right = list(code[0].targets)
    changed = changed_in_list(left, right, id_from_el)
    assert changed == []


def test_changed_in_list_detects_reorder():
    """changed_in_list should work with reordered elements."""
    left_code = RedBaron("from foo import a, b")
    right_code = RedBaron("from foo import b, a")  # Reordered
    left = list(left_code[0].targets)
    right = list(right_code[0].targets)
    # With same keys, this shouldn't detect changes
    changed = changed_in_list(left, right, id_from_el)
    # Both have same imports, just reordered
    assert len(changed) == 0


def test_diff_match_patch():
    from diff_match_patch import diff_match_patch

    dmp = diff_match_patch()
    old = """
bacon
eggs
ham
guido
"""
    new = """
python
eggs
ham
guido
"""
    patches = dmp.patch_make(old, new)
    patched, _ = dmp.patch_apply(patches, old)
    assert patched == new
