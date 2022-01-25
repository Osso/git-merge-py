from collections import namedtuple

from redbaron import nodes
from redbaron.node_mixin import CodeBlockMixin

from Levenshtein import distance as levenshtein

from .tools import (get_call_els,
                    get_name_els_from_call,
                    id_from_el,
                    name_els_to_string,
                    same_el)

MAX_LEVENSHTEIN_DISTANCE = 2
CODE_BLOCK_SIMILARITY_THRESHOLD = 0.5
CODE_BLOCK_SAME_THRESHOLD = 0.8
DICT_SIMILARITY_THRESHOLD = 0.5
ARGS_SIMILARITY_THRESHOLD = 0.6


def find_code_block_with_id(tree, target_el):
    node_type = type(target_el)
    node_id = id_from_el(target_el)
    functions = [f for f in tree if isinstance(f, node_type)]
    matching = [f for f in functions if id_from_el(f) == node_id]
    return best_block(matching, target_el)


def finder_with_rename_handling(tree, target_el, finder):
    most_similar_node = best_block(tree, target_el=target_el)

    if most_similar_node:
        best_match = best_block(target_el.parent, target_el=most_similar_node)
        if best_match and target_el is not best_match:
            most_similar_node = None
    else:  # no best match
        # use node with the same name
        node_with_same_id = finder(tree, target_el)
        if node_with_same_id and not best_block(target_el.parent,
                                                target_el=node_with_same_id):
            most_similar_node = node_with_same_id

    return most_similar_node


def find_func(tree, func_node):
    assert isinstance(func_node, nodes.DefNode)
    return finder_with_rename_handling(tree, target_el=func_node,
                                       finder=find_code_block_with_id)


def find_class(tree, class_node):
    assert isinstance(class_node, nodes.ClassNode)
    return finder_with_rename_handling(tree, target_el=class_node,
                                       finder=find_code_block_with_id)


def find_import(tree, import_node):
    import_types = (nodes.FromImportNode, nodes.ImportNode)
    assert isinstance(import_node, import_types)

    return [el for el in tree if isinstance(el, import_types) and
                              id_from_el(el) == id_from_el(import_node)]


def match_el_with_if_condition(el, target_el, context):
    if not isinstance(el, nodes.IfelseblockNode):
        return False

    el_if = el.value[0]
    assert isinstance(el_if, nodes.IfNode)
    target_el_if = target_el.value[0]
    assert isinstance(target_el_if, nodes.IfNode)

    if el_if.test.dumps() == target_el_if.test.dumps():
        return True

    return False


def find_all(tree, types):
    return [el for el in tree if isinstance(el, types)]


def find_single(tree, types):
    els = find_all(tree, types)

    if len(els) == 1:
        return els[0]

    return None


def same_call_guess(left, right):
    name_els_left = get_name_els_from_call(left)
    name_els_right = get_name_els_from_call(right)
    left_call_string = name_els_to_string(name_els_left)
    right_call_string = name_els_to_string(name_els_right)

    # Same function
    if left_call_string.lower() != right_call_string.lower():
        return False
    # Same number of calls
    if len(get_call_els(left)) != len(get_call_els(right)):
        return False

    # Only one call in parent, we assume it's the same one
    if (left.parent and right.parent and
            len(left.parent.find_all(left.baron_type, recursive=False)) == 1 and
            len(right.parent.find_all(right.baron_type, recursive=False)) == 1):
        return True

    left_args = get_call_els(left)[0]
    right_args = get_call_els(right)[0]
    # If first arg is a string and it's different, probably not the same call
    if (len(left_args) > 0 and len(right_args) > 0 and  # pylint: disable=len-as-condition
            isinstance(left_args[0], nodes.StringNode) and
            left_args[0].dumps() != right_args[0].dumps()):
        return False

    # If second arg is a string and it's different, probably not the same call
    if (len(left_args) > 1 and len(right_args) > 1 and
            isinstance(left_args[1], nodes.StringNode) and
            left_args[0].dumps() == right_args[0].dumps() and
            left_args[1].dumps() != right_args[1].dumps()):
        return False

    # Check arguments similarity
    if args_similarity(get_call_els(left)[0], get_call_els(right)[0]) > ARGS_SIMILARITY_THRESHOLD:
        return True

    return False


