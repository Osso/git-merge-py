import logging

from redbaron import nodes

from .context import (AfterContext,
                      gather_context)
from .matcher import guess_if_same_el
from .tools import (INDENT,
                    same_el,
                    short_context,
                    short_display_el)
from .tree import (AddEls,
                   ChangeEl,
                   ChangeIndentation,
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
        logging.debug('%s compute_diff %s = %s', indent,
                      short_display_el(left), short_display_el(right))
        return []

    logging.debug('%s compute_diff %s != %s', indent,
                  short_display_el(left), short_display_el(right))

    diff = diff_indent(left, right)

    if type(left) != type(right) or type(left) not in COMPUTE_DIFF_ONE_CALLS:  # pylint: disable=unidiomatic-typecheck
        diff = [Replace(new_value=right, old_value=left)]
    else:
        diff += COMPUTE_DIFF_ONE_CALLS[type(left)](left, right, indent+INDENT)

    logging.debug('%s compute_diff diff=%r', indent, diff)
    return diff


def _changed_el(el, stack_left, indent, context_class):
    diff = []
    el_diff = compute_diff(stack_left[0], el, indent=indent+INDENT)
    el_left = stack_left.pop(0)

    if el_diff:
        context = gather_context(el)
        logging.debug("%s context %r", indent,
                      short_context(context))
        diff += [context_class(el_left, el_diff, context=context)]

    return diff


def compute_diff_iterables(left, right, indent="", context_class=ChangeEl):
    from .differ_iterable import COMPUTE_DIFF_ITERABLE_CALLS

    logging.debug("%s compute_diff_iterables %r <=> %r", indent,
                  type(left).__name__, type(right).__name__)
    stack_left = list(left)

    diff = []
    for el_right in right:
        # Pre-processing
        if stack_left and isinstance(stack_left[0], nodes.WithNode) and not \
                isinstance(el_right, nodes.WithNode):
            logging.debug("%s with node removal %r", indent+INDENT, short_display_el(stack_left[0]))
            orig_with_node = stack_left.pop(0)
            with_node = orig_with_node.copy()
            with_node.decrease_indentation()
            stack_left = list(with_node) + stack_left
            diff += [RemoveWith(orig_with_node, context=gather_context(el_right))]

        if not stack_left:
            logging.debug("%s stack left empty, new el %r", indent+INDENT,
                          short_display_el(el_right))
            add_to_diff(diff, el_right, indent)
            continue

        # Actual processing

        max_ahead = min(10, len(stack_left))
        # Direct match
        if same_el(stack_left[0], el_right):
            # Exactly same element
            logging.debug("%s same el %r", indent+INDENT,
                          short_display_el(el_right))
            if stack_left[0].indentation != el_right.indentation:
                diff += _changed_el(el_right, stack_left, indent, context_class)
            else:
                stack_left.pop(0)
        # Custom handlers for def, class, etc.
        elif isinstance(el_right, type(stack_left[0])) and \
                type(el_right) in COMPUTE_DIFF_ITERABLE_CALLS:    # pylint: disable=unidiomatic-typecheck
            diff += COMPUTE_DIFF_ITERABLE_CALLS[type(el_right)](stack_left,
                                                                el_right,
                                                                indent+INDENT,
                                                                context_class)
        # Look forward a few elements to check if we have a match
        elif not isinstance(el_right, nodes.EmptyLineNode) and \
               any(same_el(stack_left[i], el_right) for i in range(max_ahead)):
            logging.debug("%s same el ahead %r", indent+INDENT, short_display_el(el_right))
            els = []
            for _ in range(10):
                if not stack_left or same_el(stack_left[0], el_right):
                    break
                el = stack_left.pop(0)
                diff += diff_indent(el, el_right)

                logging.debug("%s removing %r", indent+INDENT,
                              short_display_el(el))
                els.append(el)
            if stack_left[0].indentation != el_right.indentation:
                diff += _changed_el(el_right, stack_left, indent, context_class)
            else:
                stack_left.pop(0)
            if els:
                diff += [RemoveEls(els, context=gather_context(els[0]))]
        elif guess_if_same_el(stack_left[0], el_right):
            logging.debug("%s changed el %r", indent+INDENT,
                          short_display_el(el_right))
            diff += _changed_el(el_right, stack_left, indent+INDENT,
                                context_class=context_class)
        else:
            logging.debug("%s new el %r", indent+INDENT,
                          short_display_el(el_right))
            add_to_diff(diff, el_right, indent+2*INDENT)

    if stack_left:
        for el in stack_left:
            logging.debug("%s removing leftover %r", indent+INDENT,
                          short_display_el(el))
        diff += [RemoveEls(stack_left, context=AfterContext([None]))]

    # logging.debug("%s compute_diff_iterables %r", indent, diff)
    return diff


def add_to_diff(diff, el, indent):
    if diff and isinstance(diff[-1], AddEls):
        diff[-1].add_el(el)
    else:
        context = gather_context(el)
        logging.debug("%s context %r", indent, short_context(context))
        diff += [AddEls([el], context=context)]


def diff_indent(left, right):
    diff = []
    if left.indentation != right.indentation:
        delta = len(right.indentation) - len(left.indentation)
        diff += [ChangeIndentation(delta)]

    return diff
