import logging

from redbaron import RedBaron

from .matcher import find_context
from .tools import (FIRST,
                    short_display_el)

PLACEHOLDER = RedBaron("# GITMERGEPY PLACEHOLDER")[0]


def apply_changes(tree, changes):
    conflicts = []

    for change in changes:
        logging.debug('applying %r to %r', change, short_display_el(tree))
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
    conflicts = apply_changes(tree, changes)
    tree.remove(PLACEHOLDER)
    return conflicts


def add_conflict(el, changes):
    before_text = "<<<<<<<<<<"
    after_text = ">>>>>>>>>>"
    el.insert_before("#"+before_text)
    el.insert_before("# %r" % changes)
    el.insert_before("#"+after_text)
    for text in (before_text, after_text):
        for e in el.parent.find_all('CommentNode', value="#"+text):
            e.value = text
