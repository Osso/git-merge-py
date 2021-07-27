import logging

from redbaron import (RedBaron,
                      nodes)

from .context import gather_context
from .differ import (compute_diff,
                     compute_diff_iterables)
from .tools import (INDENT,
                    changed_in_list,
                    diff_list,
                    get_call_els,
                    id_from_el,
                    short_display_el)
from .tree import (AddAllDecoratorArgs,
                   AddBase,
                   AddCallArg,
                   AddDecorator,
                   AddDictItem,
                   AddFunArg,
                   AddImports,
                   ArgOnNewLine,
                   ArgRemoveNewLine,
                   ChangeAnnotation,
                   ChangeArg,
                   ChangeAssignmentNode,
                   ChangeAtomtrailersCall,
                   ChangeCallArg,
                   ChangeDecorator,
                   ChangeDecoratorArgs,
                   ChangeDefArg,
                   ChangeDictItem,
                   ChangeReturn,
                   ChangeValue,
                   MakeInline,
                   MakeMultiline,
                   MoveArg,
                   RemoveAllDecoratorArgs,
                   RemoveBases,
                   RemoveCallArgs,
                   RemoveDecorators,
                   RemoveDictItem,
                   RemoveFunArgs,
                   RemoveImports,
                   RenameClass,
                   RenameDef,
                   Replace,
                   ReplaceAnnotation,
                   ReplaceAttr,
                   ReplaceTarget)


def get_previous_arg(arg, deleted):
    previous = arg.previous
    deleted = set(id_from_el(el) for el in deleted)
    while id_from_el(previous) in deleted:
        previous = previous.previous
    return previous


def diff_redbaron(left, right, indent):
    return compute_diff_iterables(left, right, indent=indent+INDENT)


def diff_replace(left, right, indent):
    return [Replace(new_value=right, old_value=left)]


def diff_arg_node(left, right, indent):
    diff = []
    # Target
    if id_from_el(left.target) != id_from_el(right.target):
        diff += [ReplaceTarget(new_value=right.target, old_value=left.target)]
    # Value
    if left.value is None and right.value is None:
        pass
    elif left.value is not None and right.value is not None:
        changes = compute_diff(left.value, right.value, indent=indent+INDENT)
        if changes:
            diff += [ChangeArg(right, changes=changes)]
    else:
        diff += [ReplaceAttr('value', right.value)]
    # Annotation
    if isinstance(left, nodes.DefArgumentNode):
        if left.annotation is None and right.annotation is None:
            pass
        elif left.annotation is not None and right.annotation is not None:
            changes = compute_diff(left.annotation, right.annotation, indent=indent+INDENT)
            if changes:
                diff += [ChangeAnnotation(right, changes=changes)]
        else:
            diff += [ReplaceAnnotation(right.annotation)]
    return diff


