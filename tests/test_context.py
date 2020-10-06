from redbaron import RedBaron

from gitmergepy.context import (AfterContext,
                                BeforeContext,
                                find_context,
                                match_after_context,
                                match_before_context)


def test_match_after_context():
    tree = RedBaron("# line 1\n# line 2\n# line 3\n")
    line2 = tree[1]
    line3 = tree[2]
    endl = tree.node_list[-1]

    # At then end
    context = AfterContext([line3, endl, None])
    assert not match_after_context(tree, 3, context)
    assert match_after_context(tree, 4, context)
    assert not match_after_context(tree, 5, context)
    assert not match_after_context(tree, 6, context)
    # Pattern found but not at the end
    context = AfterContext([line2, endl, None])
    assert not match_after_context(tree, 2, context)
    # Pattern found
    context = AfterContext([line2, endl])
    assert match_after_context(tree, 2, context)


def test_match_before_context():
    tree = RedBaron("# line 1\n# line 2\n# line 3\n")
    line1 = tree[0]
    line2 = tree[1]
    endl = tree.node_list[-1]

    # At the beginning
    context = BeforeContext([endl, line1, None])
    assert not match_before_context(tree, 1, context)
    assert match_before_context(tree, 2, context)
    assert not match_before_context(tree, 3, context)
    assert not match_before_context(tree, 4, context)
    # Pattern found but not at the beginning
    context = BeforeContext([endl, line2, None])
    assert not match_before_context(tree, 3, context)
    # Pattern found
    context = BeforeContext([endl, line2])
    assert match_before_context(tree, 4, context)


def test_find_context():
    tree = RedBaron("# line 1\n# line 2\n# line 3\n")
    line1 = tree[0]
    line3 = tree[2]
    endl = tree.node_list[-1]
    context = BeforeContext([endl, line1, None])
    assert find_context(tree, context) == 2

    context = AfterContext([line3, endl, None])
    assert find_context(tree, context) == 4
