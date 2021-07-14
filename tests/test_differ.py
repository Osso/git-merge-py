from redbaron import (node,
                      nodes)

from gitmergepy.differ import simplify_white_lines
from gitmergepy.tree import (AddEls,
                             RemoveEls)


def test_simplify_white_lines():
    diff = [
        AddEls([nodes.EmptyLineNode()], context=[None]),
        RemoveEls([node("stuff")], context=[]),
        RemoveEls([node("stuff")], context=[]),
        RemoveEls([nodes.EmptyLineNode()], context=[]),
    ]
    simplify_white_lines(diff, indent="")
    assert len(diff) == 2
