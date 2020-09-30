from redbaron import nodes

from .tools import (FIRST,
                    get_name_els_from_call,
                    name_els_to_string)

WHITESPACE_NODES = (nodes.EndlNode, )


def guess_if_same_el(left, right):
    if type(left) != type(right):  # pylint: disable=unidiomatic-typecheck
        return False
    if isinstance(left, nodes.DefNode) and left.name == right.name:
        return True
    if isinstance(left, nodes.AtomtrailersNode):
        name_els_left = get_name_els_from_call(left)
        name_els_right = get_name_els_from_call(right)
        return name_els_to_string(name_els_left) == name_els_to_string(name_els_right)
    if isinstance(left, nodes.FromImportNode) and set(m.value for m in left.value) == set(m.value for m in right.value):
        return True
    if isinstance(left, nodes.WithNode):
        return True
    if isinstance(left, nodes.AssignmentNode):
        return left.name.value == right.name.value
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


def match_el_with_context(el, target_el, context, previous_el):
    if type(el) != type(target_el):  # pylint: disable=unidiomatic-typecheck
        return False

    el_dumps = el.dumps()
    target_dumps = target_el.dumps()

    if el_dumps == target_dumps:
        if previous_el is None:
            return True
        previous_el_dumps = previous_el.dumps()
        context_dumps = context[-1].dumps()
        if previous_el_dumps == context_dumps:
            return True

    return False


def match_el_without_context(el, target_el, context, previous_el):
    if type(el) != type(target_el):  # pylint: disable=unidiomatic-typecheck
        return False

    el_dumps = el.dumps()
    target_dumps = target_el.dumps()

    if el_dumps == target_dumps:
        return True

    return False


def match_el_guess(el, target_el, context, previous_el):
    return guess_if_same_el(el, target_el)


def find_el(tree, target_el, context):
    def _find_el(func):
        previous_el = None
        for el in tree:
            if func(el, target_el, context, previous_el):
                return el
            previous_el = el
        return None

    if isinstance(target_el, nodes.DefNode):
        el = find_func(tree, target_el)
        if el:
            return el

    if isinstance(target_el, nodes.ClassNode):
        el = find_class(tree, target_el)
        if el:
            return el

    if context is FIRST:
        index = 0
        while isinstance(tree.node_list[index], nodes.EndlNode) and not isinstance(target_el, nodes.EndlNode):
            index += 1
        if same_el(target_el, tree.node_list[index]):
            el = tree.node_list[index]
        else:
            el = None
    else:
        el = _find_el(match_el_with_context)
    if el:
        return el

    el = _find_el(match_el_without_context)
    if el:
        return el

    el = _find_el(match_el_guess)
    if el:
        return el
    return None


def same_el(left, right):
    return left.dumps() == right.dumps()


def gather_context(el):
    el = el.previous
    context = [el]
    while isinstance(el, WHITESPACE_NODES+(nodes.CommaNode, )):
        el = el.previous
        context.append(el)
    if context[-1] is None:
        return FIRST
    return context


def find_context(tree, target):
    for el in tree:
        if same_el(target, el):
            return el
    return None


def find_with_node(tree):
    for el in tree:
        if isinstance(el, nodes.WithNode):
            return el
    return None
