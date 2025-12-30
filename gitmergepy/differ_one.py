from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from diff_match_patch import diff_match_patch
from redbaron import RedBaron, nodes

from .actions import (
    AddAllDecoratorArgs,
    AddBase,
    AddCallArg,
    AddDecorator,
    AddDictItem,
    AddElseNode,
    AddExcept,
    AddFinally,
    AddFunArg,
    AddImports,
    AddSepComment,
    ArgOnNewLine,
    ArgRemoveNewLine,
    ChangeAnnotation,
    ChangeArg,
    ChangeAssignment,
    ChangeAtomTrailer,
    ChangeAtomtrailersEl,
    ChangeAttr,
    ChangeCallArg,
    ChangeDecorator,
    ChangeDecoratorArgs,
    ChangeDefArg,
    ChangeDictItem,
    ChangeDictValue,
    ChangeElseNode,
    ChangeExceptsNode,
    ChangeNumberValue,
    ChangeReturn,
    ChangeSepComment,
    ChangeString,
    ChangeValue,
    MakeInline,
    MakeMultiline,
    MoveArg,
    RemoveAllDecoratorArgs,
    RemoveBases,
    RemoveCallArgs,
    RemoveCallEndl,
    RemoveDecorators,
    RemoveDictItem,
    RemoveElseNode,
    RemoveFunArgs,
    RemoveImports,
    RemoveSepComment,
    RenameClass,
    RenameDef,
    Replace,
    ReplaceAnnotation,
    ReplaceAttr,
    ReplaceTarget,
)
from .context import gather_context
from .differ import compute_diff, compute_diff_iterables
from .tools import (
    INDENT,
    changed_in_list,
    diff_list,
    id_from_arg,
    id_from_decorator,
    id_from_el,
    short_display_el,
)

if TYPE_CHECKING:
    from redbaron.base_nodes import Node
    from redbaron.proxy_list import ProxyList

# Type alias for action classes (no common base class)
Action = Any


def get_previous_arg(arg: Node, deleted: list[Node]) -> Node | None:
    previous = arg.previous
    deleted_ids = set(id_from_el(el) for el in deleted)
    while id_from_el(previous) in deleted_ids:
        previous = previous.previous
    return previous


def diff_redbaron(left: RedBaron, right: RedBaron, indent: str) -> list[Action]:
    return compute_diff_iterables(left, right, indent=indent + INDENT)


def diff_replace(left: Node, right: Node, indent: str) -> list[Action]:
    return [Replace(new_value=right, old_value=left)]


def diff_number_node(left: nodes.NumberNode, right: nodes.NumberNode, indent: str) -> list[Action]:
    if left.value == right.value:
        return []

    return [ChangeNumberValue(right.value)]


def diff_arg_node(left: Node, right: Node, indent: str) -> list[Action]:
    diff: list[Action] = []
    # Target
    if id_from_el(left.target) != id_from_el(right.target):
        diff += [ReplaceTarget(new_value=right.target, old_value=left.target)]
    # Value
    if left.value is None and right.value is None:
        pass
    elif left.value is not None and right.value is not None:
        changes = compute_diff(left.value, right.value, indent=indent + INDENT)
        if changes:
            diff += [ChangeArg(right, changes=changes)]
    else:
        diff += [ReplaceAttr("value", right.value)]
    # Annotation
    if isinstance(left, nodes.DefArgumentNode):
        if left.annotation is None and right.annotation is None:
            pass
        elif left.annotation is not None and right.annotation is not None:
            changes = compute_diff(left.annotation, right.annotation, indent=indent + INDENT)
            if changes:
                diff += [ChangeAnnotation(right, changes=changes)]
        else:
            diff += [ReplaceAnnotation(right.annotation)]
    return diff


