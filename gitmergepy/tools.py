import types

from redbaron import (RedBaron,
                      nodes)

FIRST = object()
LAST = object()
INDENT = "."
WHITESPACE_NODES = (nodes.EndlNode, )


def append_coma_list(target_list, to_add, new_line=False):
    if new_line:
        target_list.append("\n")
    target_list.append(to_add)


def insert_coma_list(target_list, position, to_add, new_line=False):
    if new_line:
        target_list.insert(position, "\n")
        position += 1
    target_list.insert(position, to_add)


def sort_imports(targets):
    targets.sort(key=lambda el: el.value)


def short_display_el(el):
    if el is None:
        return "None"

    if isinstance(el, nodes.DefNode):
        return "Fun(\"%s\")" % el.name

    if isinstance(el, nodes.ClassNode):
        return "Class(\"%s\")" % el.name

    if isinstance(el, nodes.ClassNode):
        return "Class(\"%s\")" % el.name

    if isinstance(el, nodes.EndlNode):
        return "new line indent=%d" % len(el.indent)

    for line in el.dumps().splitlines():
        if line.strip():
            return line

    return "a bunch of blank lines"


def short_display_list(node_list):
    return ', '.join(short_display_el(el) for el in node_list)


def short_context(context):
    if context is None:
        return "no context"
    if context is LAST:
        return "last"

    from .context import AfterContext
    if isinstance(context, AfterContext):
        # if context[-1] is None:
        #     return "last -%d" % (len(context) - 1)
        return 'after ' + '|'.join(short_display_el(el) for el in context)

    # if context[-1] is None:
    #     return "first +%d" % (len(context) - 1)
    return '|'.join(short_display_el(el) for el in reversed(context))


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
    return atom_trailer_node.find_all("call")


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
        if arg.target is not None:
            return id_from_el(arg.target)
        return id_from_el(arg.value)
    if isinstance(arg, nodes.ListArgumentNode):
        return '*' + arg.name.value
    if isinstance(arg, nodes.DictArgumentNode):
        return '**' + arg.name.value
    if isinstance(arg, nodes.NameNode):
        return arg.name.value
    if isinstance(arg, nodes.DefArgumentNode):
        return arg.name.value
    if isinstance(arg, nodes.StringNode):
        return arg.value
    if isinstance(arg, nodes.AtomtrailersNode):
        return '.'.join(id_from_el(el) if not isinstance(el, nodes.CallNode)
                        else '()'
                        for el in arg)
    return arg


def make_indented(coma_list, handle_brackets=False):
    if coma_list._indented:
        return

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

        column = first_el.absolute_bounding_box.top_left.column - 1

        node = nodes.CommaNode({
            "type": "comma",
            "first_formatting": [],
            "second_formatting": [{
                "type": "endl",
                "indent": column * " ",
                "formatting": [], "value": "\n"}]})
        return with_parent(self, node)

    coma_list._get_middle_separator = types.MethodType(_get_middle_separator,
                                                       coma_list)
    coma_list._indented = True


def skip_context_endl(tree, context, index=0):
    if not tree:  # pylint: disable=len-as-condition
        return 0

    while index < len(tree) and isinstance(tree[index], nodes.EmptyLine):
        index += 1
    return index


def with_parent(tree, el):
    el.parent = tree
    el.on_attribute = tree.on_attribute
    return el


def find_endl(tree):
    if isinstance(tree, nodes.EndlNode):
        return tree
    if isinstance(tree, nodes.IfelseblockNode):
        return find_endl(tree.value)
    if isinstance(tree, (nodes.DefNode, nodes.WithNode, nodes.ClassNode,
                         nodes.IfNode, RedBaron, nodes.NodeList,
                         nodes.ElifNode, nodes.ElseNode)):
        last_el = tree.node_list[-1]
        return find_endl(last_el)

    return None


def same_el(left, right):
    # For speed
    if type(left) != type(right):  # pylint: disable=unidiomatic-typecheck
        return False

    return left.dumps() == right.dumps()


def empty_lines(els):
    for el in els:
        if not isinstance(el, nodes.EndlNode):
            return False
    return True
