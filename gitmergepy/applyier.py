from redbaron import (RedBaron,
                      nodes)

from .context import (AfterContext,
                      BeforeContext,
                      find_context)
from .tools import (LAST,
                    append_coma_list,
                    insert_coma_list)

PLACEHOLDER = RedBaron("# GITMERGEPY PLACEHOLDER")[0]


def apply_changes(tree, changes):
    conflicts = []

    for change in changes:
        # logging.debug('applying %r to %r', change, short_display_el(tree))
        conflicts += change.apply(tree)

    return conflicts


def insert_at_context(el, context, tree, endl=None):
    if context is LAST:  # insert at the end
        tree.append(el)
    elif context[-1] is None:  # insert at the beginning
        tree.insert(0, el)
    else:  # look for context
        index = find_context(tree, context)
        if index:
            # Move function to new position
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
        insert_coma_list(tree, position=0, to_add=el, new_line=new_line)
        return True

    # Look for context
    index = find_context(tree, context)
    if index:
        insert_coma_list(tree, position=index, to_add=el, new_line=new_line)
        return True

    return False


def apply_changes_safe(tree, changes):
    """Workaround redbaron bug in case of empty tree"""
    conflicts = apply_changes(tree, changes)
    return conflicts


def add_conflicts(source_el, conflicts):
    for conflict in conflicts:
        add_conflict(source_el, conflict)


def add_conflict(source_el, conflict):
    if isinstance(source_el.parent, nodes.IfelseblockNode):
        source_el = source_el.parent

    if conflict.insert_before and source_el.parent is not None:
        tree = source_el.parent
        index = tree.index(source_el)
    else:
        tree = source_el
        index = 0

    def _insert(text):
        nonlocal index
        tree.insert(index, "# " + text + "\n")
        index += 1

    before_text = "<<<<<<<<<<"
    after_text = ">>>>>>>>>>"
    _insert(before_text)
    if conflict.reason:
        _insert("Reason %s" % conflict.reason)
    if conflict.change:
        _insert(repr(conflict.change))
    if conflict.els:
        for el in conflict.els:
            for line in el.dumps().splitlines():
                _insert(line.strip())
    _insert(after_text)
    tree.insert(index, "\n")