def diff_def_node(left: nodes.DefNode, right: nodes.DefNode, indent: str) -> list[Action]:
    diff: list[Action] = []
    # Name
    if left.name != right.name:
        right.old_name = left.name
        diff += [RenameDef(right)]

    # Args
    to_add, to_remove = diff_list(left.arguments, right.arguments)
    for arg in to_add:
        logging.debug("%s fun new arg %r", indent, short_display_el(arg))
        diff += [AddFunArg(arg, context=gather_context(arg, limit=1), on_new_line=arg.on_new_line)]
    if to_remove:
        for arg in to_remove:
            logging.debug("%s fun old arg %r", indent, short_display_el(arg))
        diff += [RemoveFunArgs(to_remove)]
    changed = changed_in_list(left.arguments, right.arguments, value_getter=_check_for_arg_changes)
    for old_arg, new_arg in changed:
        logging.debug("%s fun changed args %r", indent, short_display_el(new_arg))
        diff_arg = compute_diff(old_arg, new_arg, indent=indent + INDENT)
        if not old_arg.on_new_line and new_arg.on_new_line:
            rel_indent = len(new_arg.indentation) - len(new_arg.parent.parent.indentation)
            diff_arg += [ArgOnNewLine(indentation=rel_indent * " ")]
        if old_arg.on_new_line and not new_arg.on_new_line:
            diff_arg += [ArgRemoveNewLine()]
        if id_from_el(get_previous_arg(old_arg, to_remove)) != id_from_el(
            get_previous_arg(new_arg, to_remove)
        ):
            diff_arg += [MoveArg(context=gather_context(new_arg))]
        if diff_arg:
            diff += [ChangeDefArg(new_arg, changes=diff_arg)]

    # Comments in args
    diff += diff_list_comments(
        left.arguments, right.arguments, indent=indent, list_changer=ChangeDefArg
    )

    # Decorators
    to_add, to_remove = diff_list(left.decorators, right.decorators, key_getter=id_from_decorator)
    for decorator in to_add:
        diff += [AddDecorator(decorator, context=gather_context(decorator))]
    if to_remove:
        diff += [RemoveDecorators(to_remove)]
    for arg in to_add:
        logging.debug("%s fun new decorator %r", indent, short_display_el(arg))
    for arg in to_remove:
        logging.debug("%s fun old decorator %r", indent, short_display_el(arg))
    changed = changed_in_list(left.decorators, right.decorators, key_getter=id_from_decorator)
    for left_el, right_el in changed:
        logging.debug("%s fun changed decorator %r ", indent, right_el)
        diff_decorator = []
        if left_el.call and right_el.call:
            changes = compute_diff(left_el.call, right_el.call, indent=indent + INDENT)
            diff_decorator += [ChangeDecoratorArgs(right_el, changes=changes)]
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


def diff_import_node(
    left: nodes.FromImportNode, right: nodes.FromImportNode, indent: str
) -> list[Action]:
    to_add, to_remove = diff_list(left.targets, right.targets, key_getter=lambda t: t.value)
    diff: list[Action] = []
    if to_add:
        diff += [
            AddImports(
                list(to_add),
                one_per_line=right.targets.detect_one_per_line(),
                add_brackets=right.targets.has_brackets(),
            )
        ]
    if to_remove:
        diff += [RemoveImports(to_remove)]
    return diff


def diff_with_node(left: nodes.WithNode, right: nodes.WithNode, indent: str) -> list[Action]:
    diff: list[Action] = []
    if left.contexts.dumps() != right.contexts.dumps():
        logging.debug("%s changed contexts %r", indent, short_display_el(right.contexts))
        diff += [ReplaceAttr("contexts", right.contexts.copy())]

    diff += compute_diff_iterables(left, right, indent=indent)

    return diff


def diff_atom_trailer_node(
    left: nodes.AtomtrailersNode, right: nodes.AtomtrailersNode, indent: str
) -> list[Action]:
    diff: list[Action] = []

    if len(left) != len(right):
        return [Replace(new_value=right, old_value=left)]

    for index, (el_left, el_right) in enumerate(zip(left, right)):
        if not isinstance(el_left, type(el_right)):
            diff += [
                ChangeAtomtrailersEl(
                    el_left, index=index, changes=[Replace(new_value=el_right, old_value=el_left)]
                )
            ]
        else:
            el_diff = compute_diff(el_left, el_right, indent=indent + INDENT)
            if el_diff:
                diff += [ChangeAtomtrailersEl(el_left, index=index, changes=el_diff)]

    return [ChangeAtomTrailer(right, diff)]


