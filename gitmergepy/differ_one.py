import logging

from redbaron import (RedBaron,
                      nodes)

from .differ import (compute_diff,
                     compute_diff_iterables)
from .matcher import gather_context
from .tools import (INDENT,
                    changed_in_list,
                    diff_list,
                    get_call_els,
                    id_from_el,
                    iter_coma_list,
                    short_display_el)
from .tree import (AddAllDecoratorArgs,
                   AddCallArg,
                   AddDecorator,
                   AddFunArg,
                   AddImports,
                   ChangeArg,
                   ChangeArgDefault,
                   ChangeAssignmentNode,
                   ChangeAtomtrailersCall,
                   ChangeAttr,
                   ChangeCallArgValue,
                   ChangeDecorator,
                   ChangeDecoratorArgs,
                   ChangeIndentation,
                   ChangeValue,
                   RemoveAllDecoratorArgs,
                   RemoveCallArgs,
                   RemoveDecorators,
                   RemoveFunArgs,
                   RemoveImports,
                   Replace,
                   ReplaceTarget)


def diff_redbaron(left, right, indent):
    return compute_diff_iterables(left, right, indent=indent+INDENT)


def diff_replace(left, right, indent):
    return [Replace(right)]


def diff_arg_node(left, right, indent):
    diff = []
    if id_from_el(left.target) != id_from_el(right.target):
        diff += [ReplaceTarget(right.target)]
    changes = compute_diff(left.value, right.value, indent=indent+INDENT)
    diff += [ChangeArg(right, changes=changes)]
    return diff


def diff_def_node(left, right, indent):
    diff = []
    # Name
    if left.name != right.name:
        diff += [ChangeAttr('name', right.name)]
    # Args
    to_add, to_remove = diff_list(left.arguments, right.arguments,
                                  key_getter=id_from_el)
    for arg in to_add:
        logging.debug('%s fun new arg %r', indent, short_display_el(arg))
    for arg in to_remove:
        logging.debug('%s fun old arg %r', indent, short_display_el(arg))
    for arg in to_add:
        diff += [AddFunArg(arg, context=gather_context(arg),
                           new_line=arg.previous.endl if arg.previous else False)]
    if to_remove:
        diff += [RemoveFunArgs(to_remove)]
    changed = changed_in_list(left.arguments, right.arguments,
                              key_getter=lambda t: t.name.value,
                              value_getter=lambda t: t.dumps())
    for _, arg in changed:
        logging.debug('%s fun changed args %r', indent,
                      short_display_el(arg))
    diff += [ChangeArgDefault(el_right,
                              changes=compute_diff(el_left, el_right,
                                                   indent=indent+INDENT))
             for el_left, el_right in changed]
    # Decorators
    to_add, to_remove = diff_list(left.decorators, right.decorators,
                                  key_getter=lambda t: t.name.value)
    for decorator in to_add:
        diff += [AddDecorator(decorator,
                              context=gather_context(decorator))]
    if to_remove:
        diff += [RemoveDecorators(to_remove)]
    for arg in to_add:
        logging.debug('%s fun new decorator %r', indent, short_display_el(arg))
    for arg in to_remove:
        logging.debug('%s fun old decorator %r', indent, short_display_el(arg))
    changed = changed_in_list(left.decorators, right.decorators,
                              key_getter=lambda t: t.name.value,
                              value_getter=lambda t: t.dumps())
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
            diff += [ChangeDecorator(left, changes=diff_decorator)]

    # Remove extra newlines that should have been in parent
    # left_copy = left.copy()
    # while isinstance(left_copy.data[-1][0], nodes.EndlNode):
    #     left_copy.data.pop()

    # right_copy = right.copy()
    # while isinstance(right_copy.data[-1][0], nodes.EndlNode):
    #     right_copy.data.pop()

    # diff += compute_diff_iterables(left_copy, right_copy, indent=indent)
    diff += compute_diff_iterables(left, right, indent=indent)

    return diff


def create_add_remove_imports(to_add_class, to_add, to_remove_class, to_remove):
    diff = []
    if to_add:
        diff += [to_add_class([el for el in to_add])]
    if to_remove:
        diff += [to_remove_class(to_remove)]
    return diff


