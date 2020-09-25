import logging

from redbaron import nodes

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


def append_coma_list(l, to_add):

    def copy_sep():
        """Copy existing element to keep indentation"""
        if len(l) > 3:
            return l.node_list[2].copy()
        return l.middle_separator.copy()

    def copy_import(index):
        """Copy existing element to keep indentation"""
        if l:
            el = l.node_list[index].copy()
            el.value = to_add.value
            el.target = to_add.target
            return el
        return to_add.copy()

    if isinstance(l[-1], nodes.RightParenthesisNode):
        sep = copy_sep()
        new_import = copy_import(index=1)
        is_empty = len(l.data) == 2
        # Workaround redbaron bug: extra separator if last element is a )
        # Insert into data
        if not is_empty:
            l.data[-2][1] = sep
        l.data.insert(-1, [new_import, None])
        # Match node_list to data
        if not is_empty:
            l.node_list.insert(-1, sep)
        l.node_list.insert(-1, new_import)
    else:
        l.append(copy_import(index=0))


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


def match_indentation(import_el, indent_ref):
    logging.debug("match_indentation %s", short_display_el(indent_ref))
    if import_el.targets.style == 'flat':
        existing_imports = import_el.targets
        import_el.targets = indent_ref.copy()
        import_el.targets.middle_separator = import_el.targets.node_list[2]
        clear_coma_list(import_el.targets)
        for i in existing_imports:
            append_coma_list(import_el.targets, i)


def clear_coma_list(l):
    del l.data[1:-1]
    del l.node_list[1:-1]
