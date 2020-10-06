from redbaron import nodes

from .tools import (WHITESPACE_NODES,
                    iter_coma_list,
                    same_el,
                    short_context)


class BeforeContext(list):
    def match(self, tree, index, node_list_workaround=True):
        return match_before_context(tree, index, self,
                                    node_list_workaround=node_list_workaround)


class AfterContext(list):
    def match(self, tree, index, node_list_workaround=True):
        return match_after_context(tree, index, self,
                                   node_list_workaround=node_list_workaround)


def match_before_context(tree, index, context, node_list_workaround=True):
    assert context
    start_index = index - len(context)
    if context[-1] is None:
        start_index += 1
        context = context[:-1]
    if start_index < 0:
        return False

    if node_list_workaround:
        nodes_list = tree.node_list
    else:
        nodes_list = tree
    els = nodes_list[start_index:index]

    if len(els) != len(context):
        return False

    for context_el, el in zip(reversed(context), els):
        if not same_el(context_el, el):
            return False

    return True


def match_after_context(tree, index, context, node_list_workaround=True):
    print('match_after_context', tree.node_list)
    print('index', index)
    print('len(tree)', len(tree.node_list))
    print('context', short_context(context))
    assert context

    if context[-1] is None:
        context = context[:-1]
        if index + len(context) != len(tree.node_list):
            return False

    end_index = index + len(context)
    print('end_index', end_index)

    if node_list_workaround:
        nodes_list = tree.node_list
    else:
        nodes_list = tree
    els = nodes_list[index:end_index]
    print('els', els)

    if len(els) != len(context):
        print('lens differ')
        return False

    for context_el, el in zip(context, els):
        if not same_el(context_el, el):
            print('not same')
            return False

    return True


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


def gather_context(el):
    after_context = gather_after_context(el)
    if after_context[-1] is None:
        return after_context

    el = el.previous
    context = BeforeContext([el])
    while isinstance(el, WHITESPACE_NODES+(nodes.CommaNode, )):
        el = el.previous
        context.append(el)
    return context


def gather_after_context(el):
    el = el.next

    context = AfterContext([el])
    while isinstance(el, WHITESPACE_NODES+(nodes.CommaNode, )):
        el = el.next
        context.append(el)
    return context


def is_last(el):
    context = gather_after_context(el)
    return context[-1] is None
