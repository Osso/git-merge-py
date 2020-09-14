from redbaron import nodes


def sort_imports(targets):
    new_targets = [t.copy() for t in targets]
    targets.extend(sorted(new_targets, key=lambda el: el.value))
    for _ in new_targets:
        targets.pop(0)


def short_display_el(el):
    if isinstance(el, nodes.DefNode):
        return "Fun(\"%s\")" % el.name
    return type(el).__name__


def diff_list(left, right, key_getter, value_getter=None):
    left_keys = set(key_getter(i) for i in left)
    right_keys = set(key_getter(i) for i in right)

    to_add = [el for el in right if key_getter(el) not in left_keys]
    to_remove = [el for el in left if key_getter(el) not in right_keys]

    return to_add, to_remove


def changed_list(left, right, key_getter, value_getter):
    left_keys = set(key_getter(i) for i in left)
    right_keys = set(key_getter(i) for i in right)
    both_keys = left_keys & right_keys

    changed = []
    left_els = [el for el in left if key_getter(el) in both_keys]
    right_els = [el for el in right if key_getter(el) in both_keys]

    for left_el, right_el in zip(left_els, right_els):
        if value_getter(left_el) != value_getter(right_el):
            changed.append(right_el)

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
