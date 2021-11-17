def remove_with(with_node):
    assert with_node.parent
    with_node_copy = with_node.copy()
    with_node_copy.decrease_indentation()
    index = with_node.parent.index(with_node) + 1
    for el, sep in with_node_copy.value._data:
        el.parent = with_node.parent
        if sep:
            sep.parent = with_node.parent
    with_node.parent._data[index:index] = with_node_copy.value._data
    with_node.parent._synchronise()
    with_node.parent.remove(with_node)
    return list(with_node_copy)
