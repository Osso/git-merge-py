from redbaron import (RedBaron,
                      nodes)

from .context import (AfterContext,
                      BeforeContext,
                      find_context,
                      find_context_coma_list)
from .tools import (LAST,
                    append_coma_list,
                    find_endl,
                    find_indentation,
                    insert_coma_list,
                    make_endl,
                    make_node,
                    skip_context_endl)

PLACEHOLDER = RedBaron("# GITMERGEPY PLACEHOLDER")[0]


def apply_changes(tree, changes):
    conflicts = []

    for change in changes:
        # logging.debug('applying %r to %r', change, short_display_el(tree))
        conflicts += change.apply(tree)

    return conflicts


def insert_at_context(el, context, tree, node_list_workaround=False,
                      endl=None):
    if context is LAST:
        # insert at the end
        if node_list_workaround:
            if endl is not None:
                tree.node_list.append(endl)
            tree.node_list.append(el)
        else:
            tree.append(el)
    elif context[-1] is None:
        # insert at the beginning
        if node_list_workaround:
            index = skip_context_endl(tree, context)
            tree.node_list.insert(index, el)
            if endl is not None:
                tree.node_list.insert(index, endl)
        else:
            tree.insert(0, el)
    else:
        # Look for context
        index = find_context(tree, context,
                             node_list_workaround=node_list_workaround)
        if index:
            # Move function to new position
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
    assert isinstance(context, (AfterContext, BeforeContext))

    if isinstance(context, AfterContext) and context[-1] is None:
        # insert at the end
        append_coma_list(tree, el, new_line=new_line)
        return True

    if isinstance(context, BeforeContext) and context[-1] is None:
        # insert at the beginning
        # insert_coma_list(tree, position=skip_context_endl(tree, context),
        #                  to_add=el, new_line=new_line)
        insert_coma_list(tree, position=0, to_add=el, new_line=new_line)
        return True

    # Look for context
    index = find_context_coma_list(tree, context)
    if index:
        insert_coma_list(tree, position=index, to_add=el, new_line=new_line)
        return True

    return False


def apply_changes_safe(tree, changes):
    """Workaround redbaron bug in case of empty tree"""
    tree.node_list.append(PLACEHOLDER)
    conflicts = apply_changes(tree, changes)
    tree.node_list.remove(PLACEHOLDER)
    remove_trailing_empty_lines(tree)
    add_final_endl(tree)
    return conflicts


def add_final_endl(tree):
    endl = make_endl(tree)

    if find_endl(tree) is None:
        tree.node_list.append(endl)


def remove_trailing_empty_lines(tree):
    while len(tree.node_list) > 1 and \
            isinstance(tree.node_list[-2], nodes.EndlNode) and \
            isinstance(tree.node_list[-1], nodes.EndlNode):
        tree.node_list.pop()


def add_conflicts(source_el, conflicts):
    for conflict in conflicts:
        add_conflict(source_el, conflict)


def add_conflict(source_el, conflict):
    if isinstance(source_el.parent, nodes.IfelseblockNode):
        source_el = source_el.parent

    if conflict.insert_before and source_el.parent is not None:
        tree = source_el.parent
        index = tree.node_list.index(source_el)
    else:
        tree = source_el
        index = 0

    # Copy indentation
    endl = find_indentation(source_el)
    if endl is None:
        endl = make_endl(tree)
        skip_first_endl = (tree.parent is None and index == 0)
    else:
        skip_first_endl = True

    def _insert(text, skip_indentation=False):
        nonlocal index
        text_el = make_node(text, parent=tree.node_list,
                            on_attribute=tree.on_attribute)
        if not skip_indentation:
            tree.node_list.insert(index, endl.copy())
            index += 1
        tree.node_list.insert(index, text_el)
        index += 1

    before_text = "<<<<<<<<<<"
    after_text = ">>>>>>>>>>"
    _insert("# "+before_text, skip_indentation=skip_first_endl)
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
    # if skip_first_endl:
    tree.node_list.insert(index, endl.copy())
    # Remove # in front
    # for text in (before_text, after_text):
    #     for e in el.parent.find_all('CommentNode', value="# "+text):
    #         e.value = text
