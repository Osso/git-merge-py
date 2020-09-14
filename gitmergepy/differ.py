import logging

from redbaron import nodes

from .matcher import (find_func,
                      gather_context,
                      guess_if_same_el,
                      same_el)
from .tools import (changed_list,
                    diff_list,
                    is_iterable)
from .tree import (AddEl,
                   AddFunArg,
                   AddImports,
                   ChangeArgDefault,
                   ChangeAttr,
                   ChangeEl,
                   ChangeFun,
                   ChangeValue,
                   MoveFunction,
                   NoDefault,
                   RemoveEl,
                   RemoveFunArgs,
                   RemoveImports,
                   RemoveWith)

VALUES_NODES = (nodes.CommentNode,
                nodes.AssociativeParenthesisNode)
INDENT = "."


def compute_diff_one(left, right, indent=""):

    if left.dumps() == right.dumps():
        logging.debug('%s compute_diff_one %s = %s', indent, type(left).__name__, type(right).__name__)
        return []
    logging.debug('%s compute_diff_one %s != %s', indent, type(left).__name__, type(right).__name__)
    diff = []
    if isinstance(left, VALUES_NODES):
        diff += [ChangeValue(right.value)]
    elif isinstance(left, nodes.DefNode):
        diff = []
        if left.name != right.name:
            diff += [ChangeAttr('name', right.name)]
        to_add, to_remove = diff_list(left.arguments, right.arguments,
                                      key_getter=lambda t: t.name.value)
        logging.debug('%s diff fun new args %r old args %r', indent, to_add, to_remove)
        for arg in to_add:
            diff += [AddFunArg(arg, context=gather_context(arg))]
        if to_remove:
            diff += [RemoveFunArgs(to_remove)]

        changed = changed_list(left.arguments, right.arguments,
                               key_getter=lambda t: t.name.value,
                               value_getter=lambda t: t.value.value if t.value else NoDefault)
        diff += [ChangeArgDefault(el) for el in changed]

        logging.debug('%s diff fun changed args %r', indent, changed)
    elif isinstance(left, nodes.FromImportNode):
        to_add, to_remove = diff_list(left.targets, right.targets,
                                      key_getter=lambda t: t.value)
        diff += create_add_remove(AddImports, to_add,
                                  RemoveImports, to_remove)
    elif isinstance(left, nodes.WithNode):
        if left.contexts.dumps() != right.contexts.dumps():
            diff += [ChangeAttr('contexts', right.contexts.copy())]

    logging.debug('%s compute_diff_one %r', indent, diff)
    return diff


def create_add_remove(to_add_class, to_add, to_remove_class, to_remove):
    diff = []
    if to_add:
        diff += [to_add_class(to_add)]
    if to_remove:
        diff += [to_remove_class(to_remove)]
    return diff


def compute_diff(left, right, indent="", context=None):
    # type: (NodeType, NodeType, Optional[Dict[str, int]]) -> None
    """Compare two abstract syntax trees.
    Return `None` if they are equal, and raise an exception otherwise.
    """
    logging.debug("%s compute_diff %r <=> %r", indent, type(left).__name__, type(right).__name__)

    diff = compute_diff_one(left, right, indent=indent+INDENT)
    if is_iterable(left):
        assert is_iterable(right)
        diff += compute_diff_iterables(left, right, indent=indent+INDENT)

    logging.debug("%s compute_diff %r", indent, diff)
    return diff


