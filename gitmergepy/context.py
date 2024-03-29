from redbaron import nodes

from .matcher import (same_el,
                      same_el_guess)
from .tools import (WHITESPACE_NODES,
                    empty_lines)


class BeforeContext(list):
    def __eq__(self, other):
        if len(other) != len(self):
            return False
        return all(same_el(el, el_other) for el, el_other in zip(self, other))

    def match_el(self, tree, el):
        index = tree.index(el)
        return self.match(tree, index)

    def _skip_els(self, els, prev_elements, old_tree):
        def _filter(el):
            return (old_tree and el.new) or (not old_tree and el.hidden)

        not_hidden_prev_elements = [el for el in prev_elements
                                    if not _filter(el)]
        for el in els:
            if _filter(el):
                els.remove(el)
                if not_hidden_prev_elements:
                    els.insert(0, not_hidden_prev_elements.pop())

    def match(self, tree, index, old_tree=False):
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
        self._skip_els(els, prev_elements=tree[:start_index],
                       old_tree=old_tree)

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

    def _skip_els(self, els, next_elements, old_tree):
        def _filter(el):
            return (old_tree and el.new) or (not old_tree and el.hidden)

        not_hidden_next_elements = [el for el in next_elements
                                    if not _filter(el)]
        for el in els:
            if _filter(el):
                els.remove(el)
                if not_hidden_next_elements:
                    els.append(not_hidden_next_elements.pop(0))

    def match(self, tree, index, old_tree=False):
        context = self

        if context[-1] is None:
            context = context[:-1]
            if index + len(context) != len(tree):
                return False

        end_index = index + len(context)

        els = tree[index:end_index]
        self._skip_els(els, next_elements=tree[end_index:], old_tree=old_tree)

        if len(els) != len(context):
            return False

        for context_el, el in zip(context, els):
            if not same_el_guess(context_el, el):
                return False

        return True

    def copy(self):
        return AfterContext(self)


def find_context_with_reduction(tree, context, look_in_old_tree_first=False):
    trimmed_context = context.copy()

    while trimmed_context and not empty_lines(trimmed_context):

        # Simple case: exact context found
        matches = find_context(tree, trimmed_context,
                               look_in_old_tree_first=look_in_old_tree_first)
        if matches:
            return matches

        # Empty lines mismatch
        if isinstance(trimmed_context[0], nodes.EmptyLineNode):
            context_no_endl = trimmed_context.copy()
            while (context_no_endl and
                   isinstance(context_no_endl[0], nodes.EmptyLineNode)):
                del context_no_endl[0]
            matches = find_context(tree, context_no_endl,
                                   look_in_old_tree_first=look_in_old_tree_first)
            if matches:
                return matches

        # Try with a shorter context
        del trimmed_context[-1]

    return []


def _find_context(tree, context, old_tree):
    matches = []

    for index in range(len(tree) + 1):
        if context.match(tree, index, old_tree=old_tree):
            matches.append(index)

    return matches


def find_context(tree, context, look_in_old_tree_first=False):
    indexes = _find_context(tree, context, old_tree=look_in_old_tree_first)
    if not indexes:
        indexes = _find_context(tree, context,
                                old_tree=not look_in_old_tree_first)
    return indexes


def gather_context(el, limit=5):
    el = el.previous
    context = BeforeContext([])
    for _ in range(limit):
        while isinstance(el, WHITESPACE_NODES+(nodes.CommaNode, )):
            context.append(el)
            el = el.previous
        context.append(el)
        if el is None:
            break
        el = el.previous
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
