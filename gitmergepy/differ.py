import logging

from redbaron import nodes

from .matcher import (gather_context,
                      guess_if_same_el,
                      same_el)
from .tools import (INDENT,
                    LAST,
                    short_display_el)
from .tree import (AddEls,
                   ChangeEl,
                   RemoveEls,
                   RemoveWith,
                   Replace)


def compute_diff(left, right, indent=""):
    # type: (NodeType, NodeType, Optional[Dict[str, int]]) -> None
    """Compare two abstract syntax trees.
    Return `None` if they are equal, and raise an exception otherwise.
    """
    from .differ_one import COMPUTE_DIFF_ONE_CALLS

    if left.dumps() == right.dumps():
        # logging.debug('%s compute_diff %s = %s', indent,
        #               type(left).__name__, type(right).__name__)
        logging.debug('%s compute_diff %s = %s', indent,
                      short_display_el(left), short_display_el(right))
        return []

    # logging.debug('%s compute_diff %s != %s', indent,
    #               type(left).__name__, type(right).__name__)
    logging.debug('%s compute_diff %s != %s', indent,
                  short_display_el(left), short_display_el(right))

    if type(left) != type(right):  # pylint: disable=unidiomatic-typecheck
        diff = [Replace(right)]
    elif type(left) in COMPUTE_DIFF_ONE_CALLS:  # pylint: disable=unidiomatic-typecheck
        diff = COMPUTE_DIFF_ONE_CALLS[type(left)](left, right, indent+INDENT)
    else:
        # Unhandled
        logging.warning("unhandled element type %s", type(left))
        diff = []

    logging.debug('%s compute_diff diff=%r', indent, diff)
    return diff


def compute_diff_iterables(left, right, indent="", context_class=ChangeEl):
    from .differ_iterable import COMPUTE_DIFF_ITERABLE_CALLS

    logging.debug("%s compute_diff_iterables %r <=> %r", indent,
                  type(left).__name__, type(right).__name__)
    stack_left = list(left.node_list)

    def _changed_el(el, stack_left, context_class=context_class):
        diff = []
        el_diff = compute_diff(stack_left[0], el, indent=indent+2*INDENT)
        el_left = stack_left.pop(0)

        if el_diff:
            diff += [context_class(el_left, el_diff, context=gather_context(el))]

        return diff

    diff = []
    for el_right in right.node_list:
        if not stack_left:
            logging.debug("%s stack_left empty, new el %r", indent+INDENT,
                          short_display_el(el_right))
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
            logging.debug("%s same el %r", indent+INDENT,
                          short_display_el(el_right))
            stack_left.pop(0)
        # Look forward a few elements to check if we have a match
        elif any(same_el(stack_left[i], el_right) for i in range(max_ahead)):
            logging.debug("%s same el ahead %r", indent+INDENT, el_right.dumps())
            els = []
            for _ in range(10):
                if not stack_left or same_el(stack_left[0], el_right):
                    break
                el = stack_left.pop(0)
                logging.debug("%s removing %r", indent+INDENT,
                              short_display_el(el))
                els.append(el)
            stack_left.pop(0)
            diff += [RemoveEls(els, context=gather_context(el_right))]
        elif type(el_right) in COMPUTE_DIFF_ITERABLE_CALLS:    # pylint: disable=unidiomatic-typecheck
            diff += COMPUTE_DIFF_ITERABLE_CALLS[type(el_right)](stack_left,
                                                                el_right,
                                                                indent+INDENT,
                                                                context_class)
        elif guess_if_same_el(stack_left[0], el_right):
            logging.debug("%s changed el %r", indent+INDENT,
                          short_display_el(el_right))
            diff += _changed_el(el_right, stack_left)
        else:
            logging.debug("%s new el %r", indent+INDENT,
                          short_display_el(el_right))
            add_to_diff(diff, el_right)

    if stack_left:
        for el in stack_left:
            logging.debug("%s removing leftover %r", indent+INDENT,
                          short_display_el(el))
        diff += [RemoveEls(stack_left, context=LAST)]

    logging.debug("%s compute_diff_iterables %r", indent, diff)
    return diff


def add_to_diff(diff, el):
    if diff and isinstance(diff[-1], AddEls):
        diff[-1].add_el(el)
    else:
        diff += [AddEls([el], context=gather_context(el))]
