from redbaron import RedBaron, nodes
from redbaron.base_nodes import NodeList
from redbaron.node_mixin import ValueIterableMixin
from redbaron.proxy_list import DictProxyList, ProxyList

PLACEHOLDER = RedBaron("# GITMERGEPY PLACEHOLDER")[0]


def hide_if_empty(tree):
    if all(el.hidden for el in tree):
        tree.hidden = True


def apply_changes(tree, changes, skip_checks=False):
    from .actions import RemoveImports, Replace

    conflicts = []
    for change in changes:
        conflicts += change.apply(tree)

    if len(changes) == 1 and isinstance(changes[0], (Replace, RemoveImports)):
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

    # Sanity check - verify the tree is still valid Python
    if not skip_checks and not getattr(tree, "hidden", False):
        try:
            tree_to_check = tree
            if isinstance(getattr(tree_to_check, "parent", None), DictProxyList):
                tree_to_check = tree_to_check.parent.parent
            if isinstance(
                tree_to_check,
                (
                    nodes.DictArgumentNode,
                    nodes.DecoratorNode,
                    nodes.WithNode,
                    nodes.CallArgumentNode,
                    nodes.ElifNode,
                    nodes.ExceptNode,
                ),
            ):
                tree_to_check = tree_to_check.parent.parent
            if isinstance(tree_to_check, nodes.CallNode):
                tree_to_check = tree_to_check.parent.parent
            while isinstance(tree_to_check, (nodes.ElseNode, ProxyList)):
                tree_to_check = tree_to_check.parent
            parent = getattr(tree_to_check, "parent", None)
            if (
                parent is not None
                and isinstance(parent, ProxyList)
                and getattr(tree_to_check, "is_sep", False)
            ):
                tree_to_check = tree_to_check.parent.parent
            if isinstance(tree_to_check, (nodes.CallNode, nodes.ExceptNode)):
                tree_to_check = tree_to_check.parent.parent
            RedBaron(tree_to_check.dumps())
        except RecursionError:
            # Skip sanity check if redbaron has recursion issues with moved nodes
            pass

    return conflicts
