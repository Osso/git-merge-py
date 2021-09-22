import logging

from redbaron import nodes

from .context import (gather_after_context,
                      gather_context)
from .matcher import (CODE_BLOCK_SAME_THRESHOLD,
                      code_block_similarity,
                      find_el_strong,
                      same_el_guess)
from .tools import (INDENT,
                    empty_lines,
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
                   ReplaceEls,
                   SameEl)

NODE_TYPES_THAT_CAN_BE_FOUND_BY_ID = (nodes.DefNode,
                                      nodes.ClassNode,
                                      nodes.FromImportNode)


def compare_formatting(left, right):
    diff = []
    names = ('first_formatting', 'second_formatting',
             'third_formatting', 'fourth_formatting')
    for name in names:
        if getattr(left, name).fst() != getattr(right, name).fst():
            diff += [ReplaceAttr(name, getattr(right, name).copy())]
    return diff


def compute_diff(left, right, indent=""):
    from .differ_one import COMPUTE_DIFF_ONE_CALLS

    if left.dumps() == right.dumps():
        logging.debug('%s compute_diff %s = %s', indent,
                      short_display_el(left), short_display_el(right))
        return []

    logging.debug('%s compute_diff %s != %s', indent,
                  short_display_el(left), short_display_el(right))

    diff = diff_indent(left, right)

    if not isinstance(right, type(left)) or type(left) not in COMPUTE_DIFF_ONE_CALLS:  # pylint: disable=unidiomatic-typecheck
        diff = [Replace(new_value=right, old_value=left)]
    else:
        diff += COMPUTE_DIFF_ONE_CALLS[type(left)](left, right, indent+INDENT)

    # Compare formatting
    diff += compare_formatting(left, right)

    logging.debug('%s compute_diff diff=%r', indent, diff)

    return diff


def changed_el(el, stack_left, indent, change_class):
    diff = []
    el_diff = compute_diff(stack_left[0], el, indent=indent+INDENT)
    stack_el = stack_left.pop(0)

    if el_diff:
        diff += [change_class(stack_el, el_diff, context=gather_context(el))]

    return diff


def __remove_or_replace(diff, els, context, indent, force_separate):
    if any(isinstance(el, nodes.WithNode) for el in els):
        force_separate = True

    if not force_separate and diff and isinstance(diff[-1], AddEls) and \
            same_el(diff[-1].context[0], context[0]):
        # Transform add+remove into a ReplaceEls
        logging.debug("%s transforming into replace", indent+INDENT)
        replace = ReplaceEls(to_add=diff[-1].to_add, to_remove=els,
                             context=diff[-1].context)
        diff.pop()
        diff.append(replace)
    else:
        logging.debug("%s remove els %r, context ~%r", indent+INDENT,
                      ", ".join(short_display_el(el) for el in els),
                      short_context(context))
        diff += make_remove_els(els, diff)


def _remove_or_replace(diff, els, context, indent, force_separate):
    _els = []

    for el in els:
        if el.already_processed:
            assert False, "checking that this never happens"
            if _els:
                __remove_or_replace(diff, _els, context, indent, force_separate)
                force_separate = True
                _els = []
        else:
            _els.append(el)

    if _els:
        __remove_or_replace(diff, _els, context, indent, force_separate)


def _flush_remove(els, diff, force_separate, indent):
    if not els:
        return

    _remove_or_replace(diff, els, indent=indent,
                       context=gather_context(els[0]),
                       force_separate=force_separate)
    del els[:]


def process_stack_till_el(stack_left, stop_el, tree, diff,
                          indent, force_separate=False):
    """stop_el is None means continue till the end of the stack"""
    els = []
    while stack_left and not (stop_el and same_el(stack_left[0], stop_el)):
        el = stack_left.pop(0)
        if el.already_processed:
            logging.debug("%s el aready processed %r, flushing", indent+INDENT,
                          short_display_el(el))
            _flush_remove(els, diff=diff, force_separate=force_separate,
                          indent=indent)
            force_separate = True
            continue

        process_stack_el(stack_left=stack_left, el_to_delete=el, tree=tree,
                         els=els, diff=diff, indent=indent)

    _flush_remove(els, diff=diff, force_separate=force_separate, indent=indent)


