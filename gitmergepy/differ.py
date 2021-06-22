import logging

from redbaron import nodes

from .context import (gather_after_context,
                      gather_context)
from .matcher import (CODE_BLOCK_SAME_THRESHOLD,
                      code_block_similarity,
                      find_el_strong,
                      guess_if_same_el_for_diff_iterable,
                      same_el_guess)
from .tools import (INDENT,
                    same_el,
                    short_context,
                    short_display_el)
from .tree import (AddEls,
                   ChangeEl,
                   ChangeIndentation,
                   RemoveEls,
                   RemoveWith,
                   Replace,
                   ReplaceAttr,
                   ReplaceEls)


def compare_formatting(left, right):
    diff = []
    names = ('first_formatting', 'second_formatting',
             'third_formatting', 'fourth_formatting')
    for name in names:
        if getattr(left, name).fst() != getattr(right, name).fst():
            diff += [ReplaceAttr(name, getattr(right, name).copy())]
    return diff


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

    # Compare formatting
    diff += compare_formatting(left, right)

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


def _remove_or_replace(diff, els, context, indent, force_separate):
    if not force_separate and diff and isinstance(diff[-1], AddEls) and \
            same_el(diff[-1].context[0], context[0]):
        # Transform add+remove into a ReplaceEls
        logging.debug("%s transforming into replace", indent+INDENT)
        replace = ReplaceEls(to_add=diff[-1].to_add, to_remove=els,
                             context=diff[-1].context)
        diff.pop()
        diff.append(replace)
    else:
        logging.debug("%s remove els %r, context %r", indent+INDENT, els,
                      context)
        diff.append(RemoveEls(els, context=context))


def check_removed_withs(stack_left, el_right, indent):
    """Check for removal of with node + shifting of content"""
    if (stack_left and
            isinstance(stack_left[0], nodes.WithNode) and
            not isinstance(el_right, nodes.WithNode)):
        orig_with_node = stack_left[0]
        with_node = orig_with_node.copy()
        with_node.decrease_indentation()

        lines_in_with = len(stack_left[0])
        code_block_to_compare = el_right.parent.make_code_block(start=el_right, length=lines_in_with)

        if code_block_similarity(with_node.value, code_block_to_compare) > 0.6:
            logging.debug("%s with node removal %r", indent+INDENT,
                          short_display_el(stack_left[0]))
            del stack_left[0]
            stack_left[:] = list(with_node) + stack_left
            return [RemoveWith(orig_with_node,
                               context=gather_context(el_right))]

    return []


