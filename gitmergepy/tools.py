import types

from redbaron import (RedBaron,
                      nodes)

FIRST = object()
LAST = object()
INDENT = "."


def iter_coma_list(l):
    trimmed_list = l.node_list
    if isinstance(trimmed_list[0], nodes.LeftParenthesisNode):
        trimmed_list = trimmed_list[1:]
    if isinstance(trimmed_list[-1], nodes.RightParenthesisNode):
        trimmed_list = trimmed_list[:-1]

    for el in trimmed_list[::2]:
        yield el


def append_coma_list(l, to_add, new_line=False):
    insert_coma_list(l, position=LAST, to_add=to_add, new_line=new_line)


def insert_coma_list(l, position, to_add, new_line=False):

    def copy_sep():
        """Copy existing element to keep indentation"""
        middle_separator = l._get_middle_separator()
        separator = with_parent(l, middle_separator)
        if new_line:
            separator.second_formatting.insert(0, new_line.copy())
            separator.second_formatting.pop()
        return nodes.NodeList([separator])

    index = len(l.node_list) if position is LAST else 2 * position - 1
    if position == 0:
        index += 1
    data_index = len(l.data) if position is LAST else position
    sep = copy_sep()
    new_el = with_parent(l, to_add.copy())

    if l.node_list and isinstance(l.node_list[-1], nodes.RightParenthesisNode):
        is_empty = len(l.node_list) == 2
        index += -1 if position is LAST else 1
        data_index += -1 if position is LAST else 1
    else:
        is_empty = len(l.node_list) == 0  # pylint: disable=len-as-condition

    l.data.insert(data_index, [new_el, []])

    if not is_empty and position == 0:
        l.node_list.insert(index, sep[0])
    l.node_list.insert(index, new_el)
    if not is_empty and (position is LAST or position > 0):
        l.node_list.insert(index, sep[0])


def pop_coma_list(l):
    if isinstance(l[0], nodes.LeftParenthesisNode):
        del l.data[1]
        del l.node_list[1:3]
    else:
        del l.data[0]
        del l.node_list[0]


def remove_coma_list(l, el):
    for d in l.data:
        if d[0] == el:
            l.data.remove(d)
    index = l.node_list.index(el)
    del l.node_list[index]
    if index > 0:
        del l.node_list[index - 1]


def sort_imports(targets):
    for target in sorted(iter_coma_list(targets), key=lambda el: el.value):
        append_coma_list(targets, target)
        pop_coma_list(targets)


def short_display_el(el):
    if isinstance(el, nodes.DefNode):
        return "Fun(\"%s\")" % el.name

    if isinstance(el, nodes.ClassNode):
        return "Class(\"%s\")" % el.name

    if isinstance(el, nodes.ClassNode):
        return "Class(\"%s\")" % el.name

    if isinstance(el, nodes.EndlNode):
        return "new line"

    for line in el.dumps().splitlines():
        if line.strip():
            return line

    return "a bunch of blank lines"


def short_display_list(l):
    return ', '.join(short_display_el(el) for el in l)


def short_context(context):
    if context is None:
        return "no context"
    if context is LAST:
        return "last"
    if context[-1] is None:
        return "first +%d" % (len(context) - 1)
    return short_display_el(context[-1])


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


def get_call_els(atom_trailer_node):
    return [el for el in atom_trailer_node if isinstance(el, nodes.CallNode)]


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
    if isinstance(arg, nodes.ListArgumentNode):
        return '*' + arg.name.value
    if isinstance(arg, nodes.DictArgumentNode):
        return '**' + arg.name.value
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


def clear_coma_list(l):
    del l.data[1:-1]
    del l.node_list[1:-1]


def skip_context_endl(tree, context, index=0):
    if len(tree.node_list) == 0:  # pylint: disable=len-as-condition
        return 0

    while isinstance(tree.node_list[index], nodes.EndlNode):
        index += 1
        if index >= len(tree.node_list):
            break
    return index


def with_parent(tree, el):
    el.parent = tree.node_list
    el.on_attribute = tree.on_attribute
    return el


def decrease_indentation(tree):
    """Workaround redbaron de-indent bug"""
    def _shift(el):
        el.indent = el.indent[:-4]

    if isinstance(tree, nodes.IfelseblockNode):
        decrease_indentation(tree.value)
        return
    if not hasattr(tree, 'node_list'):
        return

    indentation = None
    for el in tree.node_list:
        print('el', short_display_el(el))
        if not isinstance(el, nodes.EndlNode):
            decrease_indentation(el)
        else:
            if indentation is None:
                indentation = el.indent
            if el.indent < indentation:
                break
            _shift(el)


def find_indentation(el):
    tree = el.parent
    if tree is None:
        return ""

    index = tree.node_list.index(el)
    if index > 0:
        endl = tree.node_list[index-1]
        if isinstance(endl, nodes.EndlNode):
            return endl.indent
    return ""