def diff_def_node(left, right, indent):
    diff = []
    # Name
    if left.name != right.name:
        diff += [RenameDef(right)]

    # Args
    to_add, to_remove = diff_list(left.arguments, right.arguments)
    for arg in to_add:
        logging.debug('%s fun new arg %r', indent, short_display_el(arg))
        diff += [AddFunArg(arg, context=gather_context(arg),
                           on_new_line=arg.on_new_line)]
    if to_remove:
        for arg in to_remove:
            logging.debug('%s fun old arg %r', indent, short_display_el(arg))
        diff += [RemoveFunArgs(to_remove)]
    changed = changed_in_list(left.arguments, right.arguments,
                              value_getter=_check_for_arg_changes)
    for old_arg, new_arg in changed:
        logging.debug('%s fun changed args %r', indent,
                      short_display_el(new_arg))
        diff_arg = compute_diff(old_arg, new_arg, indent=indent+INDENT)
        if not old_arg.on_new_line and new_arg.on_new_line:
            rel_indent = len(new_arg.indentation) - len(new_arg.parent.parent.indentation)
            diff_arg += [ArgOnNewLine(indentation=rel_indent*" ")]
        if old_arg.on_new_line and not new_arg.on_new_line:
            diff_arg += [ArgRemoveNewLine()]
        if id_from_el(get_previous_arg(old_arg, to_remove)) != id_from_el(get_previous_arg(new_arg, to_remove)):
            diff_arg += [MoveArg(context=gather_context(new_arg))]
        if diff_arg:
            diff += [ChangeDefArg(new_arg, changes=diff_arg)]

    # Decorators
    to_add, to_remove = diff_list(left.decorators, right.decorators)
    for decorator in to_add:
        diff += [AddDecorator(decorator,
                              context=gather_context(decorator))]
    if to_remove:
        diff += [RemoveDecorators(to_remove)]
    for arg in to_add:
        logging.debug('%s fun new decorator %r', indent, short_display_el(arg))
    for arg in to_remove:
        logging.debug('%s fun old decorator %r', indent, short_display_el(arg))
    changed = changed_in_list(left.decorators, right.decorators)
    for left_el, right_el in changed:
        logging.debug('%s fun changed decorator %r ', indent, right_el)
        diff_decorator = []
        if left_el.call and right_el.call:
            changes = compute_diff(left_el.call, right_el.call,
                                   indent=indent+INDENT)
            diff_decorator += [ChangeDecoratorArgs(right_el,
                                                   changes=changes)]
        elif left_el.call:
            diff_decorator += [RemoveAllDecoratorArgs(None)]
        elif right_el.call:
            diff_decorator += [AddAllDecoratorArgs(right_el.call)]
        if diff_decorator:
            diff += [ChangeDecorator(left_el, changes=diff_decorator)]

    diff += diff_inline_vs_multiline(left, right, indent=indent)

    # Body
    diff += compute_diff_iterables(left.value, right.value, indent=indent)

    return diff


def diff_import_node(left, right, indent):
    to_add, to_remove = diff_list(left.targets, right.targets,
                                  key_getter=lambda t: t.value)
    diff = []
    if to_add:
        diff += [AddImports([el for el in to_add],
                            one_per_line=right.targets.detect_one_per_line(),
                            add_brackets=right.targets.has_brackets())]
    if to_remove:
        diff += [RemoveImports(to_remove)]
    return diff


def diff_with_node(left, right, indent):
    diff = []
    if left.contexts.dumps() != right.contexts.dumps():
        logging.debug('%s changed contexts %r', indent, short_display_el(right.contexts))
        diff += [ReplaceAttr('contexts', right.contexts.copy())]

    diff += compute_diff_iterables(left, right, indent=indent)

    return diff


def diff_atom_trailer_node(left, right, indent):
    diff = []
    if id_from_el(left) != id_from_el(right):
        diff += [Replace(new_value=right, old_value=left)]
    else:
        calls_diff = []
        calls_els_left = get_call_els(left)
        calls_els_right = get_call_els(right)
        for index, (el_left, el_right) in enumerate(zip(calls_els_left,
                                                        calls_els_right)):
            calls_diff = compute_diff(el_left, el_right, indent=indent)
            if calls_diff:
                diff += [ChangeAtomtrailersCall(el_left, index=index,
                                                changes=calls_diff)]
    return diff


def _check_for_arg_changes(arg):
    endl = "\n" if arg.on_new_line else ""
    return endl + arg.dumps() + '_%d' % arg.index_on_parent


def diff_call_node(left, right, indent):
    diff = []
    to_add, to_remove = diff_list(left, right)
    for arg in to_add:
        logging.debug('%s call new arg %r', indent, short_display_el(arg))
    for arg in to_remove:
        logging.debug('%s call old arg %r', indent, short_display_el(arg))
    for arg in to_add:
        diff += [AddCallArg(arg, context=gather_context(arg),
                            on_new_line=arg.on_new_line)]
    if to_remove:
        diff += [RemoveCallArgs(to_remove)]

    changed = changed_in_list(left, right, value_getter=_check_for_arg_changes)

    for old_arg, new_arg in changed:
        logging.debug('%s call changed args %r', indent,
                      short_display_el(new_arg))
        diff_arg = compute_diff(old_arg, new_arg, indent=indent+INDENT)
        if not old_arg.on_new_line and new_arg.on_new_line:
            rel_indent = len(new_arg.indentation) - len(new_arg.parent.parent.indentation)
            diff_arg += [ArgOnNewLine(indentation=rel_indent*" ")]
        if old_arg.on_new_line and not new_arg.on_new_line:
            diff_arg += [ArgRemoveNewLine()]
        if id_from_el(get_previous_arg(old_arg, to_remove)) != id_from_el(get_previous_arg(new_arg, to_remove)):
            diff_arg += [MoveArg(context=gather_context(new_arg))]
        diff += [ChangeCallArg(new_arg, changes=diff_arg)]
    return diff


