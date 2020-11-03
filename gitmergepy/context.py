from redbaron import nodes

from .tools import (WHITESPACE_NODES,
                    same_el)


class BeforeContext(list):
    def match_el(self, tree, el):
        index = tree.index(el)
        return self.match(tree, index)

    def match(self, tree, index):
        context = self
        start_index = index - len(context)
        if context[-1] is None:
            start_index += 1
            context = context[:-1]
            if start_index != 0:
                return False
        if start_index < 0:
            return False

        els = tree[start_index:index]

        if len(els) != len(context):
            return False

        for context_el, el in zip(reversed(context), els):
            if not same_el(context_el, el):
                return False

        return True

    def copy(self):
        return BeforeContext(self)


class AfterContext(list):
    def match_el(self, tree, el):
        index = tree.index(el) + 1
        return self.match(tree, index)

    def match(self, tree, index):
        context = self

        if context[-1] is None:
            context = context[:-1]
            if index + len(context) != len(tree):
                return False

        end_index = index + len(context)

        els = tree[index:end_index]

        if len(els) != len(context):
            return False

        for context_el, el in zip(context, els):
            if not same_el(context_el, el):
                return False

        return True

    def copy(self):
        return AfterContext(self)


def find_context(tree, context):
    for index in range(len(tree) + 1):
        if context.match(tree, index):
            return index
    return None


def gather_context(el):
    # after_context = gather_after_context(el)
    # if after_context[-1] is None:
    #     return after_context

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