def _check_for_arg_changes(arg: Node) -> str:
    endl = "\n" if arg.on_new_line else ""
    return endl + arg.dumps() + "_%d" % arg.index_on_parent


def diff_call_node(left: nodes.CallNode, right: nodes.CallNode, indent: str) -> list[Action]:
    diff: list[Action] = []

    # Added/Removed args
    to_add, to_remove = diff_list(left, right, key_getter=id_from_arg)
    for arg in to_add:
        logging.debug("%s call new arg %r", indent, short_display_el(arg))
    for arg in to_remove:
        logging.debug("%s call old arg %r", indent, short_display_el(arg))
    for arg in to_add:
        diff += [AddCallArg(arg, context=gather_context(arg, limit=1), on_new_line=arg.on_new_line)]
    if to_remove:
        diff += [RemoveCallArgs(to_remove)]

    changed = changed_in_list(
        left, right, key_getter=id_from_arg, value_getter=_check_for_arg_changes
    )

    # Changed args
    for old_arg, new_arg in changed:
        logging.debug("%s call changed args %r", indent, short_display_el(new_arg))
        diff_arg = compute_diff(old_arg, new_arg, indent=indent + INDENT)
        if not old_arg.on_new_line and new_arg.on_new_line:
            rel_indent = len(new_arg.indentation) - len(new_arg.parent.parent.indentation)
            diff_arg += [ArgOnNewLine(indentation=rel_indent * " ")]
        if old_arg.on_new_line and not new_arg.on_new_line:
            diff_arg += [ArgRemoveNewLine()]
        if id_from_el(get_previous_arg(old_arg, to_remove)) != id_from_el(
            get_previous_arg(new_arg, to_remove)
        ):
            diff_arg += [MoveArg(context=gather_context(new_arg))]
        if diff_arg:
            diff += [ChangeCallArg(new_arg, changes=diff_arg)]

    # Comments
    diff += diff_list_comments(left, right, indent=indent, list_changer=ChangeCallArg)

    # New lines for brackets
    if len(left) > 0 and left[-1].endl and len(right) > 0 and not right[-1].endl:
        diff += [RemoveCallEndl()]

    return diff


def diff_assignment_node(
    left: nodes.AssignmentNode, right: nodes.AssignmentNode, indent: str
) -> list[Action]:
    diff: list[Action] = []
    if left.target.value != right.target.value:
        diff += [ReplaceAttr("target", right.target)]

    el_diff = compute_diff(left.value, right.value, indent=indent + INDENT)
    if el_diff:
        diff += [ChangeAssignment(left, changes=el_diff)]

    return diff


def diff_class_node_decorators(
    left: nodes.ClassNode, right: nodes.ClassNode, indent: str
) -> list[Action]:
    diff: list[Action] = []

    to_add, to_remove = diff_list(left.decorators, right.decorators)
    for decorator in to_add:
        diff += [AddDecorator(decorator, context=gather_context(decorator))]
    if to_remove:
        diff += [RemoveDecorators(to_remove)]
    if to_add:
        logging.debug("%s class new decorators %r", indent, to_add)
    if to_remove:
        logging.debug("%s class old decorators %r", indent, to_remove)
    changed = changed_in_list(left.decorators, right.decorators)
    for left_el, right_el in changed:
        logging.debug("%s class changed decorator %r ", indent, right_el)
        diff_decorator = []
        if left_el.call and right_el.call:
            changes = compute_diff(left_el.call, right_el.call, indent=indent + INDENT)
            diff_decorator += [ChangeDecoratorArgs(right_el, changes=changes)]
        elif left_el.call:
            diff_decorator += [RemoveAllDecoratorArgs(None)]
        elif right_el.call:
            diff_decorator += [AddAllDecoratorArgs(right_el.call)]
        if diff_decorator:
            diff += [ChangeDecorator(left_el, changes=diff_decorator)]

    return diff


