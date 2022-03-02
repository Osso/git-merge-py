from redbaron import nodes
from redbaron.node_mixin import CodeBlockMixin
from redbaron.proxy_list import ProxyList


def add_conflicts(source_el, conflicts):
    for conflict in conflicts:
        add_conflict(source_el, conflict)


def add_conflict(source_el, conflict):
    if isinstance(source_el.parent, ProxyList) and \
       isinstance(source_el.parent.parent, nodes.IfelseblockNode):
        source_el = source_el.parent.parent

    if conflict.insert_before and isinstance(source_el.parent, CodeBlockMixin):
        tree = source_el.parent
        index = tree.index(source_el)
    else:
        tree = source_el
        index = 0

    while tree.parent and (not isinstance(tree, CodeBlockMixin) or isinstance(tree, nodes.IfelseblockNode)):
        tree = tree.parent

    # We can only add code to add CodeProxyList
    assert isinstance(tree, CodeBlockMixin)

    def _insert(text):
        nonlocal index
        txt = "# " + text
        tree.insert(index, txt.strip() + "\n")
        index += 1

    before_text = "<<<<<<<<<<"
    after_text = ">>>>>>>>>>"
    _insert(before_text)
    if conflict.reason:
        _insert("Conflict: reason %s" % conflict.reason)
    if conflict.change:
        for line in repr(conflict.change).splitlines():
            _insert(line)
    if conflict.els:
        for el in conflict.els:
            for line in el.dumps().splitlines()[0:5]:
                _insert(line.rstrip())
    _insert(after_text)