def diff_assignment_node(left, right, indent):
    diff = []
    if left.target.value != right.target.value:
        diff += [ReplaceAttr('target', right.target)]

    el_diff = compute_diff(left.value, right.value, indent=indent+INDENT)
    if el_diff:
        diff += [ChangeAssignmentNode(left, changes=el_diff)]

    return diff


def diff_class_node_decorators(left, right, indent):
    diff = []

    to_add, to_remove = diff_list(left.decorators, right.decorators)
    for decorator in to_add:
        diff += [AddDecorator(decorator,
                              context=gather_context(decorator))]
    if to_remove:
        diff += [RemoveDecorators(to_remove)]
    if to_add:
        logging.debug('%s class new decorators %r', indent, to_add)
    if to_remove:
        logging.debug('%s class old decorators %r', indent, to_remove)
    changed = changed_in_list(left.decorators, right.decorators)
    for left_el, right_el in changed:
        logging.debug('%s class changed decorator %r ', indent, right_el)
        diff_decorator = []
        if left_el.call and right_el.call:
            changes = compute_diff(left_el.call, right_el.call,
                                   indent=indent+INDENT)
            diff_decorator += [ChangeDecoratorArgs(right_el,
                                                   changes=changes)]
        elif left_el.call:
            diff_decorator += [RemoveAllDecoratorArgs(None)]
        elif right_el.call:
            diff_decorator += [AddAllDecoratorArgs(right_el.call)]
        if diff_decorator:
            diff += [ChangeDecorator(left_el, changes=diff_decorator)]

    return diff


def diff_class_node_bases(left, right, indent):
    diff = []

    to_add, to_remove = diff_list(left.inherit_from, right.inherit_from)
    for base in to_add:
        diff += [AddBase(base,
                              context=gather_context(base))]
    if to_remove:
        diff += [RemoveBases(to_remove)]
    if to_add:
        logging.debug('%s class new bases %r', indent, to_add)
    if to_remove:
        logging.debug('%s class old bases %r', indent, to_remove)
    changed = changed_in_list(left.inherit_from, right.inherit_from)
    for left_el, right_el in changed:
        logging.debug('%s class changed base %r ', indent, right_el)
        diff_base = compute_diff(left_el, right_el, indent=indent+INDENT)
        if diff_base:
            diff += [ChangeDecorator(left_el, changes=diff_base)]

    return diff


def diff_class_node(left, right, indent):
    diff = []

    # Name
    if left.name != right.name:
        diff += [RenameClass(right)]

    # Bases
    diff += diff_class_node_bases(left, right, indent)

    # Decorators
    diff += diff_class_node_decorators(left, right, indent)

    # Inline vs multiline
    diff += diff_inline_vs_multiline(left, right, indent=indent)

    # Body
    diff += compute_diff_iterables(left.value, right.value, indent=indent+INDENT)

    return diff


def diff_if_else_block_node(left, right, indent):
    diff = compute_diff_iterables(left.value, right.value, indent+INDENT)
    if diff:
        return [ChangeValue(right, changes=diff)]
    return []


def diff_if_node(left, right, indent):
    diff = []
    if left.test.dumps() != right.test.dumps():
        diff += [ReplaceAttr('test', right.test.copy())]

    diff += compute_diff_iterables(left, right, indent=indent+INDENT)
    return diff


def diff_else_node(left, right, indent):
    return compute_diff_iterables(left, right, indent=indent+INDENT)


