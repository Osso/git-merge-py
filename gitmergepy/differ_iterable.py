import logging

from redbaron import nodes

from .context import gather_context
from .differ import (add_to_diff,
                     changed_el,
                     compute_diff,
                     process_stack_till_el,
                     simplify_white_lines)
from .matcher import (CODE_BLOCK_SAME_THRESHOLD,
                      code_block_similarity,
                      find_class,
                      find_func,
                      find_import)
from .tools import (INDENT,
                    id_from_el,
                    short_display_el)
from .tree import (AddImports,
                   ChangeClass,
                   ChangeEl,
                   ChangeFun,
                   ChangeImport,
                   MoveClass,
                   MoveFun,
                   MoveImport,
                   RemoveEls)


def _process_empty_lines(el, el_right):
    empty_lines = []

    _el = el.next
    _el_right = el_right
    for _ in range(2):
        if not isinstance(_el, nodes.EmptyLineNode):
            break
        empty_lines.append(_el)
        _el.already_processed = True
        if (isinstance(_el_right.next, nodes.EmptyLineNode) and
                _el_right.already_processed):
            _el_right.next.already_processed = True

        _el = _el.next
        _el_right = _el_right.next

    return empty_lines


def diff_node_with_id(stack_left, el_right, indent, global_diff,
                      el_type=nodes.DefNode, finder=find_func,
                      change_class=ChangeFun, move_class=MoveFun,
                      process_empty_lines=True):
    logging.debug("%s changed %r", indent, short_display_el(el_right))
    diff = []

    # el has not been moved and stack is the same
    if (stack_left and
            isinstance(stack_left[0], el_type) and
            id_from_el(stack_left[0]) == id_from_el(el_right)):
        logging.debug("%s not moved", indent+INDENT)
        diff += changed_el(el_right, stack_left, indent=indent,
                            change_class=change_class)
    else:
        if hasattr(el_right, 'matched_el'):  # already matched earlier
            logging.debug("%s already matched & moved %r", indent+INDENT,
                          id_from_el(el_right))
            el = el_right.matched_el
            moved = True
        else:  # el has not been moved, some old elements are before it
            logging.debug("%s assuming not moved, removing preceeding els %r",
                          indent+INDENT, id_from_el(el_right))
            el = finder(stack_left, el_right)
            moved = False
        if el:
            el.already_processed = True
            el_right.already_processed = True
            if process_empty_lines:
                empty_lines = _process_empty_lines(el, el_right)
            else:
                empty_lines = []
            if not moved and el in stack_left:
                logging.debug("%s %r ahead, processing stack", indent+INDENT,
                              id_from_el(el_right))
                process_stack_till_el(stack_left, stop_el=el,
                                      tree=el_right.parent,
                                      diff=diff,
                                      indent=indent)
                global_diff.extend(diff)
                simplify_white_lines(global_diff, indent=indent+INDENT)
                diff = []
            el_diff = compute_diff(el, el_right, indent=indent+2*INDENT)
            context = gather_context(el_right)
            if moved:
                diff += [move_class(el, changes=el_diff, context=context,
                                    empty_lines=empty_lines)]
            elif el_diff:
                diff += [change_class(el, changes=el_diff, context=context)]
        else:
            if code_block_similarity(el_right, stack_left[0]) > CODE_BLOCK_SAME_THRESHOLD:
                logging.debug("%s renamed %r", indent+INDENT,
                              id_from_el(el_right))
                el_diff = compute_diff(stack_left[0], el_right,
                                       indent=indent+INDENT)
                assert el_diff  # at least a rename
                el_right.old_name = id_from_el(stack_left[0])
                diff += [change_class(stack_left[0], el_diff,
                                      context=gather_context(el_right))]
                stack_left.pop(0)
            elif isinstance(stack_left[0], nodes.DefNode) and el_right.parent:
                el = finder(el_right.parent, stack_left[0])
                if el:
                    # stack_left[0] is defined somewhere else
                    # we are not modifying it
                    logging.debug("%s new %r", indent+INDENT,
                                  id_from_el(el_right))
                    add_to_diff(diff, el_right, indent=indent+2*INDENT)
                else:
                    # stack_left[0] is nowhere else
                    # assume function is modified
                    logging.debug("%s assumed changed %r", indent+INDENT,
                                  id_from_el(el_right))
                    old_name = id_from_el(stack_left[0])
                    diff_el = changed_el(el_right, stack_left, indent=indent,
                                          change_class=change_class)
                    if diff_el:
                        diff_el[0].old_name = old_name
                        diff += diff_el
            else:
                logging.debug("%s new %r", indent+INDENT, id_from_el(el_right))
                add_to_diff(diff, el_right, indent=indent+2*INDENT)
    return diff


def diff_def_node(stack_left, el_right, indent, global_diff):
    return diff_node_with_id(stack_left, el_right, indent, global_diff,
                             el_type=nodes.DefNode, finder=find_func,
                             change_class=ChangeFun, move_class=MoveFun,
                             process_empty_lines=True)


def diff_class_node(stack_left, el_right, indent, global_diff):
    return diff_node_with_id(stack_left, el_right, indent, global_diff,
                             el_type=nodes.ClassNode, finder=find_class,
                             change_class=ChangeClass, move_class=MoveClass,
                             process_empty_lines=True)


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
        el = find_import(stack_left, el_right)

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
