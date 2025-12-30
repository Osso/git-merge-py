from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .context import find_context

if TYPE_CHECKING:
    from redbaron.base_nodes import Node
    from redbaron.proxy_list import ProxyList


def append_coma_list(target_list: ProxyList, to_add: Node | str, on_new_line: bool = False) -> None:
    insert_coma_list(target_list, len(target_list), to_add, on_new_line=on_new_line)


def insert_coma_list(
    target_list: ProxyList, position: int, to_add: Node | str, on_new_line: bool = False
) -> None:
    if on_new_line:
        target_list.insert_on_new_line(position, to_add)
    else:
        target_list.insert(position, to_add)


def insert_at_context_coma_list(
    el: Node | str, context: list[Any], tree: ProxyList, on_new_line: bool = False
) -> bool:
    # Look for context
    indexes = find_context(tree, context)
    if indexes:
        insert_coma_list(tree, position=indexes[0], to_add=el, on_new_line=on_new_line)
        return True

    return False
