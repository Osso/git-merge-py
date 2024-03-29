from itertools import islice
import logging

from redbaron import nodes
from redbaron.utils import indent_str

from .actions import (AddChangeEl,
                      AddEls,
                      ChangeEl,
                      ChangeIndentation,
                      RemoveEls,
                      RemoveWith,
                      Replace,
                      ReplaceAttr,
                      ReplaceEls,
                      SameEl)
from .context import (gather_after_context,
                      gather_context)
from .matcher import (code_block_similarity,
                      find_el_strong,
                      same_el_guess)
from .tools import (INDENT,
                    empty_lines,
                    same_el,
                    short_context,
                    short_display_el)
from .tools_actions import remove_with

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
        logging.debug('%s diff_one %s', indent+INDENT, type(left).__name__)
        diff += COMPUTE_DIFF_ONE_CALLS[type(left)](left, right, indent+INDENT)

        # Compare formatting
        diff += compare_formatting(left, right)

    logging.debug('%s diff =', indent)
    for d in diff:
        logging.debug(indent_str(repr(d), indent+"."))

    return diff


def changed_el(el, stack_left, indent, change_class):
    diff = []
    el_diff = compute_diff(stack_left[0], el, indent=indent+INDENT)
    stack_el = stack_left.pop(0)

    if el_diff:
        diff += [change_class(stack_el, el_diff, context=gather_context(el))]

    return diff


def simplify_to_add_to_remove(to_add, to_remove):
    # Simplify if possible
    while to_add and to_remove and same_el(to_add[0], to_remove[0]):
        del to_add[0]
        del to_remove[0]


def append_replace(diff, to_add, to_remove, indent):
    if to_remove and to_add:
        # Transform add+remove into a ReplaceEls
        logging.debug("%s transforming into replace", indent)
        replace = ReplaceEls(to_add=to_add, to_remove=to_remove,
                             context=diff[-1].context)
        diff.pop()
        diff.append(replace)
    elif to_remove:
        logging.debug("%s removing empty AddEls", indent)
        remove = RemoveEls(to_remove=to_remove, context=diff[-1].context)
        diff.pop()
        diff.append(remove)
    elif not to_add:
        logging.debug("%s removing empty AddEls", indent)
        diff.pop()


def __remove_or_replace(diff, els, indent, ignore_context=False):
    assert els
    context = gather_context(els[0])

    for el in els:
        if el.already_processed:
            assert False, "checking that this never happens"

    if diff and isinstance(diff[-1], AddEls):
        to_add = diff[-1].to_add
        to_remove = els
        simplify_to_add_to_remove(to_add, to_remove)
        append_replace(diff, to_add, to_remove, indent=indent+INDENT)

    else:
        diff += __remove(els, context=context, indent=indent+INDENT)


def __remove(els, context, indent):
    logging.debug("%s remove els %r", indent,
                  ", ".join(short_display_el(el) for el in els))

    if len(els) == 1:
        el = els[0]
        comment_before_function = detect_comment_before_function(el)
        if comment_before_function is not None:
            context = gather_after_context(comment_before_function)
            logging.debug("%s after context %r", indent, short_context(context))
            return [RemoveEls([el], context=context)]

    logging.debug("%s context %r", indent, short_context(context))
    return [RemoveEls(els, context=context)]


def _remove_or_replace(diff, els, indent):
    els = split_diff_if_matching_with(diff, els, indent)
    if els:
        __remove_or_replace(diff, els, indent)


def _flush_remove(els, diff, indent):
    if not els:
        return

    _remove_or_replace(diff, list(els), indent=indent)

    del els[:]


def process_stack_till_el(stack_left, stop_el, tree, diff, indent):
    """stop_el is None means continue till the end of the stack"""
    els = []
    while stack_left and not (stop_el and same_el(stack_left[0], stop_el)):
        el = stack_left.pop(0)
        if el.already_processed:
            logging.debug("%s el aready processed %r, flushing", indent+INDENT,
                          short_display_el(el))
            _flush_remove(els, diff=diff, indent=indent)
        else:
            process_stack_el(stack_left=stack_left, el_to_delete=el, tree=tree,
                             els=els, diff=diff, indent=indent)

    _flush_remove(els, diff=diff, indent=indent)


