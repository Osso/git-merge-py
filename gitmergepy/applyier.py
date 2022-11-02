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
        # we don't have the new tree here and tree is now a fragment
        skip_checks = True

    if isinstance(tree, nodes.CallNode) and tree.value.auto_separator:
        tree.value.reformat()
    elif isinstance(tree, nodes.DefNode):
        tree.arguments.reformat()

    if isinstance(tree, (nodes.ClassNode, nodes.DefNode)):
        tree.value._synchronise()

    # Hide if empty
    if isinstance(tree, (NodeList, ValueIterableMixin)):
        hide_if_empty(tree)

    # Sanity check
    if not skip_checks and not tree.hidden:  # skipped for fragments that are not parseable
        tree_to_check = tree
        if isinstance(tree_to_check.parent, DictProxyList):
            tree_to_check = tree_to_check.parent.parent
        if isinstance(tree_to_check, (nodes.DictArgumentNode,
                                      nodes.DecoratorNode,
                                      nodes.WithNode,
                                      nodes.CallArgumentNode,
                                      nodes.ElifNode,
                                      nodes.ExceptNode)):
            tree_to_check = tree_to_check.parent.parent
        if isinstance(tree_to_check, nodes.CallNode):
            tree_to_check = tree_to_check.parent.parent
        while isinstance(tree_to_check, (nodes.ElseNode, ProxyList)):
            tree_to_check = tree_to_check.parent
        if isinstance(tree_to_check.parent, ProxyList) and tree_to_check.is_sep:
            tree_to_check = tree_to_check.parent.parent
        if isinstance(tree_to_check, (nodes.CallNode, nodes.ExceptNode)):
            tree_to_check = tree_to_check.parent.parent
        RedBaron(tree_to_check.dumps())

    return conflicts
