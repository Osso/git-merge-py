from redbaron import nodes

from .tools import (get_name_els_from_call,
                    name_els_to_string,
                    same_el)


def guess_if_same_el(left, right):
    if type(left) != type(right):  # pylint: disable=unidiomatic-typecheck
        return False

    if isinstance(left, nodes.WithNode):
        return True
    if isinstance(left, nodes.IfelseblockNode):
        return True
    if isinstance(left, nodes.EndlNode):
        return True
    if match_el_guess(left, right, None):
        return True

    return False


def find_func(tree, func_node):
    assert isinstance(func_node, nodes.DefNode)

    for el in tree:
        if isinstance(el, nodes.DefNode):
            if func_node.name == el.name:
                return el

    return None


def find_class(tree, class_node):
    assert isinstance(class_node, nodes.ClassNode)

    for el in tree:
        if isinstance(el, nodes.ClassNode):
            if class_node.name == el.name:
                return el

    return None


def match_el_without_context(el, target_el, context):
    return same_el(el, target_el)


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


def find_single(tree, types):
    els = [el for el in tree.node_list
           if isinstance(el, types)]

    if len(els) == 1:
        return els[0]

    return None


def match_el_guess(left, right, context):
    if type(left) != type(right):  # pylint: disable=unidiomatic-typecheck
        return False

    if isinstance(left, nodes.DefNode):
        return left.name == right.name
    if isinstance(left, nodes.AtomtrailersNode):
        name_els_left = get_name_els_from_call(left)
        name_els_right = get_name_els_from_call(right)
        return name_els_to_string(name_els_left) == name_els_to_string(name_els_right)
    if isinstance(left, nodes.FromImportNode):
        return set(m.value for m in left.value) == set(m.value for m in right.value)
    if isinstance(left, nodes.AssignmentNode):
        return left.name.value == right.name.value
    if isinstance(left, nodes.WithNode):
        return left.contexts.dumps() == right.contexts.dumps()
    if isinstance(left, (nodes.IfNode, nodes.ElseNode)):
        return True

    return False


def find_el_strong(tree, target_el, context):
    """Strong matches: match with an id"""
    if isinstance(target_el, nodes.DefNode):
        el = find_func(tree, target_el)
        if el:
            return el

    if isinstance(target_el, nodes.ClassNode):
        el = find_class(tree, target_el)
        if el:
            return el

    if isinstance(target_el, nodes.IfNode):
        el = tree.node_list[0]
        assert isinstance(el, nodes.IfNode)
        return el

    if isinstance(target_el, nodes.ElseNode):
        el = tree.node_list[-1]
        return el if isinstance(el, nodes.ElseNode) else None

    return None


def find_el(tree, target_el, context):
    el = find_el_strong(tree, target_el, context)
    if el is not None:
        return el

    # Match full context
    el = find_el_exact_match_with_context(tree, target_el, context)
    if el is not None:
        return el

    # Match context with endl
    smaller_context = context.copy()
    while isinstance(smaller_context[0], nodes.EndlNode):
        del smaller_context[0]
    from .tools import short_context
    import logging
    logging.debug("smaller_context %r", short_context(smaller_context))
    el = find_el_exact_match_with_context(tree, target_el, smaller_context)
    if el is not None:
        return el

    # Require context for indentation
    if isinstance(target_el, nodes.EndlNode):
        return None

    # Match with exact element
    def _find_el(func):
        for el in tree.node_list:
            if func(el, target_el, context):
                return el
        return None

    el = _find_el(match_el_without_context)
    if el:
        return el

    # Start guessing here
    if isinstance(target_el, nodes.IfelseblockNode):
        el = _find_el(match_el_with_if_condition)
        if el:
            return el

        el = find_single(tree, nodes.IfelseblockNode)
        if el:
            return el

    if isinstance(target_el, nodes.WithNode):
        el = find_single(tree, nodes.WithNode)
        if el:
            return el

    el = _find_el(match_el_guess)
    if el:
        return el
    return None


def find_with_node(tree):
    for el in tree:
        if isinstance(el, nodes.WithNode):
            return el
    return None


def find_el_exact_match_with_context(tree, target_el, context):
    for el in tree.node_list:
        if same_el(el, target_el) and context.match_el(tree, el):
            return el
    return None