def same_el_guess(left, right, context=None):
    if isinstance(left, (nodes.SpaceNode, nodes.EmptyLineNode)):
        return left.dumps() == right.dumps()

    if type(left) != type(right):  # pylint: disable=unidiomatic-typecheck
        return False

    if isinstance(left, (nodes.IfNode, nodes.ElseNode,
                         nodes.EndlNode, nodes.ReturnNode)):
        return True
    if isinstance(left, (nodes.DefNode, nodes.ClassNode)):
        if left.name == right.name:
            return True
        if hasattr(right, 'old_name') and left.name == right.old_name:
            return True
        if hasattr(left, 'old_name') and left.old_name == right.name:
            return True
    if isinstance(left, nodes.AtomtrailersNode):
        return same_call_guess(left, right)
    if isinstance(left, nodes.FromImportNode):
        return set(m.dumps() for m in left.value) == set(m.dumps() for m in right.value)
    if isinstance(left, nodes.AssignmentNode):
        return levenshtein(left.target.dumps(), right.target.dumps()) < MAX_LEVENSHTEIN_DISTANCE
    if isinstance(left, nodes.IfelseblockNode):
        return same_el_guess(left[0], right[0])
    if isinstance(left, nodes.TryNode):
        return code_block_similarity(left.value, right.value) > CODE_BLOCK_SIMILARITY_THRESHOLD
    if isinstance(left, nodes.WithNode):
        if left.contexts.dumps() == right.contexts.dumps():
            return True
        return code_block_similarity(left.value, right.value) > CODE_BLOCK_SIMILARITY_THRESHOLD
    if isinstance(left, (nodes.WhileNode, nodes.ElifNode, nodes.WhileNode)):
        if left.test.dumps() == right.test.dumps():
            return True
        return code_block_similarity(left.value, right.value) > CODE_BLOCK_SIMILARITY_THRESHOLD
    if isinstance(left, nodes.ForNode):
        if left.target.dumps() == right.target.dumps() and left.iterator.dumps() == right.iterator.dumps():
            return True
        return code_block_similarity(left.value, right.value) > CODE_BLOCK_SIMILARITY_THRESHOLD
    if isinstance(left, nodes.DictNode):
        return dict_similarity(left, right) > DICT_SIMILARITY_THRESHOLD
    if isinstance(left, nodes.NumberNode):
        return True

    return same_el(left, right)


def find_el_strong(tree, target_el):
    """Strong matches: match with an id"""
    if isinstance(target_el, nodes.DefNode):
        el = find_func(tree, target_el)
        if el is not None:
            return el

    if isinstance(target_el, nodes.ClassNode):
        el = find_class(tree, target_el)
        if el is not None:
            return el

    if isinstance(target_el, nodes.FromImportNode):
        els = find_import(tree, target_el)
        if els:
            return els[0]

    if isinstance(target_el, nodes.IfNode):
        el = tree[0]
        assert isinstance(el, nodes.IfNode)
        return el

    if isinstance(target_el, nodes.ElseNode):
        el = tree[-1]
        return el if isinstance(el, nodes.ElseNode) else None

    if isinstance(target_el, nodes.ReturnNode):
        el = find_single(tree, nodes.ReturnNode)
        if el is not None:
            return el

    return None


def find_els_exact(tree, target_el, old_tree=False):
    if old_tree:
        def filter(el):
            return not el.new
    else:
        def filter(el):
            return not el.hidden

    return [el for el in tree if same_el(el, target_el) and filter(el)]


