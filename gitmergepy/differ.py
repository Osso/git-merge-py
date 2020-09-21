import logging

from redbaron import nodes

from .matcher import (find_func,
                      gather_context,
                      guess_if_same_el,
                      same_el)
from .tools import (changed_list,
                    diff_list,
                    get_call_el,
                    is_iterable)
from .tree import (AddAllDecoratorArgs,
                   AddCallArg,
                   AddDecorator,
                   AddEl,
                   AddFunArg,
                   AddImports,
                   ChangeArgDefault,
                   ChangeAssignmentNode,
                   ChangeAtomtrailersCall,
                   ChangeAttr,
                   ChangeCallArgValue,
                   ChangeDecorator,
                   ChangeDecoratorArgValue,
                   ChangeEl,
                   ChangeFun,
                   ChangeValue,
                   MoveFunction,
                   NoDefault,
                   RemoveAllDecoratorArgs,
                   RemoveCallArgs,
                   RemoveDecorators,
                   RemoveEls,
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
        # Name
        if left.name != right.name:
            diff += [ChangeAttr('name', right.name)]
        # Args
        to_add, to_remove = diff_list(left.arguments, right.arguments,
                                      key_getter=lambda t: t.name.value)
        logging.debug('%s diff fun new args %r old args %r', indent, to_add, to_remove)
        for arg in to_add:
            diff += [AddFunArg(arg.copy(), context=gather_context(arg))]
        if to_remove:
            diff += [RemoveFunArgs(to_remove)]

        changed = changed_list(left.arguments, right.arguments,
                               key_getter=lambda t: t.name.value,
                               value_getter=lambda t: t.value.value if t.value else NoDefault)
        diff += [ChangeArgDefault(el.copy()) for _, el in changed]
        # Decorators
        to_add, to_remove = diff_list(left.decorators, right.decorators,
                                      key_getter=lambda t: t.name.value)
        for decorator in to_add:
            diff += [AddDecorator(decorator.copy(),
                                  context=gather_context(decorator))]
        if to_remove:
            diff += [RemoveDecorators(to_remove)]
        logging.debug('%s diff fun new decorators %r old decorators %r', indent, to_add, to_remove)
        changed = changed_list(left.decorators, right.decorators,
                               key_getter=lambda t: t.name.value,
                               value_getter=lambda t: t.dumps())
        for left_el, right_el in changed:
            diff_decorator = []
            if left_el.call and right_el.call:
                diff_decorator += [ChangeDecoratorArgValue(el) for el in changed]
            elif left_el.call:
                logging.debug('%s diff fun remove decorators %r old decorators %r', indent, to_add, to_remove)
                diff_decorator += [RemoveAllDecoratorArgs(right_el)]
            elif right_el.call:
                diff_decorator += [AddAllDecoratorArgs(right.call)]
            if diff_decorator:
                diff += [ChangeDecorator(left, changes=diff_decorator)]
        logging.debug('%s diff fun changed decorators %r', indent, changed)
    elif isinstance(left, nodes.FromImportNode):
        to_add, to_remove = diff_list(left.targets, right.targets,
                                      key_getter=lambda t: t.value)
        diff += create_add_remove(AddImports, to_add,
                                  RemoveImports, to_remove)
    elif isinstance(left, nodes.WithNode):
        if left.contexts.dumps() != right.contexts.dumps():
            diff += [ChangeAttr('contexts', right.contexts.copy())]
    elif isinstance(left, nodes.AtomtrailersNode):
        call_el_left = get_call_el(left)
        call_el_right = get_call_el(right)
        el_diff = compute_diff_one(call_el_left, call_el_right,
                                   indent=indent+INDENT)
        if el_diff:
            diff += [ChangeAtomtrailersCall(call_el_left, changes=el_diff)]
    elif isinstance(left, nodes.CallNode):
        to_add, to_remove = diff_list(left, right,
                                      key_getter=lambda t: t.name.value)
        logging.debug('%s diff call new args %r old args %r', indent, to_add, to_remove)
        for arg in to_add:
            diff += [AddCallArg(arg.copy(), context=gather_context(arg))]
        if to_remove:
            diff += [RemoveCallArgs(to_remove)]

        changed = changed_list(left, right,
                               key_getter=lambda t: t.name.value,
                               value_getter=lambda t: t.value.value if t.value else NoDefault)
        diff += [ChangeCallArgValue(el.copy()) for _, el in changed]
    elif isinstance(left, nodes.AssignmentNode):
        if left.name.value != right.name.value:
            diff += [ChangeAttr('name', right.name)]

        el_diff = compute_diff_one(left.value, right.value,
                                   indent=indent+INDENT)
        if el_diff:
            diff += [ChangeAssignmentNode(left, changes=el_diff)]

    logging.debug('%s compute_diff_one %r', indent, diff)
    return diff


def create_add_remove(to_add_class, to_add, to_remove_class, to_remove):
    diff = []
    if to_add:
        diff += [to_add_class([el.copy() for el in to_add])]
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
            diff += [context_class(el, el_diff, context=gather_context(el))]
            previous_el = el_left

        return diff

    diff = []
    for el_right in right:
        if not stack_left:
            logging.debug("%s stack_left empty, new el %r", indent+INDENT, type(el_right).__name__)
            add_to_diff(diff, el_right)
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
                            add_to_diff(diff, el_right)
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
                        add_to_diff(diff, el_right)
        elif isinstance(el_right, nodes.ClassNode):
            logging.debug("%s changed class %r", indent+INDENT, type(el_right).__name__)
            # We have encountered a function
            if isinstance(stack_left[0], nodes.ClassNode) and stack_left[0].name == el_right.name:
                # Class has not been moved
                logging.debug("%s not moved class %r", indent+INDENT, el_right.name)
                diff += _changed_el(el_right, stack_left)
            else:
                logging.debug("%s new class %r", indent+INDENT, el_right.name)
                add_to_diff(diff, el_right)
        elif isinstance(el_right, nodes.AtomtrailersNode):
            if get_call_el(el_right):
                logging.debug("%s modified call %r", indent+INDENT, el_right.name)
                el_left = stack_left.pop(0)
                el_diff = compute_diff_one(el_left, el_right, indent=indent+INDENT)
                if el_diff:
                    diff += [context_class(el_left, el_diff, context=gather_context(el_left))]
            else:
                logging.debug("%s new AtomtrailersNode %r", indent+INDENT, el_right.name)
                add_to_diff(diff, el_right)
        elif guess_if_same_el(stack_left[0], el_right):
            # previous_el or
            logging.debug("%s changed el %r", indent+INDENT, type(el_right).__name__)
            diff += _changed_el(el_right, stack_left)
        else:
            logging.debug("%s new el %r", indent+INDENT, type(el_right).__name__)
            add_to_diff(diff, el_right)
            previous_el = None

    if stack_left:
        logging.debug("%s compute_diff_iterables removing leftover %r", indent, stack_left)
        diff = [RemoveEls([el], context=gather_context(el)) for el in stack_left] + diff

    logging.debug("%s compute_diff_iterables %r", indent, diff)
    return diff


def add_to_diff(diff, el):
    if diff and isinstance(diff[-1], AddEl):
        diff[-1].add_el(el)
    else:
        diff += [AddEl([el], context=gather_context(el))]
