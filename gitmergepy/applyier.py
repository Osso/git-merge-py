import logging

from redbaron import (RedBaron,
                      nodes)

from .matcher import find_context
from .tools import (FIRST,
                    LAST,
                    append_coma_list,
                    insert_coma_list,
                    short_display_el)

PLACEHOLDER = RedBaron("# GITMERGEPY PLACEHOLDER")[0]


def apply_changes(tree, changes):
    conflicts = []

    for change in changes:
        logging.debug('applying %r to %r', change, short_display_el(tree))
        conflicts += change.apply(tree)

    return conflicts


def insert_at_context(el, context, tree, node_list_workaround=False,
                      endl=None):
    if context is FIRST:
        # insert at the beginning
        if node_list_workaround:
            tree.node_list.insert(0, el)
            if endl is not None:
                tree.node_list.insert(0, endl)
        else:
            tree.insert(0, el)
    elif context is LAST:
        # insert at the end
        if node_list_workaround:
            if endl is not None:
                tree.node_list.append(endl)
            tree.node_list.append(el)
        else:
            tree.append(el)
    else:
        # Look for context
        context_el = find_context(tree, context[-1])
        if context_el:
            # Move function to new position
            # Workaround redbaron insert_after bug
            if node_list_workaround:
                index = tree.node_list.index(context_el) + 1
            else:
                index = tree.index(context_el) + 1
            # Workaround redbaron bug with new lines on insert
            if node_list_workaround:
                tree.node_list.insert(index, el)
                if endl is not None:
                    tree.node_list.insert(index, endl)
            else:
                tree.insert(index, el)
        else:
            return False
    return True


def insert_at_context_coma_list(el, context, tree, new_line=False):
    if context is FIRST:
        # insert at the beginning
        insert_coma_list(tree, position=0, to_add=el, new_line=new_line)
    elif context is LAST:
        # insert at the end
        append_coma_list(tree, el, new_line=new_line)
    else:
        # Look for context
        context_el = find_context(tree, context[-1])
        if context_el:
            # Move function to new position
            # Workaround redbaron insert_after bug
            insert_coma_list(tree, position=tree.index(context_el)+1,
                             to_add=el, new_line=new_line)
        else:
            return False
    return True


def apply_changes_safe(tree, changes):
    """Workaround redbaron bug in case of empty tree"""
    tree.node_list.append(PLACEHOLDER)
    conflicts = apply_changes(tree, changes)
    tree.node_list.remove(PLACEHOLDER)
    remove_trailing_empty_lines(tree)
    return conflicts


def remove_trailing_empty_lines(tree):
    while len(tree.node_list) > 1 and \
            isinstance(tree.node_list[-2], nodes.EndlNode) and \
            isinstance(tree.node_list[-1], nodes.EndlNode):
        tree.node_list.pop()


def add_conflicts(source_el, conflicts):
    for conflict in conflicts:
        add_conflict(source_el, conflict)


def add_conflict(source_el, conflict):
    index = 0

    def _insert(text):
        nonlocal index

        if conflict.insert_before:
            tree = source_el.parent
            text_el = tree._convert_input_to_node_object(text,
                                                         parent=tree.node_list,
                                                         on_attribute=tree.on_attribute)
            endl = tree._convert_input_to_node_object("\n",
                                                      parent=tree.node_list,
                                                      on_attribute=tree.on_attribute)
            _index = tree.node_list.index(source_el)
            tree.node_list.insert(_index, endl)
            tree.node_list.insert(_index, text_el)
        else:
            text_el = source_el._convert_input_to_node_object(text,
                                                              parent=source_el.node_list,
                                                              on_attribute=source_el.on_attribute)
            endl = source_el._convert_input_to_node_object("\n",
                                                           parent=source_el.node_list,
                                                           on_attribute=source_el.on_attribute)
            source_el.node_list.insert(index, endl)
            source_el.node_list.insert(index, text_el)
            index += 2

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