def compute_diff_iterables(left, right, indent="", context_class=ChangeEl):
    logging.debug("%s compute_diff_iterables %r <=> %r", indent, type(left).__name__, type(right).__name__)
    stack_left = list(left)
    previous_el = None

    def _changed_el(el, stack_left, context_class=context_class):
        nonlocal previous_el
        diff = []
        el_diff = compute_diff(stack_left[0], el, indent=indent+INDENT)
        el_left = stack_left.pop(0)

        if el_diff:
            diff += [context_class(el_left, el_diff, context=previous_el)]
            previous_el = el_left

        return diff

    diff = []
    for el_right in right:
        if not stack_left:
            logging.debug("%s stack_left empty, new el %r", indent+INDENT, type(el_right).__name__)
            diff += [AddEl(el_right, context=gather_context(el_right))]
            continue

        # Pre-processing
        if isinstance(stack_left[0], nodes.WithNode) and not \
                isinstance(el_right, nodes.WithNode):
            logging.debug("%s with node removal %r", indent+INDENT, stack_left[0].contexts)
            with_node = stack_left.pop(0)
            with_node.decrease_indentation(4)
            stack_left = list(with_node) + stack_left
            diff += [RemoveWith(with_node)]

        # Actual processing
        if same_el(stack_left[0], el_right):
            # Exactly same element
            logging.debug("%s same el %r", indent+INDENT, type(el_right).__name__)
            stack_left.pop(0)
            previous_el = el_right
        elif isinstance(el_right, nodes.DefNode):
            logging.debug("%s changed fun %r", indent+INDENT, type(el_right).__name__)
            # We have encountered a function
            if isinstance(stack_left[0], nodes.DefNode) and stack_left[0].name == el_right.name:
                # Function has not been moved
                logging.debug("%s not moved fun %r", indent+INDENT, el_right.name)
                diff += _changed_el(el_right, stack_left)
            else:
                # Function has been moved, look for it
                el = find_func(stack_left, el_right)
                if el:
                    logging.debug("%s moved fun %r", indent+INDENT, el_right.name)
                    el_diff = compute_diff(el, el_right, indent=indent+2*INDENT)
                    context = gather_context(el_right)
                    stack_left.remove(el)
                    diff += [MoveFunction(el,
                                           changes=el_diff,
                                           context=context)]
                else:
                    if isinstance(stack_left[0], nodes.DefNode):
                        el = find_func(right, stack_left[0])
                        if el:
                            # stack_left[0] is defined somewhere else
                            # we are not modifying it
                            logging.debug("%s new fun %r", indent+INDENT, el_right.name)
                            diff += [AddEl(el_right, context=gather_context(el_right))]
                        else:
                            # stack_left[0] is nowhere else
                            # assume function is modified
                            logging.debug("%s assumed changed fun %r", indent+INDENT, el_right.name)
                            old_name = stack_left[0].name
                            diff_el = _changed_el(el_right, stack_left,
                                                  context_class=ChangeFun)
                            if diff_el:
                                diff_el[0].old_name = old_name
                                diff += diff_el
                    else:
                        logging.debug("%s new fun %r", indent+INDENT, el_right.name)
                        diff += [AddEl(el_right, context=gather_context(el_right))]
        elif isinstance(el_right, nodes.ClassNode):
            logging.debug("%s changed class %r", indent+INDENT, type(el_right).__name__)
            # We have encountered a function
            if isinstance(stack_left[0], nodes.ClassNode) and stack_left[0].name == el_right.name:
                # Class has not been moved
                logging.debug("%s not moved class %r", indent+INDENT, el_right.name)
                diff += _changed_el(el_right, stack_left)
            else:
                logging.debug("%s new class %r", indent+INDENT, el_right.name)
                diff += [AddEl(el_right, context=gather_context(el_right))]
        elif guess_if_same_el(stack_left[0], el_right):
            # previous_el or
            logging.debug("%s changed el %r", indent+INDENT, type(el_right).__name__)
            diff += _changed_el(el_right, stack_left)
        else:
            logging.debug("%s new el %r", indent+INDENT, type(el_right).__name__)
            diff += [AddEl(el_right, context=gather_context(el_right))]
            previous_el = None

    if stack_left:
        logging.debug("%s compute_diff_iterables removing leftover %r", indent, stack_left)
        diff = [RemoveEl(el, context=gather_context(el)) for el in stack_left] + diff

    logging.debug("%s compute_diff_iterables %r", indent, diff)
    return diff