def _expand_bases(inherit_from: list[Node]) -> list[Node]:
    """Expand TupleNodes in inherit_from to individual base classes.

    RedBaron parses `class C(A, B)` as inherit_from=[TupleNode("A, B")]
    rather than [NameNode("A"), NameNode("B")]. This function flattens
    the list so we can compare individual bases.
    """
    result = []
    for item in inherit_from:
        if type(item) is nodes.TupleNode:
            result.extend(item.value)
        else:
            result.append(item)
    return result


def diff_class_node_bases(
    left: nodes.ClassNode, right: nodes.ClassNode, indent: str
) -> list[Action]:
    diff: list[Action] = []

    # Expand TupleNodes to get individual bases for comparison
    left_bases = _expand_bases(left.inherit_from)
    right_bases = _expand_bases(right.inherit_from)

    to_add, to_remove = diff_list(left_bases, right_bases)
    for base in to_add:
        diff += [AddBase(base.copy(), context=gather_context(base))]
    if to_remove:
        diff += [RemoveBases(to_remove)]
    if to_add:
        logging.debug("%s class new bases %r", indent, to_add)
    if to_remove:
        logging.debug("%s class old bases %r", indent, to_remove)
    changed = changed_in_list(left_bases, right_bases)
    for left_el, right_el in changed:
        logging.debug("%s class changed base %r ", indent, right_el)
        diff_base = compute_diff(left_el, right_el, indent=indent + INDENT)
        if diff_base:
            diff += [ChangeDecorator(left_el, changes=diff_base)]

    return diff


def diff_class_node(left: nodes.ClassNode, right: nodes.ClassNode, indent: str) -> list[Action]:
    diff: list[Action] = []

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
    diff += compute_diff_iterables(left.value, right.value, indent=indent + INDENT)

    return diff


def diff_if_else_block_node(
    left: nodes.IfelseblockNode, right: nodes.IfelseblockNode, indent: str
) -> list[Action]:
    diff = compute_diff_iterables(left.value, right.value, indent + INDENT)
    if diff:
        return [ChangeValue(right, changes=diff)]
    return []


def diff_if_node(left: nodes.IfNode, right: nodes.IfNode, indent: str) -> list[Action]:
    diff: list[Action] = []
    if left.test.dumps() != right.test.dumps():
        diff += [ChangeAttr("test", compute_diff(left.test, right.test, indent=indent + INDENT))]

    diff += compute_diff_iterables(left, right, indent=indent + INDENT)
    return diff


def diff_elif_node(left: nodes.ElifNode, right: nodes.ElifNode, indent: str) -> list[Action]:
    diff: list[Action] = []
    if left.test.dumps() != right.test.dumps():
        diff += [ChangeAttr("test", compute_diff(left.test, right.test, indent=indent + INDENT))]

    diff += compute_diff_iterables(left, right, indent=indent + INDENT)
    return diff


def diff_else_node(left: nodes.ElseNode, right: nodes.ElseNode, indent: str) -> list[Action]:
    return compute_diff_iterables(left, right, indent=indent + INDENT)


def diff_endl_node(left: nodes.EndlNode, right: nodes.EndlNode, indent: str) -> list[Action]:
    return []


def diff_return_node(left: nodes.ReturnNode, right: nodes.ReturnNode, indent: str) -> list[Action]:
    diff = compute_diff(left.value, right.value, indent=indent + INDENT)
    if diff:
        return [ChangeReturn(right, changes=diff)]
    return []


def diff_list_node(left: nodes.ListNode, right: nodes.ListNode, indent: str) -> list[Action]:
    diff = compute_diff_iterables(left.value, right.value, indent + INDENT)
    if diff:
        return [ChangeValue(right, changes=diff)]
    return []


