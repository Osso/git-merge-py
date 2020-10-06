from redbaron import RedBaron

from gitmergepy.context import (AfterContext,
                                BeforeContext,
                                find_context)


def test_match_after_context():
    tree = RedBaron("# line 1\n# line 2\n# line 3\n")
    line2 = tree[1]
    line3 = tree[2]
    endl = tree.node_list[-1]
    # At then end
    context = AfterContext([None])
    assert not context.match(tree, 5, context)
    assert context.match(tree, 6, context)
    # At then end -2
    context = AfterContext([line3, endl, None])
    assert not context.match(tree, 3, context)
    assert context.match(tree, 4, context)
    assert not context.match(tree, 5, context)
    assert not context.match(tree, 6, context)
    # Pattern found but not at the end
    context = AfterContext([line2, endl, None])
    assert not context.match(tree, 2, context)
    # Pattern found
    context = AfterContext([line2, endl])
    assert context.match(tree, 2, context)


def test_match_before_context():
    tree = RedBaron("# line 1\n# line 2\n# line 3\n")
    line1 = tree[0]
    line2 = tree[1]
    endl = tree.node_list[-1]

    # At the beginning
    context = BeforeContext([None])
    assert context.match(tree, 0, context)
    assert not context.match(tree, 1, context)
    # At the begging +2
    context = BeforeContext([endl, line1, None])
    assert not context.match(tree, 1, context)
    assert context.match(tree, 2, context)
    assert not context.match(tree, 3, context)
    assert not context.match(tree, 4, context)
    # Pattern found but not at the beginning
    context = BeforeContext([endl, line2, None])
    assert not context.match(tree, 3, context)
    # Pattern found
    context = BeforeContext([endl, line2])
    assert context.match(tree, 4, context)


def test_match_el_after_context():
    tree = RedBaron("# line 1\n# line 2\n# line 3\n")
    line2 = tree[1]
    line3 = tree[2]
    endl = tree.node_list[-1]
    # At then end
    context = AfterContext([None])
    assert not context.match_el(tree, tree.node_list[4], context)
    assert context.match_el(tree, tree.node_list[5], context)
    # At then end -2
    context = AfterContext([line3, endl, None])
    assert not context.match_el(tree, tree.node_list[2], context)
    assert context.match_el(tree, tree.node_list[3], context)
    assert not context.match_el(tree, tree.node_list[4], context)
    assert not context.match_el(tree, tree.node_list[5], context)
    # Pattern found but not at the end
    context = AfterContext([line2, endl, None])
    assert not context.match_el(tree, tree.node_list[1], context)
    # Pattern found
    context = AfterContext([line2, endl])
    assert context.match_el(tree, tree.node_list[1], context)


def test_match_el_before_context():
    tree = RedBaron("# line 1\n# line 2\n# line 3\n")
    line1 = tree[0]
    line2 = tree[1]
    endl = tree.node_list[-1]

    # At the beginning
    context = BeforeContext([None])
    assert context.match_el(tree, tree.node_list[0], context)
    assert not context.match_el(tree, tree.node_list[1], context)
    # At the begging +2
    context = BeforeContext([endl, line1, None])
    assert not context.match_el(tree, tree.node_list[1], context)
    assert context.match_el(tree, tree.node_list[2], context)
    assert not context.match_el(tree, tree.node_list[3], context)
    assert not context.match_el(tree, tree.node_list[4], context)
    # Pattern found but not at the beginning
    context = BeforeContext([endl, line2, None])
    assert not context.match_el(tree, tree.node_list[3], context)
    # Pattern found
    context = BeforeContext([endl, line2])
    assert context.match_el(tree, tree.node_list[4], context)


def test_find_context():
    tree = RedBaron("# line 1\n# line 2\n# line 3\n")
    line1 = tree[0]
    line3 = tree[2]
    endl = tree.node_list[-1]

    # At the end
    context = BeforeContext([None])
    assert find_context(tree, context) == 0
    # At the end -2
    context = BeforeContext([endl, line1, None])
    assert find_context(tree, context) == 2

    context = AfterContext([line3, endl, None])
    assert find_context(tree, context) == 4


def test_find_context_decorator():
    tree = RedBaron("""
@decorator1
@decorator3
@decorator2
def fun():
    pass
""")
    fun = tree[1]
    decorator1 = fun.decorators[0]
    context = BeforeContext([decorator1])
    assert find_context(fun.decorators, context, node_list_workaround=False) == 1
