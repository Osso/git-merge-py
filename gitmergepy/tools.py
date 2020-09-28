import logging
import types

from redbaron import (RedBaron,
                      nodes)

FIRST = object()
LAST = object()
INDENT = "."


def iter_coma_list(l):
    trimmed_list = l
    if isinstance(l[0], nodes.LeftParenthesisNode):
        trimmed_list = trimmed_list[1:]
    if isinstance(l[-1], nodes.RightParenthesisNode):
        trimmed_list = trimmed_list[:-1]
    return iter(trimmed_list)


def append_coma_list(l, to_add, new_line=False):
    insert_coma_list(l, position=LAST, to_add=to_add, new_line=new_line)


def insert_coma_list(l, position, to_add, new_line=False):

    def copy_sep():
        """Copy existing element to keep indentation"""
        if new_line:
            separator = l.middle_separator.copy()
            separator.parent = l.node_list
            separator.on_attribute = l.on_attribute
            separator.second_formatting.pop()
            seps = [separator, new_line]
        else:
            separator = l._get_middle_separator()
            separator.parent = l.node_list
            separator.on_attribute = l.on_attribute
            seps = [separator]
        return nodes.NodeList(seps)

    def copy_el(index):
        """Copy existing element to keep indentation"""
        new_el = to_add.copy()
        new_el.parent = l.node_list
        new_el.on_attribute = l.on_attribute
        return new_el

    if isinstance(l[-1], nodes.RightParenthesisNode):
        sep = copy_sep()
        new_el = copy_el(index=1)
        is_empty = len(l.data) == 2
        # Workaround redbaron bug: extra separator if last element is a )
        # Insert into data
        l.data.insert(-1 if position is LAST else position + 1,
                      [new_el, sep])
        if not is_empty and position is LAST:
            l.data[-2][1] = sep
            l.data[-1][1] = None
        # Match node_list to data
        if not is_empty:
            l.node_list.insert(-1 if position is LAST else 2 * position + 1,
                               sep)
        l.node_list.insert(-1 if position is LAST else 2 * position + 1,
                           new_el)
    else:
        sep = copy_sep()
        new_el = copy_el(index=0)
        if position is LAST:
            l.data.append([new_el, None])
        else:
            l.data.insert(position, [new_el, sep])
        is_empty = len(l.data) == 0  # pylint: disable=len-as-condition
        if not is_empty and position is LAST:
            l.data[-2][1] = sep
            l.data[-1][1] = None
        if not is_empty:
            if position is LAST:
                l.node_list.append(sep)
            else:
                l.node_list.insert(2 * position, sep)

        if position is LAST:
            l.node_list.append(new_el)
        else:
            l.node_list.insert(2 * position, new_el)


def pop_coma_list(l):
    if isinstance(l[0], nodes.LeftParenthesisNode):
        # Workaround bug: extra separator if first element is a (
        del l.data[1]
        del l.node_list[1:3]
    else:
        del l[0]


def sort_imports(targets):
    for target in sorted(iter_coma_list(targets), key=lambda el: el.value):
        append_coma_list(targets, target)
        pop_coma_list(targets)


def short_display_el(el):
    if isinstance(el, nodes.DefNode):
        return "Fun(\"%s\")" % el.name
    # return type(el).__name__
    for line in el.dumps().splitlines():
        if line.strip():
            return line
    return "a bunch of blank lines"


def short_context(context):
    if context is FIRST:
        return "first"
    if context is LAST:
        return "last"
    if context is None:
        return "no context"
    return context[-1].dumps().splitlines()[-1]


def diff_list(left, right, key_getter, value_getter=None):
    left = list(left)
    right = list(right)
    left_keys = set(key_getter(i) for i in left)
    right_keys = set(key_getter(i) for i in right)

    to_add = [el for el in right if key_getter(el) not in left_keys]
    to_remove = [el for el in left if key_getter(el) not in right_keys]

    return to_add, to_remove