def diff_tuple_node(left: nodes.TupleNode, right: nodes.TupleNode, indent: str) -> list[Action]:
    diff = compute_diff_iterables(left.value, right.value, indent + INDENT)
    if diff:
        return [ChangeValue(right, changes=diff)]
    return []


def diff_list_argument_node(
    left: nodes.ListArgumentNode, right: nodes.ListArgumentNode, indent: str
) -> list[Action]:
    return compute_diff(left.value, right.value, indent=indent + INDENT)


def diff_dict_argument_node(
    left: nodes.DictArgumentNode, right: nodes.DictArgumentNode, indent: str
) -> list[Action]:
    return compute_diff(left.value, right.value, indent=indent + INDENT)


def diff_dict_node(left: nodes.DictNode, right: nodes.DictNode, indent: str) -> list[Action]:
    diff: list[Action] = []

    to_add, to_remove = diff_list(left, right)

    for item in to_add:
        logging.debug("%s dict new key %r", indent, short_display_el(item.key))
        diff += [AddDictItem(item, previous_item=item.previous)]
    for item in to_remove:
        logging.debug("%s dict removed key %r", indent, short_display_el(item.key))
        diff += [RemoveDictItem(item)]

    changed = changed_in_list(left, right)
    for left_el, right_el in changed:
        logging.debug("%s dict changed key %r", indent, short_display_el(left_el.key))
        diff += [
            ChangeDictValue(
                left_el, changes=compute_diff(left_el.value, right_el.value, indent=indent + INDENT)
            )
        ]

    diff += diff_list_comments(left, right, indent=indent, list_changer=ChangeDictItem)

    return diff


def diff_for_node(left: nodes.ForNode, right: nodes.ForNode, indent: str) -> list[Action]:
    diff: list[Action] = []
    if left.target.dumps() != right.target.dumps():
        diff += [ReplaceAttr("target", right.target.copy())]

    if left.iterator.dumps() != right.iterator.dumps():
        diff += [ReplaceAttr("iterator", right.iterator.copy())]

    diff += compute_diff_iterables(left, right, indent=indent + INDENT)
    diff += diff_else_node_for_loops(left, right, indent)
    return diff


def diff_while_node(left: nodes.WhileNode, right: nodes.WhileNode, indent: str) -> list[Action]:
    diff: list[Action] = []

    if left.test.dumps() != right.test.dumps():
        diff += [ReplaceAttr("test", right.test.copy())]

    diff += compute_diff_iterables(left, right, indent=indent + INDENT)
    diff += diff_else_node_for_loops(left, right, indent)
    return diff


def diff_else_node_for_loops(left: Node, right: Node, indent: str) -> list[Action]:
    diff: list[Action] = []

    if left.else_ and right.else_:
        diff_else = compute_diff_iterables(
            left.else_ or [], right.else_ or [], indent=indent + INDENT
        )
        if diff_else:
            diff += [ChangeElseNode(diff_else)]
    elif left.else_:
        diff += [RemoveElseNode()]
    elif right.else_:
        diff += [AddElseNode(right.else_)]

    return diff


def diff_pass_node(left: nodes.PassNode, right: nodes.PassNode, indent: str) -> list[Action]:
    return []


def diff_inline_vs_multiline(left: Node, right: Node, indent: str) -> list[Action]:
    if left.value.header and not right.value.header:
        return [MakeInline()]
    if not left.value.header and right.value.header:
        return [MakeMultiline()]
    return []


def diff_try_node(left: nodes.TryNode, right: nodes.TryNode, indent: str) -> list[Action]:
    diff: list[Action] = []

    diff += compute_diff_iterables(left, right, indent=indent + INDENT)
    diff += diff_excepts_node(left, right, indent)
    diff += diff_else_node_for_loops(left, right, indent)

    # Handle finally block
    if not left.finally_ and right.finally_:
        logging.debug("%s added finally block", indent)
        diff += [AddFinally(right.finally_)]

    return diff


