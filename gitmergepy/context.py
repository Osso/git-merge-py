from itertools import (dropwhile,
                       takewhile)

from redbaron import nodes

from .matcher import (find_el,
                      same_el_guess)
from .tools import (WHITESPACE_NODES,
                    empty_lines,
                    same_el)


class BeforeContext(list):
    def match_el(self, tree, el):
        index = tree.index(el)
        return self.match(tree, index)

    def match(self, tree, index):
        if not self:
            return True

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
            if not same_el_guess(context_el, el):
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
            if not same_el_guess(context_el, el):
                return False

        return True

    def copy(self):
        return AfterContext(self)


def find_context_with_reduction(tree, context):
    relevant_context = context.copy()

    for _ in range(3):
        matches = find_context(tree, relevant_context)
        if matches:
            return matches
        del relevant_context[-1]
        if not relevant_context or empty_lines(relevant_context):
            break

    return []


def find_context(tree, context):
    matches = []

    for index in range(len(tree) + 1):
        if context.match(tree, index):
            matches.append(index)

    return matches


def gather_context(el):
    el = el.previous
    context = BeforeContext([el])
    while isinstance(el, WHITESPACE_NODES+(nodes.CommaNode, )):
        el = el.previous
        context.append(el)
    if el and el.previous:
        context.append(el.previous)
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
