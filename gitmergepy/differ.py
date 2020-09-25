import logging

from redbaron import nodes

from .matcher import (find_func,
                      gather_context,
                      guess_if_same_el,
                      same_el)
from .tools import (INDENT,
                    LAST,
                    get_call_el,
                    is_iterable,
                    short_display_el)
from .tree import (AddEls,
                   ChangeEl,
                   ChangeFun,
                   MoveFunction,
                   RemoveEls,
                   RemoveWith,
                   Replace)


def compute_diff_one(left, right, indent=""):
    from .differ_calls import COMPUTE_DIFF_ONE_CALLS

    if left.dumps() == right.dumps():
        logging.debug('%s compute_diff_one %s = %s', indent,
                      type(left).__name__, type(right).__name__)
        logging.debug('%s compute_diff_one %s = %s', indent,
                      short_display_el(left), short_display_el(right))
        return []

    logging.debug('%s compute_diff_one %s != %s', indent,
                  type(left).__name__, type(right).__name__)
    logging.debug('%s compute_diff_one %s != %s', indent,
                  short_display_el(left), short_display_el(right))

    if type(left) != type(right):  # pylint: disable=unidiomatic-typecheck
        diff = [Replace(right)]
    elif type(left) in COMPUTE_DIFF_ONE_CALLS:  # pylint: disable=unidiomatic-typecheck
        diff = COMPUTE_DIFF_ONE_CALLS[type(left)](left, right, indent)
    else:
        # Unhandled
        diff = []

    logging.debug('%s compute_diff_one %r', indent, diff)
    return diff


def compute_diff(left, right, indent=""):
    # type: (NodeType, NodeType, Optional[Dict[str, int]]) -> None
    """Compare two abstract syntax trees.
    Return `None` if they are equal, and raise an exception otherwise.
    """
    logging.debug("%s compute_diff %r <=> %r", indent,
                  short_display_el(left), short_display_el(right))

    diff = compute_diff_one(left, right, indent=indent+INDENT)
    if is_iterable(left) and not isinstance(left, nodes.AtomtrailersNode):
        assert is_iterable(right)
        diff += compute_diff_iterables(left, right, indent=indent+INDENT)

    logging.debug("%s compute_diff %r", indent, diff)
    return diff


def compute_diff_iterables(left, right, indent="", context_class=ChangeEl):
    logging.debug("%s compute_diff_iterables %r <=> %r", indent, type(left).__name__, type(right).__name__)
    stack_left = list(left)

    def _changed_el(el, stack_left, context_class=context_class):
        diff = []
        el_diff = compute_diff(stack_left[0], el, indent=indent+INDENT)
        stack_left.pop(0)

        if el_diff:
            diff += [context_class(el, el_diff, context=gather_context(el))]

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
            logging.debug("%s with node removal %r", indent+INDENT, short_display_el(stack_left[0]))
            with_node = stack_left.pop(0)
            with_node.decrease_indentation(4)
            stack_left = list(with_node) + stack_left
            diff += [RemoveWith(with_node, context=gather_context(el_right))]

        # Actual processing

        # Direct match
        max_ahead = min(10, len(stack_left))
        if same_el(stack_left[0], el_right):
            # Exactly same element
            logging.debug("%s same el %r", indent+INDENT, el_right.dumps())
            stack_left.pop(0)
        # Look forward a few elements to check if we have a match
        elif any(same_el(stack_left[i], el_right) for i in range(max_ahead)):
            logging.debug("%s same el ahead %r", indent+INDENT, el_right.dumps())
            els = []
            for _ in range(10):
                if not stack_left or same_el(stack_left[0], el_right):
                    break
                els += [stack_left.pop(0)]
                logging.debug("%s removing %r", indent+INDENT, els[-1].dumps())
            stack_left.pop(0)
            diff += [RemoveEls(els, context=gather_context(el_right))]
        elif isinstance(el_right, nodes.DefNode):
            logging.debug("%s changed fun %r", indent+INDENT, type(el_right).__name__)
            # We have encountered a function
            if isinstance(stack_left[0], nodes.DefNode) and stack_left[0].name == el_right.name:
                # Function has not been moved
                logging.debug("%s not moved fun %r", indent+INDENT, el_right.name)
                diff += _changed_el(el_right, stack_left,
                                    context_class=ChangeFun)
            else:
                # Function has been moved, look for it
                el = find_func(stack_left, el_right)
                if el:
                    logging.debug("%s moved fun %r", indent+INDENT, el_right.name)
                    el_diff = compute_diff(el, el_right, indent=indent+2*INDENT)
                    context = gather_context(el_right)
                    stack_left.remove(el)
                    diff += [MoveFunction(el, changes=el_diff,
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
            logging.debug("%s changed el %r", indent+INDENT, type(el_right).__name__)
            diff += _changed_el(el_right, stack_left)
        else:
            logging.debug("%s new el %r", indent+INDENT, el_right.dumps())
            add_to_diff(diff, el_right)

    if stack_left:
        for el in stack_left:
            logging.debug("%s removing leftover %r", indent+INDENT, short_display_el(el))
        diff += [RemoveEls(stack_left, context=LAST)]

    logging.debug("%s compute_diff_iterables %r", indent, diff)
    return diff


def add_to_diff(diff, el):
    if diff and isinstance(diff[-1], AddEls):
        diff[-1].add_el(el)
    else:
        diff += [AddEls([el], context=gather_context(el))]
