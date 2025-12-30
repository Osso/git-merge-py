from .context import find_context


def append_coma_list(target_list, to_add, on_new_line=False):
    insert_coma_list(target_list, len(target_list), to_add, on_new_line=on_new_line)


def insert_coma_list(target_list, position, to_add, on_new_line=False):
    if on_new_line:
        target_list.insert_on_new_line(position, to_add)
    else:
        target_list.insert(position, to_add)


def insert_at_context_coma_list(el, context, tree, on_new_line=False):
    # Look for context
    indexes = find_context(tree, context)
    if indexes:
        insert_coma_list(tree, position=indexes[0], to_add=el, on_new_line=on_new_line)
        return True

    return False
