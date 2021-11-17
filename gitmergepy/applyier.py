from redbaron import (RedBaron,
                      nodes)
from redbaron.proxy_list import (DictProxyList,
                                 ProxyList)

PLACEHOLDER = RedBaron("# GITMERGEPY PLACEHOLDER")[0]


def apply_changes(tree, changes, skip_checks=False):
    conflicts = []
    for change in changes:
        conflicts += change.apply(tree)

    if isinstance(tree, nodes.CallNode) and tree.value.auto_separator:
        tree.value.reformat()
    elif isinstance(tree, nodes.DefNode):
        tree.arguments.reformat()

    if isinstance(tree, (nodes.ClassNode, nodes.DefNode)):
        tree.value._synchronise()

    # Sanity check
    if not skip_checks:  # skipped for fragments that are not parseable
        if isinstance(tree.parent, DictProxyList):
            tree = tree.parent.parent
        if isinstance(tree, (nodes.DictArgumentNode, nodes.DecoratorNode,
                             nodes.WithNode, nodes.CallArgumentNode,
                             nodes.ElifNode, nodes.ExceptNode)):
            tree = tree.parent.parent
        if isinstance(tree, nodes.CallNode):
            tree = tree.parent.parent
        while isinstance(tree, (nodes.ElseNode, ProxyList)):
            tree = tree.parent
        RedBaron(tree.dumps())

    return conflicts
