from redbaron import RedBaron

from .matcher import (find_context,
                      gather_context)


def apply_changes(tree, changes):
    for change in changes:
        print('applying change', change)
        change.apply(tree)


def insert_at_context(el, context_stack, tree):
    try:
        context = context_stack[-1]
    except IndexError:
        context = None

    while context is not None:
        # Look for context
        context_el = find_context(tree, context)
        if context_el:
            # Move function to new position
            context_el.insert_after(el)
            break
        # Context not found, look for previous context
        context = gather_context(context)[-1]
    else:
        # move to beginning
        tree.insert(0, el)


def apply_changes_safe(tree, changes):
    """Workaround redbaron bug in case of empty tree"""
    placeholder = RedBaron("# GITMERGEPY PLACEHOLDER")[0]
    tree.append(placeholder)
    apply_changes(tree, changes)
    tree.remove(placeholder)
