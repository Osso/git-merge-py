from redbaron import node, nodes

from gitmergepy.actions import AddEls, RemoveEls
from gitmergepy.differ import simplify_white_lines


def test_simplify_white_lines():
    diff = [
        AddEls([nodes.EmptyLineNode()], context=[None]),
        RemoveEls([node("stuff")], context=[]),
        RemoveEls([node("stuff")], context=[]),
        RemoveEls([nodes.EmptyLineNode()], context=[]),
    ]
    simplify_white_lines(diff, indent="")
    assert len(diff) == 2
