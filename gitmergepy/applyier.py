import logging

from redbaron import RedBaron

from .matcher import find_context
from .tools import (FIRST,
                    LAST,
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
        # insert at the beginning
        tree.insert(0, el)
    elif context is LAST:
        # insert at the end
        tree.append(el)
    else:
        # Look for context
        context_el = find_context(tree, context[-1])
        if context_el:
            print('args', type(tree))
            # Move function to new position
            # Workaround redbaron insert_after bug
            tree.insert(tree.index(context_el)+1, el)
        else:
            return False
    return True


def apply_changes_safe(tree, changes):
    """Workaround redbaron bug in case of empty tree"""
    tree.append(PLACEHOLDER)
    conflicts = apply_changes(tree, changes)
    tree.remove(PLACEHOLDER)
    return conflicts


def add_conflicts(source_el, conflicts):
    for conflict in conflicts:
        add_conflict(source_el, conflict)


def add_conflict(source_el, conflict):
    index = 0

    def _insert(text):
        nonlocal index
        if conflict.insert_before:
            source_el.insert_before(text)
        else:
            source_el.insert(index, text)
            index += 1

    before_text = "<<<<<<<<<<"
    after_text = ">>>>>>>>>>"
    _insert("# "+before_text)
    if conflict.reason:
        _insert("# Reason %s" % conflict.reason)
    if conflict.change:
        _insert("# %r" % conflict.change)
    if conflict.els:
        for el in conflict.els:
            for line in el.dumps().splitlines():
                line = "# %s" % line
                _insert(line.strip())
    _insert("# "+after_text)
    # Remove # in front
    # for text in (before_text, after_text):
    #     for e in el.parent.find_all('CommentNode', value="# "+text):
    #         e.value = text