def process_stack_el(stack_left, el_to_delete, tree, els, diff,
                     indent, force_separate=False):
    matching_el_by_id = find_el_strong(tree, target_el=el_to_delete,
                                       context=[])
    if matching_el_by_id:
        logging.debug("%s marking as found %r", indent+2*INDENT,
                      short_display_el(el_to_delete))
        _flush_remove(els, diff=diff, force_separate=force_separate,
                      indent=indent)
        matching_el_by_id.matched_el = el_to_delete
        matching_el_by_id.already_processed = True
        diff.extend(call_diff_iterable(matching_el_by_id,
                                       stack_left=stack_left,
                                       indent=indent+2*INDENT,
                                       diff=diff))
    else:
        logging.debug("%s removing %r", indent+2*INDENT,
                      short_display_el(el_to_delete))
        els.append(el_to_delete)


def process_same_el(el_right, stack_left, indent):
    logging.debug("%s same el %r", indent+INDENT,
                  short_display_el(el_right))

    if stack_left[0].indentation != el_right.indentation:
        return changed_el(el_right, stack_left, indent=indent,
                           change_class=ChangeEl)

    return [SameEl(stack_left.pop(0))]


def process_matched_el_from_look_ahead(el_right, stack_left, indent):
    if el_right.already_processed:
        return []

    if same_el(stack_left[0], el_right):
        return process_same_el(el_right, stack_left, indent=indent)

    return changed_el(el_right, stack_left, indent=indent+INDENT,
                       change_class=ChangeEl)


def check_removed_withs(stack_left, el_right, indent):
    """Check for removal of with node + shifting of content"""
    if (stack_left and
            isinstance(stack_left[0], nodes.WithNode) and
            not isinstance(el_right, nodes.WithNode)):
        orig_with_node = stack_left[0]
        with_node = orig_with_node.copy()
        with_node.decrease_indentation()

        if match_with(orig_with_node, code_block=el_right.parent,
                               start_el=el_right) > 0.6:
            logging.debug("%s with node removal %r", indent+INDENT,
                          short_display_el(stack_left[0]))
            del stack_left[0]
            stack_left[:] = list(with_node) + stack_left
            return [RemoveWith(orig_with_node,
                               context=gather_context(el_right))]

    return []


def look_ahead(stack_left, el_right, max_ahead=10):
    for el in stack_left[:max_ahead]:
        if same_el_guess(el, el_right):
            return el
    return None


def simplify_white_lines(diff, indent):
    if not diff:
        return

    found = True
    while (isinstance(diff[-1], RemoveEls) and
               isinstance(diff[-1].to_remove[0], nodes.EmptyLineNode) and
               found):
        found = False
        for el in reversed(diff[:-1]):
            if isinstance(el, AddEls) and isinstance(el.to_add[-1], nodes.EmptyLineNode):
                logging.debug("%s simplifying white line el", indent)
                found = True
                el.to_add.pop()
                if not el.to_add:
                    diff.remove(el)
                diff[-1].to_remove.pop(0)
                if not diff[-1].to_remove:
                    diff.pop()
                break
            if not isinstance(el, RemoveEls):
                break


def call_diff_iterable(el, stack_left, indent, diff):
    from .differ_iterable import COMPUTE_DIFF_ITERABLE_CALLS

    return COMPUTE_DIFF_ITERABLE_CALLS[type(el)](stack_left, el, indent,
                                                 global_diff=diff)


def match_with(with_node, code_block, start_el):
    code_block = start_el.parent
    code_block_to_compare = code_block.make_code_block(start=start_el,
                                                       length=len(with_node))
    return code_block_similarity(with_node.value, code_block_to_compare)


def look_for_with(with_node, diff):
    if not diff:
        return None
    if not isinstance(diff[-1], AddEls):
        return None
    best_score = 0
    best_score_el = None
    for el in diff[0].to_add:
        el_score = match_with(with_node, code_block=diff[0].to_add,
                              start_el=el)
        if el_score > best_score:
            best_score = el_score
            best_score_el = el
    if best_score > 0.6:
        return best_score_el
    return None


def _reprocess_add_els(old_els, global_diff, start_el):
    diff_el = global_diff[-2]
    start_el_index = diff_el.to_add.index(start_el)
    head_els = diff_el.to_add[:start_el_index]
    new_els = diff_el.to_add[start_el_index:start_el_index+len(old_els)]
    tail_els = diff_el.to_add[start_el_index+len(old_els):]
    diff_el.to_add[:] = head_els
    if not diff_el.to_add:
        del global_diff[-2]
    diff = compute_diff_iterables(old_els, new_els)
    if tail_els:
        diff += [AddEls(tail_els, context=gather_context(tail_els[0]))]
    return diff