def changed_in_list(left, right, key_getter, value_getter):
    left_keys = set(key_getter(i) for i in left)
    right_keys = set(key_getter(i) for i in right)
    both_keys = left_keys & right_keys

    changed = []
    left_els = [el for el in left if key_getter(el) in both_keys]
    right_els = [el for el in right if key_getter(el) in both_keys]

    for left_el, right_el in zip(left_els, right_els):
        if value_getter(left_el) != value_getter(right_el):
            changed.append((left_el, right_el))

    return changed


def apply_diff_to_list(elements, to_add, to_remove, key_getter):
    existing_values = set(key_getter(el) for el in elements)
    to_add = [el for el in to_add if key_getter(el) not in existing_values]
    elements.extend(to_add)

    to_remove_values = set(key_getter(el) for el in to_remove)
    for el in elements:
        if key_getter(el) in to_remove_values:
            elements.remove(el)


def is_iterable(el):
    try:
        el[0]
    except TypeError:
        return False
    else:
        return True


def get_call_el(el):
    sub_el = None
    for sub_el in el:
        if not isinstance(sub_el, nodes.NameNode):
            break

    if isinstance(sub_el, nodes.CallNode):
        return sub_el
    return None


def get_name_els_from_call(el):
    name_els = []
    for sub_el in el:
        if not isinstance(sub_el, nodes.NameNode):
            break
        name_els.append(el)
    return name_els


def name_els_to_string(els):
    return '.'.join(el.name.value for el in els)


def as_from_contexts(contexts):
    return set(c.as_.value if c.as_ else id_from_el(c.value) for c in contexts)


def id_from_el(arg):
    if isinstance(arg, nodes.CallArgumentNode):
        return 'func' + id_from_el(arg.target if arg.target else arg.value)
    if isinstance(arg, nodes.NameNode):
        return arg.name.value
    if isinstance(arg, nodes.DefArgumentNode):
        return arg.name.value
    if isinstance(arg, nodes.AtomtrailersNode):
        return '.'.join(id_from_el(el) if not isinstance(el, nodes.CallNode)
                        else '()'
                        for el in arg)
    return arg


def make_indented(coma_list, handle_brackets=False):
    # logging.debug("make_indented %s", short_display_el(indent_ref))
    # if coma_list.style == 'flat':
    #     existing_imports = import_el.targets
    #     import_el.targets = indent_ref.copy()
    #     import_el.targets.middle_separator = import_el.targets.node_list[2]
    #     clear_coma_list(import_el.targets)
    #     for i in existing_imports:
    #         append_coma_list(import_el.targets, i)
    # import_el.targets.indented_separator = indent_ref.targets.node_list[2]
    # coma_list.style = 'indented'

    # Enclose in () for multi-line
    if handle_brackets and not isinstance(coma_list[0],
                                          nodes.LeftParenthesisNode):
        targets = RedBaron("from m import (f)")[0].targets
        left_bracket = targets[0]
        right_bracket = targets[-1]
        coma_list.data.insert(0, [left_bracket, None])
        coma_list.data.append([right_bracket, None])
        coma_list.node_list.insert(0, left_bracket)
        coma_list.node_list.append(right_bracket)

    # Indentation
    def _get_middle_separator(self):
        first_el = self[0]
        if isinstance(first_el, nodes.LeftParenthesisNode):
            first_el = self[1]

        column = first_el.absolute_bounding_box.top_left.column - 1

        return nodes.CommaNode({
            "type": "comma",
            "first_formatting": [],
            "second_formatting": [{
                "type": "endl",
                "indent": column * " ",
                "formatting": [], "value": "\n"}]})

    coma_list._get_middle_separator = types.MethodType(_get_middle_separator,
                                                       coma_list)

    # coma_list._get_middle_separator()

    # first_el = coma_list[0]
    # if isinstance(first_el, nodes.LeftParenthesisNode):
    #     first_el = coma_list[1]

    # coma_list.indented_separator = coma_list.middle_separator.copy()
    # coma_list.indented_separator.second_formatting = \
    #     "\n" + (first_el.absolute_bounding_box.top_left.column - 1) * ' '


def clear_coma_list(l):
    del l.data[1:-1]
    del l.node_list[1:-1]
