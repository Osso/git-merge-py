from redbaron import nodes

from .tools import (AfterContext,
                    get_name_els_from_call,
                    iter_coma_list,
                    match_after_context,
                    match_before_context,
                    name_els_to_string,
                    same_el,
                    short_display_el,
                    skip_context_endl)


def guess_if_same_el(left, right):
    if type(left) != type(right):  # pylint: disable=unidiomatic-typecheck
        return False

    if isinstance(left, nodes.WithNode):
        return True
    if isinstance(left, (nodes.IfelseblockNode, nodes.IfNode)):
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

    return False


def find_el(tree, target_el, context):
    def _find_el(func):
        for el in tree.node_list:
            if func(el, target_el, context):
                return el
        return None

    # Strong matches: match with an id
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

    # Match with exact element + context
    if isinstance(context, AfterContext):
        if context[-1] is None:
            index = len(tree.node_list) - len(context)
            if match_after_context(tree, index, context):
                return tree.node_list[index]
        else:
            el = find_el_with_context(tree, target_el, context)
            if el:
                return el
    else:
        if context[-1] is None:
            if isinstance(target_el, nodes.EndlNode):
                index = len(context) - 1
                if match_before_context(tree, index, context):
                    return tree.node_list[index]
            else:
                # We can have a less strict match
                index = skip_context_endl(tree, context)
                el = tree.node_list[index]
                if same_el(target_el, el):
                    return el
        else:
            el = find_el_with_context(tree, target_el, context)
            if el:
                return el

    # Require context for indentation
    if isinstance(target_el, nodes.EndlNode):
        return None

    # Match with exact element
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


def find_context(tree, context, node_list_workaround=True):
    nodes_list = tree
    if node_list_workaround:
        nodes_list = tree.node_list

    for index in range(len(nodes_list) + 1):
        if context.match(tree, index,
                         node_list_workaround=node_list_workaround):
            return index
    return None


def find_context_coma_list(tree, context):
    for index, el in enumerate(iter_coma_list(tree)):
        if same_el(el, context[-1]):
            return index + 1
    return None


def find_with_node(tree):
    for el in tree:
        if isinstance(el, nodes.WithNode):
            return el
    return None


def find_el_with_context(tree, target_el, context):
    for el in tree.node_list:
        index = tree.node_list.index(el)
        if same_el(el, target_el) and context.match(tree, index):
            return el
    return None
