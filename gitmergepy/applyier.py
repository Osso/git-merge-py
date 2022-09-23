from redbaron import (RedBaron,
                      nodes)
from redbaron.base_nodes import NodeList
from redbaron.node_mixin import ValueIterableMixin
from redbaron.proxy_list import (DictProxyList,
                                 ProxyList)

PLACEHOLDER = RedBaron("# GITMERGEPY PLACEHOLDER")[0]


def hide_if_empty(tree):
    if all(el.hidden for el in tree):
        tree.hidden = True


def apply_changes(tree, changes, skip_checks=False):
    from .actions import Replace

    conflicts = []
    for change in changes:
        conflicts += change.apply(tree)

    if len(changes) == 1 and isinstance(changes[0], Replace):
        tree = tree.parent
    if isinstance(tree, nodes.CallNode) and tree.value.auto_separator:
        tree.value.reformat()
    elif isinstance(tree, nodes.DefNode):
        tree.arguments.reformat()

    if isinstance(tree, (nodes.ClassNode, nodes.DefNode)):
        tree.value._synchronise()

    # Hide if empty
    if isinstance(tree, (NodeList, ValueIterableMixin)):
        hide_if_empty(tree)
        skip_checks = True

    # Sanity check
    if not skip_checks and not tree.hidden:  # skipped for fragments that are not parseable
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
        if isinstance(tree, (nodes.CallNode, nodes.ExceptNode)):
            tree = tree.parent.parent
        RedBaron(tree.dumps())

    return conflicts