def make_remove_els(els, global_diff):
    """
    Create a RemoveEls(els) but also check for removed withs in els and
    transform the global_diff as appropriate
    """
    assert els

    if not global_diff:
        return [RemoveEls(els, context=gather_context(els[0]))]

    context = None
    diff = [global_diff.pop()]
    head = []
    tail = list(els)
    for el in els:
        if context is None:
            context = gather_context(el)

        if isinstance(el, nodes.WithNode):
            with_node = el.copy()
            with_node.decrease_indentation()
            start_el = look_for_with(with_node, diff)
            if start_el:
                if head:
                    diff += [RemoveEls(head, context=context)]
                diff += [RemoveWith(el, gather_context(el))]
                diff += _reprocess_add_els(old_els=with_node.value,
                                           global_diff=diff,
                                           start_el=start_el)
                head = []
                context = None
                del tail[0]
                continue
        head.append(el)
        del tail[0]
    assert not tail
    if head:
        diff += [RemoveEls(head, context=context)]
    return diff


def compute_diff_iterables(left, right, indent="", context_class=ChangeEl):
    logging.debug("%s compute_diff_iterables %r <=> %r", indent,
                  type(left).__name__, type(right).__name__)
    stack_left = list(left)

    diff = []
    last_added = False

    for el_right in right:
        if el_right.already_processed:
            logging.debug("%s already processed %r", indent+INDENT,
                          short_display_el(el_right))
            last_added = False
            continue

        while stack_left and stack_left[0].already_processed:
            logging.debug("%s already processed in stack %r", indent+INDENT,
                          short_display_el(stack_left[0]))
            last_added = False
            stack_left.pop(0)

        # Pre-processing
        diff += check_removed_withs(stack_left, el_right, indent=indent)
        # Handle the case of an element we can know it is deleted thanks to
        # to find_el_strong
        while stack_left and isinstance(stack_left[0], NODE_TYPES_THAT_CAN_BE_FOUND_BY_ID):
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
                    code_block_similarity(el_right, stack_left[0]) > CODE_BLOCK_SAME_THRESHOLD and  # pylint: disable=chained-comparison
                    # looks different than element with same name
                    code_block_similarity(el_right, matching_el_by_name) < CODE_BLOCK_SAME_THRESHOLD):
                break

            logging.debug("%s removing el by id %r", indent+INDENT,
                          short_display_el(stack_left[0]))
            to_remove = [stack_left.pop(0)]
            while stack_left and isinstance(stack_left[0], (nodes.EmptyLineNode, nodes.SpaceNode)):
                to_remove.append(stack_left.pop(0))
            diff += make_remove_els(to_remove, diff)
            last_added = False

        if not stack_left and not hasattr(el_right, 'matched_el'):
            logging.debug("%s stack left empty, new el %r", indent+INDENT,
                          short_display_el(el_right))
            add_to_diff(diff, el_right, last_added=last_added, indent=indent)
            continue

        # Actual processing

        # Direct match
        if stack_left and same_el(stack_left[0], el_right):
            # Exactly same element
            diff += process_same_el(el_right, stack_left, indent=indent+INDENT)
            last_added = False
        # Custom handlers for def, class, etc.
        elif isinstance(el_right, NODE_TYPES_THAT_CAN_BE_FOUND_BY_ID):
            diff += call_diff_iterable(el_right,
                                       stack_left=stack_left,
                                       indent=indent+INDENT,
                                       diff=diff)
            last_added = False
        # Look forward a few elements to check if we have a match
        elif not empty_lines([el_right]) and look_ahead(stack_left, el_right):
            logging.debug("%s same el ahead %r", indent+INDENT,
                          short_display_el(el_right))
            stop_el = look_ahead(stack_left, el_right)
            process_stack_till_el(stack_left=stack_left, stop_el=stop_el,
                                  tree=right, diff=diff,
                                  indent=indent+INDENT,
                                  force_separate=not last_added)
            diff += process_matched_el_from_look_ahead(el_right=el_right,
                                                       stack_left=stack_left,
                                                       indent=indent+INDENT)
            last_added = False
        elif same_el_guess(stack_left[0], el_right):
            logging.debug("%s changed el %r", indent+INDENT,
                          short_display_el(el_right))
            diff += changed_el(el_right, stack_left, indent+INDENT,
                                change_class=context_class)
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
            if el.already_processed:
                logging.debug("%s already processed", indent+2*INDENT)
        process_stack_till_el(stack_left, stop_el=None, tree=right,
                              diff=diff, indent=indent)

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