def process_stack_el(stack_left, el_to_delete, tree, els, diff,
                     indent, force_separate=False):
    matching_el_by_id = find_el_strong(tree, target_el=el_to_delete)
    if matching_el_by_id:
        logging.debug("%s marking as found %r", indent+2*INDENT,
                      short_display_el(el_to_delete))
        _flush_remove(els, diff=diff, indent=indent)
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
    logging.debug("%s same el %r", indent,
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


def check_for_with_first_element(with_node, start_el):
    assert start_el
    code_block = start_el.parent.make_code_block(start=start_el,
                                                 length=len(with_node))
    return any([same_el(with_node[0], el) for el in code_block[1:5]])


def score_removed_with(with_node, start_el, indent):
    """Check for removal of with node + shifting of content"""
    assert isinstance(with_node, nodes.WithNode)

    if start_el is None:
        return 0

    if isinstance(start_el, nodes.WithNode):
        return 0

    if check_for_with_first_element(with_node, start_el):
        return 0

    return compare_with_code(with_node, start_el=start_el)


def process_removed_with(stack_left, i, start_el, diff, indent):
    logging.debug("%s with node removal %r", indent+INDENT,
                  short_display_el(stack_left[i]))
    process_stack_till_el(stack_left, stack_left[i], start_el.parent,
                          diff, indent)
    with_node = stack_left.pop(0)
    added_els = remove_with(with_node)
    stack_left[:] = added_els + stack_left
    return [RemoveWith(with_node, context=gather_context(start_el))]


def check_removed_withs(stack_left, el_right, indent, diff, max_ahead=10):
    if isinstance(el_right, nodes.EmptyLineNode):
        return []
    if look_ahead(stack_left, el_right):
        return []

    for i in range(max_ahead):
        if not stack_left[i:]:
            break
        if isinstance(stack_left[i], nodes.WithNode):
            with_node = stack_left[i]
            score = score_removed_with(with_node, el_right, indent)
            if score < score_removed_with(with_node, el_right.next, indent):
                return []
            if score < 0.6:
                return []

            return process_removed_with(stack_left, i, el_right,
                                        diff=diff, indent=indent)

    return []


def look_ahead(stack_left, el_right, max_ahead=10, compare_fun=same_el_guess):
    if empty_lines([el_right]):
        return None

    for el in islice(stack_left, 0, max_ahead):
        if compare_fun(el, el_right):
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


def compare_with_code(with_node, start_el):
    code_block = start_el.parent
    code_block_to_compare = code_block.make_code_block(start=start_el,
                                                       length=len(with_node))
    return code_block_similarity(with_node.value, code_block_to_compare)


def look_for_with(with_node, code_block):
    with_node_copy = with_node.copy()
    with_node_copy.decrease_indentation()

    best_score = 0
    best_score_el = None
    for el in code_block:
        el_score = compare_with_code(with_node_copy, start_el=el)
        if el_score > best_score:
            best_score = el_score
            best_score_el = el
    if best_score > 0.6:
        return best_score_el
    return None


def look_for_with_in_diff(with_node, diff):
    if not diff:
        return None
    if not isinstance(diff[-1], (AddEls, ReplaceEls)):
        return None
    return look_for_with(with_node, code_block=diff[-1].to_add)


def _split_diff_on_with(with_node, to_remove, diff, start_el, indent):
    logging.debug("%s transforming into RemoveWith", indent+INDENT)
    with_node_copy = with_node.copy()
    with_node_copy.decrease_indentation()
    with_els = with_node_copy.value
    diff_el = diff[-1]
    is_replace = isinstance(diff_el, ReplaceEls)
    # Trim the to_add
    start_el_index = diff_el.to_add.index(start_el)
    head_els = diff_el.to_add[:start_el_index]
    new_els = diff_el.to_add[start_el_index:start_el_index+len(with_els)]
    tail_els = diff_el.to_add[start_el_index+len(with_els):]
    diff_el.to_add[:] = head_els
    # Remove AddEls/ReplaceEls if empty
    if not diff_el.to_add:
        del diff[-1]
        is_replace = False
    # Trim or add the to_remove
    if to_remove:
        if is_replace:
            diff[-1].to_remove = list(to_remove)
        else:
            __remove_or_replace(diff, to_remove, indent)

    diff += [RemoveWith(with_node, gather_context(with_node))]
    diff += compute_diff_iterables(with_els, new_els)
    if tail_els:
        diff += [AddEls(tail_els, context=gather_context(tail_els[0]))]


def split_diff_if_matching_with(diff, to_remove, indent):
    if not diff or not isinstance(diff[-1], AddEls):
        return to_remove

    els = []
    for el in to_remove:
        if isinstance(el, nodes.WithNode):
            with_node = el
            with_start_el = look_for_with_in_diff(with_node, diff)
            if with_start_el:
                _split_diff_on_with(with_node=with_node, to_remove=els,
                                    diff=diff, start_el=with_start_el,
                                    indent=indent+INDENT)
                els = []
                continue
        els.append(el)

    return els


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

        # Handle new els at the end
        if not stack_left:
            assert not hasattr(el_right, 'matched_el')
            logging.debug("%s stack left empty, new el %r", indent+INDENT,
                          short_display_el(el_right))
            add_to_diff(diff, el_right, last_added=last_added, indent=indent)
            continue

        # Pre-processing
        if not same_el(stack_left[0], el_right):
            # Handle removed withs
            diff += check_removed_withs(stack_left, el_right, indent=indent,
                                        diff=diff)

        # Actual processing

        # Direct match
        if same_el(stack_left[0], el_right):
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
        # also look ahead in right stack to double check that there isn't an
        # easier solution by adding elements
        elif (look_ahead(stack_left, el_right) and
                  not look_ahead(el_right.next_neighbors, stack_left[0],
                                 max_ahead=3, compare_fun=same_el)):
            logging.debug("%s same el ahead %r", indent+INDENT,
                          short_display_el(el_right))
            stop_el = look_ahead(stack_left, el_right)
            process_stack_till_el(stack_left=stack_left, stop_el=stop_el,
                                  tree=right, diff=diff,
                                  indent=indent+INDENT)
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


def add_to_diff(diff, el, last_added=False, indent="", changes=None):
    comment_before_function = detect_comment_before_function(el)
    if comment_before_function is not None:
        assert not changes
        context = gather_after_context(comment_before_function)
        logging.debug("%s after context %r", indent, short_context(context))
        diff += [AddEls([el], context=context)]
    elif diff and isinstance(diff[-1], AddEls) and last_added:
        diff[-1].add_el(el)
    else:
        context = gather_context(el)
        after_context = gather_after_context(el)
        logging.debug("%s context %r", indent, short_context(context))
        if changes:
            diff += [AddChangeEl(el, changes=changes,
                                 context=context, after_context=after_context)]
        else:
            diff += [AddEls([el], context=context, after_context=after_context)]


def diff_indent(left, right):
    assert not isinstance(left, nodes.NodeList)
    assert not isinstance(right, nodes.NodeList)

    diff = []
    if left.indentation != right.indentation:
        delta = len(right.indentation) - len(left.indentation)
        diff += [ChangeIndentation(delta)]

    return diff
