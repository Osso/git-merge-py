from redbaron import RedBaron

from gitmergepy.context import (AfterContext,
                                BeforeContext)
from gitmergepy.matcher import find_el


def test_find_el_at_the_end():
    tree = RedBaron("\n    call\n\n")
    context = AfterContext([None])
    el_to_remove = RedBaron("\n")[0]
    assert find_el(tree, el_to_remove, context) is tree.node_list[-1]


def test_find_el_at_the_beginning():
    tree = RedBaron("\n    call\n\n")
    context = BeforeContext([None])
    el_to_remove = RedBaron("\n    ")[0]
    assert find_el(tree, el_to_remove, context) is tree.node_list[0]


def test_find_el_at_the_beginning_2():
    tree = RedBaron("\n    call\n\n")
    context = BeforeContext([tree.node_list[0], None])
    el_to_remove = RedBaron("call")[0]
    assert find_el(tree, el_to_remove, context) is tree.node_list[1]


def test_find_el_middle():
    tree = RedBaron("\ncall\ncall2\n")
    context = BeforeContext([tree.node_list[2], tree.node_list[1]])
    el_to_remove = RedBaron("call2")[0]
    assert find_el(tree, el_to_remove, context) is tree.node_list[3]


def test_find_el_smaller_context():
    tree = RedBaron("\ncall1\ncall2\n")
    call1 = tree.node_list[1]
    call2_indent = tree.node_list[2]
    call2 = tree.node_list[3]
    context = BeforeContext([call2_indent, call1])
    del tree.node_list[2]
    assert find_el(tree, call2, context) is call2