def find_el(tree, target_el, context, look_in_old_tree_first=False):
    el = find_el_strong(tree, target_el)
    if el:
        return el

    # Match context
    if context and isinstance(target_el, CodeBlockMixin):
        el = find_best_el_with_context(tree, target_el, context,
                                       look_in_old_tree_first=look_in_old_tree_first)
        if el:
            return el
    else:
        el = find_single_el_with_context(tree, target_el, context,
                                         look_in_old_tree_first=look_in_old_tree_first)
        if el:
            return el

    # Require context for indentation
    if isinstance(target_el, nodes.EndlNode):
        return None

    # Match with exact element
    els = find_els_exact(tree, target_el, old_tree=False)
    if len(els) == 1:
        return els[0]
    els = find_els_exact(tree, target_el, old_tree=True)
    if len(els) == 1:
        return els[0]

    # Start guessing here
    def _find_el(func):
        matches = [el for el in tree if func(el, target_el, context)]
        if len(matches) == 1:
            return matches[0]
        return None

    if isinstance(target_el, nodes.IfelseblockNode):
        el = _find_el(match_el_with_if_condition)
        if el:
            return el

    if isinstance(target_el, CodeBlockMixin):
        el = best_block(tree, target_el)
        if el:
            return el

    el = _find_el(same_el_guess)
    if el:
        return el
    return None


def find_single_el_with_context(tree, target_el, context,
                                look_in_old_tree_first=False):
    matches = [el for el in find_els_with_context(tree, context=context,
                                                  look_in_old_tree_first=look_in_old_tree_first)
               if same_el_guess(el, target_el)]
    if len(matches) == 1:
        return matches[0]
    return None


def find_els_with_context(tree, context, look_in_old_tree_first):
    from .context import (AfterContext,
                          find_context_with_reduction)
    matches = []

    for index in find_context_with_reduction(tree, context=context,
                                             look_in_old_tree_first=look_in_old_tree_first):
        if isinstance(context, AfterContext):
            index -= 1
        if index == len(tree):
            continue
        matches.append(tree[index])

    return matches


def find_best_el_with_context(tree, target_el, context,
                              look_in_old_tree_first=False):
    matches = find_els_with_context(tree, context,
                                    look_in_old_tree_first=look_in_old_tree_first)
    return best_block(matches, target_el)


def best_block(tree, target_el):
    target_el_type = type(target_el)
    Result = namedtuple("Result", ["el", "score"])
    blocks_found = [Result(el, code_block_similarity(target_el, el))
                    for el in tree if isinstance(el, target_el_type)]
    if len(blocks_found) >= 2:
        blocks_found = sorted(blocks_found,
                              key=lambda x: x.score, reverse=True)
        if blocks_found[0].score - blocks_found[1].score > 0.10:
            return blocks_found[0].el

    if len(blocks_found) == 1:
        return blocks_found[0].el

    return None


def code_block_similarity(left, right):
    if isinstance(left, (nodes.DefNode, nodes.ClassNode, nodes.WithNode,
                         nodes.ForNode)):
        left = left.value
        right = right.value
    left_lines = set(line.strip() for line in left.dumps().splitlines()) - set([""])
    right_lines = set(line.strip() for line in right.dumps().splitlines()) - set([""])
    same_lines_count = len(left_lines & right_lines)
    total_lines_count = max(len(left_lines), len(right_lines))
    return same_lines_count / total_lines_count


def dict_similarity(left, right):
    left_lines = set(item.key.dumps() for item in left)
    right_lines = set(item.key.dumps() for item in right)
    same_lines_count = len(left_lines & right_lines)
    total_lines_count = max(len(left_lines), len(right_lines))
    return same_lines_count / total_lines_count


def args_similarity(left, right):
    def simplify_arg(arg):
        if getattr(arg, 'target', None) and arg.target.dumps() == arg.value.dumps():
            return arg.value.dumps()
        return arg.dumps().strip()

    left_args = set(simplify_arg(arg) for arg in left)
    right_args = set(simplify_arg(arg) for arg in right)

    same_args_count = len(left_args & right_args)
    args_count = max(len(left_args), len(right_args))
    if args_count == 0:
        return 1
    return same_args_count / args_count


def find_key(key_node, dict_node):
    key_str = key_node.dumps()

    for dict_item in dict_node.value:
        if dict_item.key.dumps() == key_str:
            return dict_item

    return None


def same_arg_guess(left, right):
    if left.target:
        return left.target.dumps() == right.target.dumps()
    return same_el(left.value, right.value)
