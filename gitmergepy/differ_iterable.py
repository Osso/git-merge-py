import logging

from redbaron import nodes

from .context import gather_context
from .differ import (add_to_diff,
                     compute_diff)
from .matcher import (find_func,
                      find_import)
from .tools import (INDENT,
                    id_from_el,
                    short_display_el)
from .tree import (AddImports,
                   ChangeClass,
                   ChangeFun,
                   ChangeImport,
                   MoveFunction,
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

    # We have encountered a function
    if isinstance(stack_left[0], nodes.DefNode) and stack_left[0].name == el_right.name:
        # Function has not been moved
        logging.debug("%s not moved", indent+INDENT)
        diff += _changed_el(el_right, stack_left, indent=indent,
                            context_class=ChangeFun)
    else:
        # Function has been moved, look for it
        el = find_func(stack_left, el_right)
        if el:
            logging.debug("%s moved fun %r", indent+INDENT, el_right.name)
            el_diff = compute_diff(el, el_right, indent=indent+2*INDENT)
            context = gather_context(el_right)
            stack_left.remove(el)
            diff += [MoveFunction(el, changes=el_diff, context=context)]
        else:
            if isinstance(stack_left[0], nodes.DefNode) and el_right.parent:
                el = find_func(el_right.parent, stack_left[0])
                if el:
                    # stack_left[0] is defined somewhere else
                    # we are not modifying it
                    logging.debug("%s new fun %r", indent+INDENT, el_right.name)
                    add_to_diff(diff, el_right, indent+2*INDENT)
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
            else:
                logging.debug("%s new fun %r", indent+INDENT, el_right.name)
                add_to_diff(diff, el_right, indent+2*INDENT)
    return diff


def diff_class_node(stack_left, el_right, indent, context_class):
    logging.debug("%s changed class %r", indent,
                  short_display_el(el_right))
    diff = []

    if isinstance(stack_left[0], nodes.ClassNode) and stack_left[0].name == el_right.name:
        # Class has not been moved
        logging.debug("%s not moved", indent+INDENT)
        diff += _changed_el(el_right, stack_left, indent=indent,
                            context_class=ChangeClass)
    else:
        logging.debug("%s new class %r", indent+INDENT, el_right.name)
        add_to_diff(diff, el_right, indent+2*INDENT)

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
        add_to_diff(diff, el_right, indent+2*INDENT)

    return diff


def diff_from_import_node(stack_left, el_right, indent, context_class):
    logging.debug("%s changed import %r", indent, short_display_el(el_right))
    diff = []

    def remove_import_if_not_found(stack):
        nonlocal diff
        # Try to keep in left and right stacks in sync, so that empty lines
        # can also be matched
        if isinstance(stack_left[0], (nodes.FromImportNode, nodes.ImportNode)):
            if not find_import(el_right.parent, stack_left[0]):
                logging.debug("%s import to remove %r", indent+INDENT,
                              short_display_el(stack_left[0]))
                diff += [RemoveEls([stack_left[0]],
                                   context=gather_context(stack_left[0]))]
                stack_left.pop(0)

    el = find_import(stack_left, el_right)
    if el:
        el_diff = compute_diff(el, el_right, indent=indent+INDENT)
        if el_diff:
            diff += [ChangeImport(el, el_diff, context=gather_context(el))]

        if el is stack_left[0]:
            stack_left.pop(0)
        else:
            stack_left.remove(el)
            remove_import_if_not_found(stack_left)

    else:
        # new import
        logging.debug("%s new import %r", indent+INDENT, id_from_el(el_right))
        diff += [ChangeImport(el_right, changes=[AddImports(el_right.targets)],
                              context=gather_context(el_right))]
        remove_import_if_not_found(stack_left)

    return diff


COMPUTE_DIFF_ITERABLE_CALLS = {
    nodes.DefNode: diff_def_node,
    nodes.ClassNode: diff_class_node,
    nodes.AtomtrailersNode: diff_atom_trailer_node,
    nodes.FromImportNode: diff_from_import_node,
}
