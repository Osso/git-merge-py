from redbaron import (RedBaron,
                      node,
                      nodes)

from gitmergepy.context import (AfterContext,
                                BeforeContext)
from gitmergepy.matcher import (code_block_similarity,
                                find_el,
                                find_import,
                                find_single_el_with_context,
                                same_el_guess)


def test_find_el_at_the_end():
    tree = RedBaron("\n    call\n")
    context = AfterContext([None])
    el_to_remove = node("call")
    assert find_single_el_with_context(tree, el_to_remove, context) is tree[0]
    assert find_el(tree, el_to_remove, context) is tree[0]


def test_find_el_at_the_end_empty_line():
    tree = RedBaron("\n    call\n\n")
    context = AfterContext([nodes.EmptyLineNode(), None])
    el_to_remove = node("call")
    assert find_single_el_with_context(tree, el_to_remove, context) is tree[0]
    assert find_el(tree, el_to_remove, context) is tree[0]


def test_find_el_at_the_end_no_match():
    tree = RedBaron("\n    call\n\n")
    context = AfterContext([None])
    el_to_remove = node("call")
    assert find_single_el_with_context(tree, el_to_remove, context) is None


def test_find_el_at_the_beginning():
    tree = RedBaron("\n    call\n\n")
    context = BeforeContext([None])
    el_to_remove = node("call")
    assert find_single_el_with_context(tree, el_to_remove, context) is tree[0]
    assert find_el(tree, el_to_remove, context) is tree[0]


def test_find_el_middle():
    tree = RedBaron("\ncall\ncall2\n")
    context = BeforeContext([tree[0]])
    el_to_remove = node("call2")
    assert find_single_el_with_context(tree, el_to_remove, context) is tree[1]
    assert find_el(tree, el_to_remove, context) is tree[1]


def test_code_block_similarity():
    node1 = node("class A: a()")
    node2 = node("class B: a()")
    assert code_block_similarity(node1, node2) == 1


def test_code_block_similarity_indentation():
    node1 = node("class A:\n                   a()")
    node2 = node("class B:\n a()")
    assert code_block_similarity(node1, node2) == 1


def test_same_el_guess_call_named_arg():
    node1 = node("fun(arg)")
    node2 = node("fun(arg=arg)")
    assert same_el_guess(node1, node2)


def test_find_import():
    import_node = node("from a import b")
    tree = RedBaron("from a import b")
    assert find_import(tree, import_node)


def test_find_import_2():
    import_node = node("from a import b")
    tree = RedBaron("from a import c, b")
    assert find_import(tree, import_node)


def test_find_import_not():
    import_node = node("from a import b")
    tree = RedBaron("from a import b2")
    assert not find_import(tree, import_node)


def test_find_import_not_2():
    import_node = node("from a import b")
    tree = RedBaron("from a2 import b")
    assert not find_import(tree, import_node)
