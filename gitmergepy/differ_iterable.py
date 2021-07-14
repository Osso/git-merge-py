import logging

from redbaron import nodes

from .context import gather_context
from .differ import (add_to_diff,
                     compute_diff,
                     process_stack_till_el,
                     simplify_white_lines)
from .matcher import (CODE_BLOCK_SAME_THRESHOLD,
                      code_block_similarity,
                      find_func,
                      find_import)
from .tools import (INDENT,
                    id_from_el,
                    short_display_el)
from .tree import (AddImports,
                   ChangeClass,
                   ChangeFun,
                   ChangeImport,
                   MoveFunction,
                   MoveImport,
                   RemoveEls)


def _changed_el(el, stack_left, indent, context_class):
    diff = []
    el_diff = compute_diff(stack_left[0], el, indent=indent+INDENT)
    stack_left.pop(0)

    if el_diff:
        diff += [context_class(el, el_diff, context=gather_context(el))]

    return diff


def diff_def_node(stack_left, el_right, indent, context_class):
    logging.debug("%s changed fun %r", indent, short_display_el(el_right))
    diff = []

    def _process_empty_lines(el):
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

    # We have encountered a function
    if stack_left and isinstance(stack_left[0], nodes.DefNode) and stack_left[0].name == el_right.name:
        # Function has not been moved
        logging.debug("%s not moved", indent+INDENT)
        # empty_lines = _process_empty_lines(stack_left[0])
        diff += _changed_el(el_right, stack_left, indent=indent,
                            context_class=ChangeFun)
    else:
        if hasattr(el_right, 'matched_el'):  # Already matched earlier
            logging.debug("%s moved fun %r", indent+INDENT, el_right.name)
            el = el_right.matched_el
            moved = True
        else:  # Function has been moved, look for it
            logging.debug("%s %r ahead, processing stack", indent+INDENT,
                          el_right.name)
            el = find_func(stack_left, el_right)
            moved = False
        if el:
            el.already_processed = True
            el_right.already_processed = True
            empty_lines = _process_empty_lines(el)
            if not moved and el in stack_left:
                process_stack_till_el(stack_left, stop_el=el,
                                      tree=el_right.parent,
                                      diff=diff,
                                      context_class=context_class,
                                      indent=indent)
                simplify_white_lines(diff, indent=indent+INDENT)
            el_diff = compute_diff(el, el_right, indent=indent+2*INDENT)
            context = gather_context(el_right)
            diff += [MoveFunction(el, changes=el_diff, context=context,
                                  empty_lines=empty_lines)]
        else:
            if isinstance(stack_left[0], nodes.DefNode) and el_right.parent:
                el = find_func(el_right.parent, stack_left[0])
                if el:
                    # stack_left[0] is defined somewhere else
                    # we are not modifying it
                    logging.debug("%s new fun %r", indent+INDENT, el_right.name)
                    add_to_diff(diff, el_right, indent=indent+2*INDENT)
                else:
                    # stack_left[0] is nowhere else
                    # assume function is modified
                    logging.debug("%s assumed changed fun %r", indent+INDENT, el_right.name)
                    old_name = stack_left[0].name
                    diff_el = _changed_el(el_right, stack_left, indent=indent,
                                          context_class=ChangeFun)
                    if diff_el:
                        diff_el[0].old_name = old_name
                        diff += diff_el
            elif code_block_similarity(el_right, stack_left[0]) > CODE_BLOCK_SAME_THRESHOLD:
                logging.debug("%s renamed def %r", indent+INDENT, el_right.name)
                el_diff = compute_diff(stack_left[0], el_right,
                                       indent=indent+INDENT)
                assert el_diff  # at least a rename
                diff_el[0].old_name = old_name
                diff += [ChangeFun(stack_left[0], el_diff,
                                   context=gather_context(el_right))]
            else:
                logging.debug("%s new fun %r", indent+INDENT, el_right.name)
                add_to_diff(diff, el_right, indent=indent+2*INDENT)
    return diff


def diff_class_node(stack_left, el_right, indent, context_class):
    logging.debug("%s changed class %r", indent,
                  short_display_el(el_right))
    diff = []

    if isinstance(stack_left[0], nodes.ClassNode) and stack_left[0].name == el_right.name:
        diff += _changed_el(el_right, stack_left, indent=indent,
                            context_class=ChangeClass)
    elif code_block_similarity(el_right, stack_left[0]) > CODE_BLOCK_SAME_THRESHOLD:
        logging.debug("%s renamed class %r to %r", indent+INDENT,
                      stack_left[0].name, el_right.name)
        el_diff = compute_diff(stack_left[0], el_right, indent=indent+INDENT)
        assert el_diff  # at least a rename
        diff += [ChangeClass(stack_left[0], el_diff,
                             context=gather_context(el_right))]
        stack_left.pop(0)
    else:
        logging.debug("%s new class %r", indent+INDENT, el_right.name)
        add_to_diff(diff, el_right, indent=indent+2*INDENT)

    return diff


def diff_atom_trailer_node(stack_left, el_right, indent, context_class):
    diff = []
    if id_from_el(el_right) == id_from_el(stack_left[0]) or \
            el_right[0] == stack_left[0][0] == 'super':
        logging.debug("%s modified call %r", indent+INDENT,
                      short_display_el(el_right))
        el_left = stack_left.pop(0)
        el_diff = compute_diff(el_left, el_right, indent=indent+INDENT)
        if el_diff:
            diff += [context_class(el_left, el_diff, context=gather_context(el_left))]
        logging.debug("%s modified call diff %r", indent+INDENT, diff)
    else:
        logging.debug("%s new AtomtrailersNode %r", indent+INDENT,
                      el_right.dumps())
        add_to_diff(diff, el_right, indent=indent+2*INDENT)

    return diff


def diff_from_import_node(stack_left, el_right, indent, context_class):
    logging.debug("%s changed import %r", indent, short_display_el(el_right))
    diff = []

    def remove_import_if_not_found(stack):
        nonlocal diff
        # Try to keep in left and right stacks in sync, so that empty lines
        # can also be matched
        if stack_left and isinstance(stack_left[0], (nodes.FromImportNode, nodes.ImportNode)):
            if not find_import(el_right.parent, stack_left[0]):
                logging.debug("%s import to remove %r", indent+INDENT,
                              short_display_el(stack_left[0]))
                diff += [RemoveEls([stack_left[0]],
                                   context=gather_context(stack_left[0]))]
                stack_left.pop(0)

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


COMPUTE_DIFF_ITERABLE_CALLS = {
    nodes.DefNode: diff_def_node,
    nodes.ClassNode: diff_class_node,
    nodes.AtomtrailersNode: diff_atom_trailer_node,
    nodes.FromImportNode: diff_from_import_node,
}