def compute_diff_iterables(left, right, indent="", context_class=ChangeEl):
    from .differ_iterable import COMPUTE_DIFF_ITERABLE_CALLS

    logging.debug("%s compute_diff_iterables %r <=> %r", indent,
                  type(left).__name__, type(right).__name__)
    stack_left = list(left)

    diff = []
    last_added = False
    node_types_that_can_be_found_by_id = (nodes.DefNode,
                                          nodes.ClassNode,
                                          nodes.FromImportNode)

    for el_right in right:
        # Pre-processing
        diff += check_removed_withs(stack_left, el_right, indent=indent)
        # Handle the case of an element we can know it is deleted thanks to
        # to find_el_strong
        while stack_left and isinstance(stack_left[0], node_types_that_can_be_found_by_id):
            # Check to see if element has been moved
            if find_el_strong(right, stack_left[0], None):
                break
            # Check to see if element on the same line still exists
            matching_el_by_name = find_el_strong(stack_left, el_right, None)
            if not matching_el_by_name:
                break
            # Double renaming case
            if (
                    # looks the same as element on same line
                    code_block_similarity(el_right, stack_left[0]) > CODE_BLOCK_SAME_THRESHOLD and
                    # looks different than element with same name
                    code_block_similarity(el_right, matching_el_by_name) < CODE_BLOCK_SAME_THRESHOLD):
                break

            logging.debug("%s removing el by id %r", indent+INDENT,
                          short_display_el(stack_left[0]))
            context = gather_context(stack_left[0])
            to_remove = [stack_left.pop(0)]
            while stack_left and isinstance(stack_left[0], (nodes.EmptyLineNode, nodes.SpaceNode)):
                to_remove.append(stack_left.pop(0))
            diff.append(RemoveEls(to_remove,
                                  context=context))
            last_added = False

        if not stack_left:
            logging.debug("%s stack left empty, new el %r", indent+INDENT,
                          short_display_el(el_right))
            add_to_diff(diff, el_right, last_added=last_added, indent=indent)
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
            last_added = False
        # Custom handlers for def, class, etc.
        elif isinstance(el_right, node_types_that_can_be_found_by_id):
            diff += COMPUTE_DIFF_ITERABLE_CALLS[type(el_right)](stack_left,
                                                                el_right,
                                                                indent+INDENT,
                                                                context_class)
            last_added = False
        # Look forward a few elements to check if we have a match
        elif not isinstance(el_right, nodes.EmptyLineNode) and \
               any(same_el_guess(stack_left[i], el_right) for i in range(max_ahead)):
            logging.debug("%s same el ahead %r", indent+INDENT, short_display_el(el_right))
            els = []
            for _ in range(10):
                if not stack_left or same_el_guess(stack_left[0], el_right):
                    break
                el = stack_left.pop(0)

                logging.debug("%s removing %r", indent+INDENT,
                              short_display_el(el))
                els.append(el)
            if same_el(stack_left[0], el_right, discard_indentation=False):
                stack_left.pop(0)
            else:
                diff += _changed_el(el_right, stack_left, indent, context_class)
            if els:
                _remove_or_replace(diff, els, indent=indent,
                                   context=gather_context(els[0]),
                                   force_separate=not last_added)
            last_added = False
        elif guess_if_same_el_for_diff_iterable(stack_left[0], el_right):
            logging.debug("%s changed el %r", indent+INDENT,
                          short_display_el(el_right))
            diff += _changed_el(el_right, stack_left, indent+INDENT,
                                context_class=context_class)
            last_added = False
        else:
            logging.debug("%s new el %r", indent+INDENT,
                          short_display_el(el_right))
            add_to_diff(diff, el_right, last_added=last_added,
                        indent=indent+2*INDENT)
            last_added = True

    if stack_left:
        for el in stack_left:
            logging.debug("%s removing leftover %r", indent+INDENT,
                          short_display_el(el))
        _remove_or_replace(diff, stack_left, indent=indent,
                           context=gather_context(stack_left[0]),
                           force_separate=not last_added)

    # logging.debug("%s compute_diff_iterables %r", indent, diff)
    return diff


def detect_comment_before_function(el):
    comment_before_function = None
    if isinstance(el, nodes.CommentNode):
        n = el
        while isinstance(n.next, nodes.CommentNode):
            n = n.next
        if isinstance(n.next, (nodes.DefNode, nodes.ClassNode)):
            comment_before_function = n

    return comment_before_function


def add_to_diff(diff, el, last_added=False, indent=""):
    comment_before_function = detect_comment_before_function(el)
    if comment_before_function is not None:
        context = gather_after_context(comment_before_function)
        logging.debug("%s after context %r", indent, short_context(context))
        diff += [AddEls([el], context=context)]
    elif diff and isinstance(diff[-1], AddEls) and last_added:
        diff[-1].add_el(el)
    else:
        context = gather_context(el)
        logging.debug("%s context %r", indent, short_context(context))
        diff += [AddEls([el], context=context)]


def diff_indent(left, right):
    assert not isinstance(left, nodes.NodeList)
    assert not isinstance(right, nodes.NodeList)

    diff = []
    if left.indentation != right.indentation:
        delta = len(right.indentation) - len(left.indentation)
        diff += [ChangeIndentation(delta)]

    return diff