def diff_excepts_node(left: nodes.TryNode, right: nodes.TryNode, indent: str) -> list[Action]:
    diff: list[Action] = []

    # Handle changes to existing except clauses
    for index, (left_except, right_except) in enumerate(zip(left.excepts, right.excepts)):
        diff_except = compute_diff_iterables(
            left_except.value, right_except.value, indent=indent + INDENT
        )
        if diff_except:
            diff += [ChangeExceptsNode(index, diff_except)]

    # Handle added except clauses
    if len(right.excepts) > len(left.excepts):
        for except_node in right.excepts[len(left.excepts) :]:
            logging.debug("%s added except clause %r", indent, short_display_el(except_node))
            diff += [AddExcept(except_node)]

    return diff


def diff_string_node(left: nodes.StringNode, right: nodes.StringNode, indent: str) -> list[Action]:
    dmp = diff_match_patch()
    patches = dmp.patch_make(left.value, right.value)
    diff = dmp.patch_toText(patches)
    return [ChangeString(left, changes=diff)]


def diff_name_node(left: nodes.NameNode, right: nodes.NameNode, indent: str) -> list[Action]:
    return [Replace(new_value=right, old_value=left)]


def diff_list_comments(
    left: ProxyList, right: ProxyList, indent: str, list_changer: type[Action]
) -> list[Action]:
    def _comment_getter(el):
        sep = el.associated_sep
        if sep is None:
            return None
        if sep.find("comment"):
            return sep.dumps()
        return None

    diff = []
    changed = changed_in_list(left, right, value_getter=_comment_getter)

    for left_el, right_el in changed:
        if left_el.associated_sep and left_el.associated_sep.second_formatting:
            if right_el.associated_sep and right_el.associated_sep.second_formatting:
                # changes = [ChangeSepComment(changes=compute_diff_iterables(
                #     left_el.associated_sep.second_formatting,
                #     right_el.associated_sep.second_formatting,
                #     indent=indent+INDENT))]
                changes = [
                    ChangeSepComment(
                        changes=[
                            Replace(
                                right_el.associated_sep.second_formatting,
                                left_el.associated_sep.second_formatting,
                            )
                        ]
                    )
                ]
            elif not right_el.associated_sep or not right_el.associated_sep.second_formatting:
                # Remove comment
                changes = [RemoveSepComment()]
        elif right_el.associated_sep and right_el.associated_sep.second_formatting:
            # Add comment
            changes = [AddSepComment(right_el)]
        else:
            continue
        diff += [list_changer(left_el, changes=changes)]

    return diff


def diff_assert_node(left: nodes.AssertNode, right: nodes.AssertNode, indent: str) -> list[Action]:
    changes = compute_diff(left.value, right.value)
    if changes:
        return [ChangeAttr("value", changes)]
    return []


def diff_comparison_node(
    left: nodes.ComparisonNode, right: nodes.ComparisonNode, indent: str
) -> list[Action]:
    diff: list[Action] = []

    changes = compute_diff(left.value, right.value)
    if changes:
        diff += [ChangeAttr("value", changes)]

    changes = compute_diff(left.first, right.first)
    if changes:
        diff += [ChangeAttr("first", changes)]

    changes = compute_diff(left.second, right.second)
    if changes:
        diff += [ChangeAttr("second", changes)]

    return diff


COMPUTE_DIFF_ONE_CALLS = {
    RedBaron: diff_redbaron,
    nodes.CommentNode: diff_replace,
    nodes.AssociativeParenthesisNode: diff_replace,
    nodes.NumberNode: diff_number_node,
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
    nodes.ElifNode: diff_elif_node,
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
    nodes.TryNode: diff_try_node,
    nodes.StringNode: diff_string_node,
    nodes.NameNode: diff_name_node,
    nodes.AssertNode: diff_assert_node,
    nodes.ComparisonNode: diff_comparison_node,
}
