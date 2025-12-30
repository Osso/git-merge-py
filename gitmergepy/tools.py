"""Utility functions for AST manipulation and display."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from redbaron import nodes
from redbaron.base_nodes import Node
from redbaron.proxy_list import DotProxyList, ProxyList

FIRST = object()
LAST = object()
INDENT = "."
WHITESPACE_NODES = (nodes.EndlNode, nodes.EmptyLineNode)

T = TypeVar("T")


def sort_imports(targets: ProxyList) -> None:
    """Sort import targets alphabetically and reformat."""
    targets.sort(key=lambda el: el.value)
    targets.reformat(force_separator=True)


def merge_imports(imports: list[Node]) -> None:
    """Merge multiple import statements into the first one."""
    from .actions import AddImports

    target_import = imports.pop(0)
    for import_el in imports:
        AddImports(import_el.targets).apply(target_import)
        import_el.parent.remove(import_el)


def short_display_el(el: Node | None) -> str:
    """Return a short string representation of an AST element."""
    match el:
        case None:
            return "None"
        case nodes.DefNode():
            return f'Fun("{el.name}")'
        case nodes.ClassNode():
            return f'Class("{el.name}")'
        case nodes.EndlNode():
            return f"new line indent={len(el.indent)}"
        case _:
            for line in el.dumps().splitlines():
                if line.strip():
                    return line.strip()
            return "a bunch of blank lines"


def short_display_list(node_list: list[Node]) -> str:
    """Return comma-separated short display of a list of nodes."""
    return ", ".join(short_display_el(el) for el in node_list)


def short_context(context: Any) -> str:
    """Return a short string representation of a context."""
    if context is None:
        return "no context"
    if context is LAST:
        return "last"

    from .context import AfterContext

    if isinstance(context, AfterContext):
        return "before " + "|".join(short_display_el(el) for el in context)

    return "|".join(short_display_el(el) for el in reversed(context))


def id_from_el(arg: Node | None) -> str:
    """Extract a unique identifier string from an AST element."""
    match arg:
        case None:
            return ""
        case nodes.DefNode() | nodes.ClassNode():
            return arg.name
        case nodes.FromImportNode():
            return id_from_el(arg.value)
        case nodes.CallArgumentNode():
            if arg.target is not None:
                return id_from_el(arg.target)
            return id_from_el(arg.value)
        case nodes.ListArgumentNode():
            return "*" + id_from_el(arg.value)
        case nodes.DictArgumentNode():
            return "**" + id_from_el(arg.value)
        case nodes.DefArgumentNode():
            return arg.target.value
        case nodes.DecoratorNode():
            return id_from_el(arg.value)
        case nodes.StringNode() | nodes.NumberNode() | nodes.NameNode():
            return arg.value
        case nodes.DotNode():
            return "."
        case nodes.GetitemNode():
            return "[" + id_from_el(arg.value) + "]"
        case nodes.AtomtrailersNode() | nodes.DottedNameNode() | DotProxyList():
            return ".".join(
                id_from_el(el) if not isinstance(el, nodes.CallNode) else "()" for el in arg
            )
        case nodes.DictitemNode():
            return id_from_el(arg.key)
        case _:
            return arg.dumps()


def id_from_arg(arg: Node) -> str:
    """Extract identifier from a function argument node."""
    match arg:
        case nodes.ListArgumentNode() | nodes.DictArgumentNode():
            return id_from_el(arg)
        case _ if not arg.target and isinstance(arg.value, nodes.NumberNode):
            return "0_%d" % arg.index_on_parent
        case _ if isinstance(arg.value, nodes.ListNode):
            target = arg.target.dumps() if arg.target else "%d" % arg.index_on_parent
            return target + "=[...]"
        case _ if isinstance(arg.value, nodes.StringNode):
            target = arg.target.dumps() if arg.target else "%d" % arg.index_on_parent
            return target + '=""'
        case _:
            return id_from_el(arg)


def significant_args(call_node: nodes.CallNode) -> str:
    """Return significant arguments representation (placeholder)."""
    return "()"


def id_from_decorator(decorator: Node) -> str:
    """Extract identifier from a decorator node."""

    def call_to_id(call: nodes.CallNode | None) -> str:
        if call is None:
            return ""
        # If first arg is a string and it's different, probably not the same call
        if call.value and isinstance(call.value[0].value, nodes.StringNode):
            return "(%s)" % call.value[0].dumps()
        return "()"

    match decorator:
        case nodes.DecoratorNode():
            return "".join(id_from_el(el) for el in decorator.value) + call_to_id(decorator.call)
        case nodes.CommentNode():
            return decorator.dumps()
        case _:
            raise ValueError(f"Unexpected decorator type: {type(decorator)}")


def diff_list(
    left: list[T],
    right: list[T],
    key_getter: Callable[[T], str] = id_from_el,
    value_getter: Callable[[T], str] | None = None,
) -> tuple[list[T], list[T]]:
    """Compute elements to add and remove between two lists.

    Returns:
        Tuple of (to_add, to_remove) lists.
    """
    left = list(left)
    right = list(right)
    left_keys = set(key_getter(i) for i in left)
    right_keys = set(key_getter(i) for i in right)

    to_add = [el for el in right if key_getter(el) not in left_keys]
    to_remove = [el for el in left if key_getter(el) not in right_keys]

    return to_add, to_remove


def changed_in_list(
    left: list[T],
    right: list[T],
    key_getter: Callable[[T], str] = id_from_el,
    value_getter: Callable[[T], str] = lambda el: el.dumps(),
) -> list[tuple[T, T]]:
    """Find elements that exist in both lists but have different values.

    Returns:
        List of (left_el, right_el) tuples for changed elements.
    """
    left_keys = set(key_getter(i) for i in left)
    right_keys = set(key_getter(i) for i in right)
    both_keys = left_keys & right_keys

    changed = []
    left_els_map = {key_getter(el): el for el in left if key_getter(el) in both_keys}
    rights_els_map = {key_getter(el): el for el in right if key_getter(el) in both_keys}

    for key, left_el in left_els_map.items():
        right_el = rights_els_map[key]
        if value_getter(left_el) != value_getter(right_el):
            changed.append((left_el, right_el))

    return changed


def apply_diff_to_list(
    elements: list[T],
    to_add: list[T],
    to_remove: list[T],
    key_getter: Callable[[T], str],
) -> None:
    """Apply additions and removals to a list in place."""
    existing_values = set(key_getter(el) for el in elements)
    to_add = [el for el in to_add if key_getter(el) not in existing_values]
    elements.extend(to_add)

    to_remove_values = set(key_getter(el) for el in to_remove)
    for el in list(elements):
        if key_getter(el) in to_remove_values:
            elements.remove(el)


def is_iterable(el: Any) -> bool:
    """Check if an element is iterable (indexable)."""
    try:
        el[0]
    except TypeError:
        return False
    else:
        return True


def get_call_els(atom_trailer_node: nodes.AtomtrailersNode) -> list[nodes.CallNode]:
    """Get all CallNode elements from an AtomtrailersNode."""
    return atom_trailer_node.find_all("call", recursive=False)


def get_name_els_from_call(el: Node) -> list[nodes.NameNode]:
    """Extract leading NameNodes from a call expression."""
    name_els = []
    for sub_el in el:
        if not isinstance(sub_el, nodes.NameNode):
            break
        name_els.append(sub_el)
    return name_els


def name_els_to_string(els: list[nodes.NameNode]) -> str:
    """Join name elements with dots."""
    return ".".join(el.dumps() for el in els)


def as_from_contexts(contexts: ProxyList) -> set[str]:
    """Extract 'as' names from with/import contexts."""
    return set(c.as_.value if c.as_ else id_from_el(c.value) for c in contexts)


def skip_context_endl(tree: ProxyList, context: Any, index: int = 0) -> int:
    """Skip empty lines at the start of a tree, returning new index."""
    if not tree:
        return 0

    while index < len(tree) and isinstance(tree[index], nodes.EmptyLine):
        index += 1
    return index


def with_parent(tree: ProxyList, el: Node) -> Node:
    """Attach parent and on_attribute to an element."""
    el.parent = tree
    el.on_attribute = tree.on_attribute
    return el


def same_el(left: Node | None, right: Node | None, discard_indentation: bool = True) -> bool:
    """Check if two elements are the same (by dumps comparison)."""
    if left is None and right is None:
        return True

    if isinstance(left, (nodes.SpaceNode, nodes.EmptyLineNode)):
        return left.dumps() == right.dumps()

    # For speed
    if type(left) != type(right):  # pylint: disable=unidiomatic-typecheck
        return False

    if discard_indentation:
        return left.dumps().lstrip(" ") == right.dumps().lstrip(" ")
    return left.dumps() == right.dumps()


def empty_lines(els: list[Node]) -> bool:
    """Check if all elements are empty/newline nodes."""
    return all(isinstance(el, (nodes.EmptyLineNode, nodes.EndlNode)) for el in els)


def get_args_names(args: ProxyList | nodes.CallNode) -> list[str]:
    """Get list of argument names/identifiers."""
    assert isinstance(args.parent, nodes.DefNode) or isinstance(args, nodes.CallNode)
    return [id_from_el(arg) for arg in args]
