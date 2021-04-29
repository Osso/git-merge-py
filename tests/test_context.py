from redbaron import RedBaron

from gitmergepy.context import (AfterContext,
                                BeforeContext,
                                find_context)


def test_match_after_context():
    tree = RedBaron("# line 1\n# line 2\n# line 3\n")
    line2 = tree[1]
    line3 = tree[2]
    # At then end
    context = AfterContext([None])
    assert not context.match(tree, 2)
    assert context.match(tree, 3)
    # At then end -2
    context = AfterContext([line3, None])
    assert not context.match(tree, 1)
    assert context.match(tree, 2)
    assert not context.match(tree, 3)
    # Pattern found but not at the end
    context = AfterContext([line2, None])
    assert not context.match(tree, 2)
    # Pattern found
    context = AfterContext([line2])
    assert context.match(tree, 1)


def test_match_before_context():
    tree = RedBaron("# line 1\n# line 2\n# line 3\n")
    line1 = tree[0]
    line2 = tree[1]

    # At the beginning
    context = BeforeContext([None])
    assert context.match(tree, 0)
    assert not context.match(tree, 1)
    # At the begining +2
    context = BeforeContext([line1, None])
    assert not context.match(tree, 0)
    assert context.match(tree, 1)
    assert not context.match(tree, 2)
    assert not context.match(tree, 3)
    # Pattern found but not at the beginning
    context = BeforeContext([line2, None])
    assert not context.match(tree, 2)
    # Pattern found
    context = BeforeContext([line2])
    assert context.match(tree, 2)


def test_match_el_after_context():
    tree = RedBaron("# line 1\n# line 2\n# line 3\n")
    line2 = tree[1]
    line3 = tree[2]

    # At then end
    context = AfterContext([None])
    assert not context.match_el(tree, tree[1])
    assert context.match_el(tree, tree[2])
    # At then end -2
    context = AfterContext([line3, None])
    assert not context.match_el(tree, tree[0])
    assert context.match_el(tree, tree[1])
    assert not context.match_el(tree, tree[2])
    # Pattern found but not at the end
    context = AfterContext([line2, None])
    assert not context.match_el(tree, tree[0])
    # Pattern found
    context = AfterContext([line2])
    assert context.match_el(tree, tree[0])


def test_match_el_before_context():
    tree = RedBaron("# line 1\n# line 2\n# line 3\n")
    line1 = tree[0]
    line2 = tree[1]

    # At the beginning
    context = BeforeContext([None])
    assert context.match_el(tree, tree[0])
    assert not context.match_el(tree, tree[1])
    # At the begging +2
    context = BeforeContext([line1, None])
    assert not context.match_el(tree, tree[0])
    assert context.match_el(tree, tree[1])
    assert not context.match_el(tree, tree[2])
    # Pattern found but not at the beginning
    context = BeforeContext([line2, None])
    assert not context.match_el(tree, tree[2])
    # Pattern found
    context = BeforeContext([line2])
    assert context.match_el(tree, tree[2])


def test_find_context():
    tree = RedBaron("# line 1\n# line 2\n# line 3\n")
    line1 = tree[0]
    line3 = tree[2]

    # At the end
    context = BeforeContext([None])
    assert find_context(tree, context) == 0
    # At the end -2
    context = BeforeContext([line1])
    assert find_context(tree, context) == 1

    context = BeforeContext([line3])
    assert find_context(tree, context) == 3

    context = AfterContext([line3])
    assert find_context(tree, context) == 2


def test_find_context_decorator():
    tree = RedBaron("""
@decorator1
@decorator3
@decorator2
def fun():
    pass
""")
    fun = tree[0]
    decorator1 = fun.decorators[0]
    context = BeforeContext([decorator1])
    assert find_context(fun.decorators, context) == 1
