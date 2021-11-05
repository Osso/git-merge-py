from redbaron import (RedBaron,
                      node,
                      nodes)

from gitmergepy.context import (AfterContext,
                                BeforeContext)
from gitmergepy.matcher import (code_block_similarity,
                                find_el,
                                find_el_exact_match_with_context)


def test_find_el_at_the_end():
    tree = RedBaron("\n    call\n")
    context = AfterContext([None])
    el_to_remove = node("call")
    assert find_el_exact_match_with_context(tree, el_to_remove, context) is tree[0]
    assert find_el(tree, el_to_remove, context) is tree[0]


def test_find_el_at_the_end_empty_line():
    tree = RedBaron("\n    call\n\n")
    context = AfterContext([nodes.EmptyLineNode(), None])
    el_to_remove = node("call")
    assert find_el_exact_match_with_context(tree, el_to_remove, context) is tree[0]
    assert find_el(tree, el_to_remove, context) is tree[0]


def test_find_el_at_the_end_no_match():
    tree = RedBaron("\n    call\n\n")
    context = AfterContext([None])
    el_to_remove = node("call")
    assert find_el_exact_match_with_context(tree, el_to_remove, context) is None


def test_find_el_at_the_beginning():
    tree = RedBaron("\n    call\n\n")
    context = BeforeContext([None])
    el_to_remove = node("call")
    assert find_el_exact_match_with_context(tree, el_to_remove, context) is tree[0]
    assert find_el(tree, el_to_remove, context) is tree[0]


def test_find_el_middle():
    tree = RedBaron("\ncall\ncall2\n")
    context = BeforeContext([tree[0]])
    el_to_remove = node("call2")
    assert find_el_exact_match_with_context(tree, el_to_remove, context) is tree[1]
    assert find_el(tree, el_to_remove, context) is tree[1]


def test_code_block_similarity():
    node1 = node("class A: a()")
    node2 = node("class B: a()")
    assert code_block_similarity(node1, node2) == 1