def diff_import_node(left, right, indent):
    to_add, to_remove = diff_list(iter_coma_list(left.targets),
                                  iter_coma_list(right.targets),
                                  key_getter=lambda t: t.value)
    return create_add_remove_imports(AddImports, to_add,
                                     RemoveImports, to_remove)


def diff_with_node(left, right, indent):
    diff = []
    if left.contexts.dumps() != right.contexts.dumps():
        logging.debug('%s changed contexts %r', indent, right.contexts)
        diff += [ChangeAttr('contexts', right.contexts.copy())]

    diff += compute_diff_iterables(left, right, indent=indent)

    return diff


def diff_atom_trailer_node(left, right, indent):
    diff = []
    if id_from_el(left) != id_from_el(right):
        diff += [Replace(right)]
    else:
        calls_diff = []
        calls_els_left = get_call_els(left)
        calls_els_right = get_call_els(right)
        for index, (el_left, el_right) in enumerate(zip(calls_els_left, calls_els_right)):
            calls_diff = compute_diff(el_left, el_right, indent=indent)
            if calls_diff:
                diff += [ChangeAtomtrailersCall(el_left, index=index,
                                                changes=calls_diff)]
    return diff


def diff_call_node(left, right, indent):
    diff = []
    to_add, to_remove = diff_list(left, right,
                                  key_getter=id_from_el)
    for arg in to_add:
        logging.debug('%s call new arg %r', indent, short_display_el(arg))
    for arg in to_remove:
        logging.debug('%s call old arg %r', indent, short_display_el(arg))
    for arg in to_add:
        diff += [AddCallArg(arg, context=gather_context(arg),
                            new_line=arg.previous.endl if arg.previous else False)]
    if to_remove:
        diff += [RemoveCallArgs(to_remove)]

    changed = changed_in_list(left, right,
                           key_getter=id_from_el,
                           value_getter=lambda t: t.dumps())
    for _, arg in changed:
        logging.debug('%s call changed args %r', indent,
                      short_display_el(arg))
    diff += [ChangeCallArgValue(el_right,
                                changes=compute_diff(el_left, el_right,
                                                     indent=indent+INDENT))
             for el_left, el_right in changed]
    return diff


def diff_assignment_node(left, right, indent):
    diff = []
    if left.name.value != right.name.value:
        diff += [ChangeAttr('name', right.name)]

    el_diff = compute_diff(left.value, right.value, indent=indent+INDENT)
    if el_diff:
        diff += [ChangeAssignmentNode(left, changes=el_diff)]

    return diff


def diff_class_node(left, right, indent):
    diff = []
    # Name
    if left.name != right.name:
        diff += [ChangeAttr('name', right.name)]
    # Decorators
    to_add, to_remove = diff_list(left.decorators, right.decorators,
                                  key_getter=lambda t: t.name.value)
    for decorator in to_add:
        diff += [AddDecorator(decorator,
                              context=gather_context(decorator))]
    if to_remove:
        diff += [RemoveDecorators(to_remove)]
    if to_add:
        logging.debug('%s class new decorators %r', indent, to_add)
    if to_remove:
        logging.debug('%s class old decorators %r', indent, to_remove)
    changed = changed_in_list(left.decorators, right.decorators,
                           key_getter=lambda t: t.name.value,
                           value_getter=lambda t: t.dumps())
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
            diff += [ChangeDecorator(left, changes=diff_decorator)]

    diff += compute_diff_iterables(left, right, indent=indent+INDENT)

    return diff


def diff_if_else_block_node(left, right, indent):
    diff = compute_diff_iterables(left.value, right.value, indent+INDENT)
    if diff:
        return [ChangeValue(right, changes=diff)]
    return []


def diff_if_node(left, right, indent):
    diff = []
    if left.test.dumps() != right.test.dumps():
        diff += [ChangeAttr('test', right.test.copy())]

    diff += compute_diff_iterables(left, right, indent=indent+INDENT)
    return diff


def diff_endl_node(left, right, indent):
    diff = []
    if left.indent != right.indent:
        diff += [ChangeIndentation(right.indent)]

    return diff


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
}
