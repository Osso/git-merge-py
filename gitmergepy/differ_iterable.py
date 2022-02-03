from itertools import islice
import logging

from redbaron import nodes

from .actions import (AddImports,
                      ChangeClass,
                      ChangeEl,
                      ChangeFun,
                      ChangeImport,
                      EnsureEmptyLines,
                      MoveClass,
                      MoveFun,
                      MoveImport,
                      RemoveEls)
from .context import gather_context
from .differ import (add_to_diff,
                     changed_el,
                     compute_diff,
                     process_stack_till_el,
                     simplify_white_lines)
from .matcher import (find_class,
                      find_func,
                      find_import)
from .tools import (INDENT,
                    id_from_el,
                    short_display_el)


def _process_empty_lines(el):
    empty_lines = []

    for _el in islice(el.next_neighbors, 0, 2):
        if not isinstance(_el, nodes.EmptyLineNode):
            break
        _el.already_processed = True
        empty_lines.append(_el)

    return empty_lines


def diff_node_with_id(stack_left, el_right, indent, global_diff,
                      el_type, finder, change_class, move_class):
    logging.debug("%s changed %r", indent, short_display_el(el_right))
    diff = []

    if hasattr(el_right, 'matched_el'):  # already matched earlier
        logging.debug("%s already matched %r", indent+INDENT,
                      id_from_el(el_right))
        most_similiar_node = el_right.matched_el
        maybe_moved = True
    else:
        most_similiar_node = finder(stack_left, el_right)
        el_right.matched_el = most_similiar_node
        logging.debug("%s looking for best match %r",
                      indent+INDENT, id_from_el(most_similiar_node))
        maybe_moved = False

    if not most_similiar_node:
        logging.debug("%s new", indent+INDENT)
        el_diff = []
        new_empty_lines = _process_empty_lines(el_right)
        if new_empty_lines:
            el_diff += [EnsureEmptyLines(new_empty_lines)]
        add_to_diff(diff, el_right, indent=indent+2*INDENT, changes=el_diff)
    elif most_similiar_node is stack_left[0]:
        logging.debug("%s not moved", indent+INDENT)
        diff += changed_el(el_right, stack_left, indent=indent,
                            change_class=change_class)
    else:
        if maybe_moved:
            logging.debug("%s moved", indent+INDENT)
        else:
            logging.debug("%s %r ahead, processing stack", indent+INDENT,
                          id_from_el(el_right))
            process_stack_till_el(stack_left, stop_el=most_similiar_node,
                                  tree=el_right.parent,
                                  diff=diff,
                                  indent=indent)
            global_diff.extend(diff)
            simplify_white_lines(global_diff, indent=indent+INDENT)
            diff = []

        most_similiar_node.already_processed = True
        el_right.already_processed = True
        new_empty_lines = _process_empty_lines(el_right)
        old_empty_lines = _process_empty_lines(most_similiar_node)
        el_diff = compute_diff(most_similiar_node, el_right,
                               indent=indent+2*INDENT)
        if new_empty_lines:
            el_diff += [EnsureEmptyLines(new_empty_lines)]
        context = gather_context(el_right)
        if maybe_moved:
            diff += [move_class(most_similiar_node, changes=el_diff,
                                context=context,
                                old_empty_lines=old_empty_lines)]
        elif el_diff:
            diff += [change_class(most_similiar_node, changes=el_diff,
                                  context=context)]
    return diff


def diff_def_node(stack_left, el_right, indent, global_diff):
    return diff_node_with_id(stack_left, el_right, indent, global_diff,
                             el_type=nodes.DefNode, finder=find_func,
                             change_class=ChangeFun, move_class=MoveFun)


def diff_class_node(stack_left, el_right, indent, global_diff):
    return diff_node_with_id(stack_left, el_right, indent, global_diff,
                             el_type=nodes.ClassNode, finder=find_class,
                             change_class=ChangeClass, move_class=MoveClass)


def diff_atom_trailer_node(stack_left, el_right, indent, global_diff):
    diff = []
    if id_from_el(el_right) == id_from_el(stack_left[0]) or \
            el_right[0] == stack_left[0][0] == 'super':
        logging.debug("%s modified call %r", indent+INDENT,
                      short_display_el(el_right))
        el_left = stack_left.pop(0)
        el_diff = compute_diff(el_left, el_right, indent=indent+INDENT)
        if el_diff:
            diff += [ChangeEl(el_left, el_diff,
                              context=gather_context(el_left))]
        logging.debug("%s modified call diff %r", indent+INDENT, diff)
    else:
        logging.debug("%s new AtomtrailersNode %r", indent+INDENT,
                      el_right.dumps())
        add_to_diff(diff, el_right, indent=indent+2*INDENT)

    return diff


def diff_from_import_node(stack_left, el_right, indent, global_diff):
    logging.debug("%s changed import %r", indent, short_display_el(el_right))
    diff = []

    def remove_import_if_not_found(stack):
        nonlocal diff
        to_remove = []
        # Try to keep in left and right stacks in sync, so that empty lines
        # can also be matched
        while stack_left and isinstance(stack_left[0], (nodes.FromImportNode,
                                                        nodes.ImportNode,
                                                        nodes.EmptyLineNode)):
            if isinstance(stack_left[0], nodes.EmptyLineNode):
                logging.debug("%s blank line to remove %r", indent+INDENT,
                              short_display_el(stack_left[0]))
                to_remove.append(stack_left[0])
                stack_left.pop(0)
            elif not find_import(el_right.parent, stack_left[0]):
                logging.debug("%s import to remove %r", indent+INDENT,
                              short_display_el(stack_left[0]))
                to_remove.append(stack_left[0])
                stack_left.pop(0)
            else:
                break
        if to_remove:
            diff += [RemoveEls(to_remove,
                               context=gather_context(to_remove[0]))]

    if hasattr(el_right, 'matched_el'):  # Already matched earlier
        el = el_right.matched_el
    else:
        els = find_import(stack_left, el_right)
        el = els[0] if els else None

    if el:
        el_diff = compute_diff(el, el_right, indent=indent+INDENT)
        if not el_diff:
            logging.debug("%s not changed", indent+INDENT)

        if not stack_left or el is not stack_left[0]:
            logging.debug("%s moved", indent+INDENT)
            el_diff += [MoveImport(el_right, context=gather_context(el_right))]

        if el_diff:
            diff += [ChangeImport(el, el_diff, context=gather_context(el))]

        # Remove el from stack
        if not hasattr(el_right, 'matched_el'):
            if el is stack_left[0]:
                stack_left.pop(0)
            else:
                el.already_processed = True
                remove_import_if_not_found(stack_left)

    else:
        # new import
        logging.debug("%s new import %r", indent+INDENT, id_from_el(el_right))
        diff += [ChangeImport(el_right, changes=[AddImports(el_right.targets)],
                              can_be_added_as_is=True,
                              context=gather_context(el_right))]
        remove_import_if_not_found(stack_left)

    return diff


def diff_return_node(stack_left, el_right, indent, global_diff):
    assert el_right.matched_el
    return compute_diff(el_right.matched_el, el_right, indent)


COMPUTE_DIFF_ITERABLE_CALLS = {
    nodes.DefNode: diff_def_node,
    nodes.ClassNode: diff_class_node,
    nodes.AtomtrailersNode: diff_atom_trailer_node,
    nodes.FromImportNode: diff_from_import_node,
    nodes.ReturnNode: diff_return_node,
}