def diff_endl_node(left, right, indent):
    return []


def diff_return_node(left, right, indent):
    diff = compute_diff(left.value, right.value, indent+INDENT)
    if diff:
        return [ChangeReturn(right, changes=diff)]
    return []


def diff_list_node(left, right, indent):
    diff = compute_diff_iterables(left.value, right.value, indent+INDENT)
    if diff:
        return [ChangeValue(right, changes=diff)]
    return []


def diff_tuple_node(left, right, indent):
    diff = compute_diff_iterables(left.value, right.value, indent+INDENT)
    if diff:
        return [ChangeValue(right, changes=diff)]
    return []


def diff_list_argument_node(left, right, indent):
    return compute_diff(left.value, right.value, indent+INDENT)


def diff_dict_argument_node(left, right, indent):
    return compute_diff(left.value, right.value, indent+INDENT)


def diff_dict_node(left, right, indent):
    diff = []

    to_add, to_remove = diff_list(left, right)

    for item in to_add:
        logging.debug('%s dict new key %r', indent, short_display_el(item.key))
        diff += [AddDictItem(item, previous_item=item.previous)]
    for item in to_remove:
        logging.debug('%s dict removed key %r', indent, short_display_el(item.key))
        diff += [RemoveDictItem(item)]

    changed = changed_in_list(left, right)
    for left_el, right_el in changed:
        logging.debug('%s dict changed key %r', indent, short_display_el(left_el.key))
        diff += [ChangeDictItem(left_el,
                                changes=compute_diff(left_el.value,
                                                     right_el.value,
                                                     indent=indent+INDENT))]

    return diff


def diff_for_node(left, right, indent):
    diff = []
    if left.target.dumps() != right.target.dumps():
        diff += [ReplaceAttr('target', right.target.copy())]

    if left.iterator.dumps() != right.iterator.dumps():
        diff += [ReplaceAttr('iterator', right.iterator.copy())]

    diff += compute_diff_iterables(left, right, indent=indent+INDENT)
    return diff


def diff_while_node(left, right, indent):
    diff = []
    if left.value.dumps() != right.value.dumps():
        diff += [ReplaceAttr('value', right.value.copy())]

    if left.as_.dumps() != right.as_.dumps():
        diff += [ReplaceAttr('as_', right.as_.copy())]

    diff += compute_diff_iterables(left, right, indent=indent+INDENT)
    return diff


def diff_pass_node(left, right, indent):
    return []


def diff_inline_vs_multiline(left, right, indent):
    if left.value.header and not right.value.header:
        return [MakeInline()]
    if not left.value.header and right.value.header:
        return [MakeMultiline()]
    return []


COMPUTE_DIFF_ONE_CALLS = {
    RedBaron: diff_redbaron,
    nodes.CommentNode: diff_replace,
    nodes.AssociativeParenthesisNode: diff_replace,
    nodes.IntNode: diff_replace,
    nodes.CallArgumentNode: diff_arg_node,
    nodes.DefArgumentNode: diff_arg_node,
    nodes.DefNode: diff_def_node,
    nodes.FromImportNode: diff_import_node,
    nodes.WithNode: diff_with_node,
    nodes.AtomtrailersNode: diff_atom_trailer_node,
    nodes.CallNode: diff_call_node,
    nodes.AssignmentNode: diff_assignment_node,
    nodes.ClassNode: diff_class_node,
    nodes.IfelseblockNode: diff_if_else_block_node,
    nodes.IfNode: diff_if_node,
    nodes.EndlNode: diff_endl_node,
    nodes.ElseNode: diff_else_node,
    nodes.ReturnNode: diff_return_node,
    nodes.ListNode: diff_list_node,
    nodes.TupleNode: diff_tuple_node,
    nodes.ListArgumentNode: diff_list_argument_node,
    nodes.DictArgumentNode: diff_dict_argument_node,
    nodes.DictNode: diff_dict_node,
    nodes.ForNode: diff_for_node,
    nodes.WhileNode: diff_while_node,
    nodes.PassNode: diff_pass_node,
}
