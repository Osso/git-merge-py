from redbaron import RedBaron

from .matcher import (find_context,
                      gather_context)
from .tools import FIRST

PLACEHOLDER = RedBaron("# GITMERGEPY PLACEHOLDER")[0]


def apply_changes(tree, changes):
    conflicts = []

    for change in changes:
        print('applying change', change)
        conflicts += change.apply(tree)

    return conflicts


def insert_at_context(el, context, tree):
    if context is FIRST:
        # move to beginning
        tree.insert(0, el)
    else:
        # Look for context
        context_el = find_context(tree, context)
        if context_el:
            # Move function to new position
            tree.insert(tree.index(context_el)+1, el)
        else:
            tree.extend(el)
            return False
    return True


def apply_changes_safe(tree, changes):
    """Workaround redbaron bug in case of empty tree"""
    tree.append(PLACEHOLDER)
    apply_changes(tree, changes)
    tree.remove(PLACEHOLDER)
