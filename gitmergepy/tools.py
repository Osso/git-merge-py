from redbaron import nodes
from redbaron.proxy_list import DotProxyList

FIRST = object()
LAST = object()
INDENT = "."
WHITESPACE_NODES = (nodes.EndlNode, nodes.EmptyLineNode)


def append_coma_list(target_list, to_add, on_new_line=False):
    insert_coma_list(target_list, len(target_list), to_add,
                     on_new_line=on_new_line)


def insert_coma_list(target_list, position, to_add, on_new_line=False):
    if on_new_line:
        target_list.insert_on_new_line(position, to_add)
    else:
        target_list.insert(position, to_add)


def sort_imports(targets):
    targets.sort(key=lambda el: el.value)
    targets.reformat(force_separator=True)


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


def id_from_el(arg):
    if arg is None:
        return ""
    if isinstance(arg, (nodes.DefNode, nodes.ClassNode)):
        return arg.name
    if isinstance(arg, nodes.FromImportNode):
        return id_from_el(arg.value)
    if isinstance(arg, nodes.CallArgumentNode):
        if arg.target is not None:
            return id_from_el(arg.target)
        return id_from_el(arg.value)
    if isinstance(arg, nodes.ListArgumentNode):
        return '*' + id_from_el(arg.value)
    if isinstance(arg, nodes.DictArgumentNode):
        return '**' + id_from_el(arg.value)
    if isinstance(arg, nodes.DefArgumentNode):
        return arg.target.value
    if isinstance(arg, nodes.DecoratorNode):
        return id_from_el(arg.value)
    if isinstance(arg, (nodes.StringNode, nodes.IntNode, nodes.NameNode)):
        return arg.value
    if isinstance(arg, nodes.DotNode):
        return '.'
    if isinstance(arg, nodes.GetitemNode):
        return '[' + id_from_el(arg.value) + ']'
    if isinstance(arg, (nodes.AtomtrailersNode, nodes.DottedNameNode,
                        DotProxyList)):
        return '.'.join(id_from_el(el) if not isinstance(el, nodes.CallNode)
                        else '()'
                        for el in arg)
    if isinstance(arg, nodes.DictitemNode):
        return id_from_el(arg.key)
    return arg.dumps()


def id_from_arg(arg):
    if isinstance(arg, (nodes.ListArgumentNode, nodes.DictArgumentNode)):
        return id_from_el(arg)
    if not arg.target and isinstance(arg.value, nodes.IntNode):
        return "0_%d" % arg.index_on_parent
    return id_from_el(arg)


def significant_args(call_node):
    return '()'


def id_from_decorator(decorator):
    def call_to_id(call):
        if call is None:
            return ''

        # If first arg is a string and it's different, probably not the same call
        if (call.value and isinstance(call.value[0].value, nodes.StringNode)):
            return '(%s)' % call.value[0].dumps()
        return '()'

    if isinstance(decorator, nodes.DecoratorNode):
        return ''.join(id_from_el(el) for el in decorator.value) + call_to_id(decorator.call)

    assert isinstance(decorator, nodes.CommentNode)
    return decorator.dumps()


def diff_list(left, right, key_getter=id_from_el, value_getter=None):
    left = list(left)
    right = list(right)
    left_keys = set(key_getter(i) for i in left)
    right_keys = set(key_getter(i) for i in right)

    to_add = [el for el in right if key_getter(el) not in left_keys]
    to_remove = [el for el in left if key_getter(el) not in right_keys]

    return to_add, to_remove


def changed_in_list(left, right, key_getter=id_from_el,
                    value_getter=lambda el: el.dumps()):
    left_keys = set(key_getter(i) for i in left)
    right_keys = set(key_getter(i) for i in right)
    both_keys = left_keys & right_keys

    changed = []
    left_els_map = {key_getter(el): el for el in left
                    if key_getter(el) in both_keys}
    rights_els_map = {key_getter(el): el for el in right
                      if key_getter(el) in both_keys}

    for key, left_el in left_els_map.items():
        right_el = rights_els_map[key]
        if value_getter(left_el) != value_getter(right_el):
            changed.append((left_el, right_el))

    return changed


def apply_diff_to_list(elements, to_add, to_remove, key_getter):
    existing_values = set(key_getter(el) for el in elements)
    to_add = [el for el in to_add if key_getter(el) not in existing_values]
    elements.extend(to_add)

    to_remove_values = set(key_getter(el) for el in to_remove)
    for el in list(elements):
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
    return atom_trailer_node.find_all("call", recursive=False)


def get_name_els_from_call(el):
    name_els = []
    for sub_el in el:
        if not isinstance(sub_el, nodes.NameNode):
            break
        name_els.append(sub_el)
    return name_els


def name_els_to_string(els):
    return '.'.join(el.dumps() for el in els)


def as_from_contexts(contexts):
    return set(c.as_.value if c.as_ else id_from_el(c.value) for c in contexts)


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


def same_el(left, right, discard_indentation=True):
    if left is None and right is None:
        return True

    if isinstance(left, (nodes.SpaceNode, nodes.EmptyLineNode)):
        return left.dumps() == right.dumps()

    # For speed
    if type(left) != type(right):  # pylint: disable=unidiomatic-typecheck
        return False

    if discard_indentation:
        return left.dumps().lstrip(" ") == right.dumps().lstrip(" ")
    return left.dumps() == right.dumps()


def empty_lines(els):
    return all(isinstance(el, (nodes.EmptyLineNode, nodes.EndlNode))
               for el in els)
