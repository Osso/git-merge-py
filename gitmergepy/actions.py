import logging

from redbaron import nodes
from redbaron.base_nodes import (BaseNode,
                                 NodeList)
from redbaron.node_mixin import CodeBlockMixin
from redbaron.utils import indent_str

from diff_match_patch import diff_match_patch

from .applyier import apply_changes
from .conflicts import (add_conflict,
                        add_conflicts)
from .context import (AfterContext,
                      find_context,
                      find_context_with_reduction,
                      gather_after_context,
                      gather_context)
from .matcher import (CODE_BLOCK_SIMILARITY_THRESHOLD,
                      code_block_similarity,
                      find_class,
                      find_el,
                      find_func,
                      find_import,
                      find_imports,
                      find_key,
                      same_arg_guess,
                      same_el_guess)
from .tools import (apply_diff_to_list,
                    as_from_contexts,
                    empty_lines,
                    get_args_names,
                    get_call_els,
                    id_from_arg,
                    id_from_el,
                    merge_imports,
                    same_el,
                    short_context,
                    short_display_el,
                    short_display_list,
                    skip_context_endl,
                    sort_imports)
from .tools_actions import remove_with
from .tools_lists import insert_at_context_coma_list

BaseNode.new = False
BaseNode.already_processed = False


def cursor_index(tree):
    try:
        tree.cursor
    except AttributeError:
        cursor_index_ = -1
    else:
        cursor_index_ = tree.cursor.index_on_parent

    return cursor_index_


def tree_after_cursor(tree):
    return tree[cursor_index(tree)+1:]


def set_cursor(tree, el):
    # logging.debug('setting cursor to %s', short_display_el(el))
    tree.cursor = el


def first_index_after_cursor(tree, indexes):
    assert indexes

    cursor_index_ = cursor_index(tree)
    index = None
    for index in indexes:
        if index > cursor_index_:
            break

    return index


class BaseEl:
    def __init__(self, el):
        self.el = el

    def __repr__(self):
        return "<%s el=\"%s\">" % (self.__class__.__name__,
                                   short_display_el(self.el))


class ElWithContext(BaseEl):
    def __init__(self, el, context):
        super().__init__(el)
        self.context = context

    def __repr__(self):
        return "<%s el=\"%s\" context=%r>" % (
            self.__class__.__name__, short_display_el(self.el),
            short_context(self.context))


class RemoveEls:
    def __init__(self, to_remove, context):
        assert to_remove
        self.to_remove = to_remove
        self.context = context

    def __repr__(self):
        return "<%s to_remove=\"%s\" context=%r>" % (
            self.__class__.__name__, short_display_list(self.to_remove),
            short_context(self.context))

    def find_anchor(self, tree):
        # We modify this
        to_remove = self.to_remove.copy()

        skipped_to_remove = []
        anchor_el = None
        for el_to_remove in self.to_remove:
            if isinstance(el_to_remove, (nodes.SpaceNode, nodes.EmptyLineNode)) and not empty_lines(self.to_remove):
                logging.debug(". skipping empty space anchor")
            else:
                logging.debug(". looking for el %r",
                              short_display_el(el_to_remove))
                # Removed els were not found in the new tree, therefore
                # the context gathered is from the old tree
                anchor_el = find_el(tree, el_to_remove, context=self.context,
                                    look_in_old_tree_first=True)
                if anchor_el:
                    logging.debug(". el found")
                    break

                logging.debug(". el not found")

            assert el_to_remove is to_remove[0]
            self.context.insert(0, el_to_remove)
            skipped_to_remove.append(to_remove.pop(0))

        if anchor_el:
            for el in reversed(skipped_to_remove):
                if same_el(anchor_el.previous, el):
                    anchor_el = anchor_el.previous
                    to_remove.insert(0, skipped_to_remove.pop())

        return anchor_el, to_remove

    def apply(self, tree):
        logging.debug("removing els %s", short_display_list(self.to_remove))
        logging.debug(". context %r", short_context(self.context))

        anchor_el, to_remove = self.find_anchor(tree)
        if anchor_el is None:
            return []

        def delete_el(el):
            tree.hide(el)
            set_cursor(tree, el)
            context.insert(0, el)
            return index + 1

        context = self.context.copy()
        index = tree.index(anchor_el)
        for el_to_remove in to_remove:
            try:
                el = tree[index]
            except IndexError:
                # End of tree, we can only assume the other elements
                # are already removed
                break
            logging.debug(". removing el %r", short_display_el(el_to_remove))
            if same_el_guess(el, el_to_remove):
                index = delete_el(el)
            else:
                logging.debug(".. not matching %r", short_display_el(el))
                logging.debug(".. looking for new index")
                updated_el = find_el(tree, el_to_remove, context)
                if updated_el:
                    logging.debug(".. found new index")
                    index = tree.index(updated_el)
                    index = delete_el(updated_el)

        return []


class AddImports:
    def __init__(self, imports, one_per_line=False, add_brackets=False):
        self.imports = imports
        self.one_per_line = one_per_line
        self.add_brackets = add_brackets

    def __repr__(self):
        return "<%s imports=%r>" % (self.__class__.__name__,
                                    ', '.join(short_display_el(el)
                                              for el in self.imports))

    def apply(self, tree):
        logging.debug(". adding imports")
        existing_imports = set(el.value for el in tree.targets)

        # Never add brackets for single import
        if self.add_brackets and (tree.targets or len(self.imports) > 1):
            tree.targets.add_brackets()

        for import_el in self.imports:
            if import_el.value not in existing_imports:
                logging.debug(".. adding import: %r", import_el.value)
                if import_el.endl:
                    tree.targets.append_with_new_line(import_el.copy())
                else:
                    tree.targets.append(import_el.copy())
        sort_imports(tree.targets)

        if self.one_per_line:
            for _, sep in tree.targets._data:
                if sep:
                    sep.second_formatting = ["\n"]
            tree.targets._synchronise()

        return []


class RemoveImports:
    def __init__(self, imports):
        self.imports = imports

    def __repr__(self):
        return "<%s imports=%r>" % (self.__class__.__name__,
                                    ', '.join(short_display_el(el)
                                              for el in self.imports))

    def apply(self, tree):
        logging.debug(". removing imports")
        for import_el in self.imports:
            logging.debug(".. removing import %r", short_display_el(import_el))

        apply_diff_to_list(tree.targets, to_add=[], to_remove=self.imports,
                           key_getter=lambda t: t.value)
        if len(tree.targets) == 1:
            tree.targets.remove_brackets()
            tree.targets.header = []
            tree.targets._synchronise()

        return []


class BaseAddEls:
    def __init__(self, to_add, context, after_context=None):
        assert context
        self.to_add = to_add
        self.context = context
        self.after_context = after_context
        self.added = []

    def __repr__(self):
        return "<%s to_add=\"%s\" context=%r>" % (
            self.__class__.__name__,
            ', '.join(short_display_el(el) for el in self.to_add),
            short_context(self.context))

    def add_el(self, el):
        self.to_add.append(el)
        if isinstance(self.context, AfterContext):
            first_in_context = self.context.pop(0)
            assert el is first_in_context
            self.context = gather_after_context(self.to_add[-1])

    def apply(self, tree):
        logging.debug("adding els")
        # Make it one insert branch by using index
        if self.context[-1] is None and False:
            if isinstance(self.context, AfterContext):
                logging.debug(". at the end")
                index = len(tree)
            else:
                logging.debug(". at the beginning")
                index = skip_context_endl(tree, self.context)
        else:
            logging.debug(". context %r", short_context(self.context))
            indexes = find_context_with_reduction(tree, self.context)

            if not indexes and self.after_context:
                logging.debug(". context not found, looking for after context "
                              "%r", short_context(self.after_context))
                indexes = find_context_with_reduction(tree, self.after_context)

            if not indexes:
                logging.debug(". context not found")
                if empty_lines(self.to_add):
                    return []
                if (isinstance(self.context[0], (nodes.DefNode,
                                                 nodes.ClassNode)) and
                        all(isinstance(el, nodes.CommentNode)
                            for el in self.to_add)):
                    return []
                return [Conflict(self.to_add, self,
                                 reason="context not found")]

            index = indexes[0]
            if len(indexes) > 1:
                index = first_index_after_cursor(tree, indexes)

            if index == 0:
                at = "the beginning"
            else:
                el = tree[index-1]
                at = short_display_el(el)
                # Mostly in case an inline comment has been added
                if self.to_add[0].on_new_line and not el.endl:
                    logging.debug("    after %r (missing new line)", at)
                    while el.next and isinstance(el.next, nodes.CommentNode) and not el.endl:
                        el = el.next
                        index = tree.index(el) + 1
                        at = short_display_el(el)

            logging.debug("    after %r", at)

        for el_to_add in self.to_add:
            logging.debug("    el %r", short_display_el(el_to_add))
            self._insert_el(el_to_add, index, tree)
            index += 1

        return []

    def _insert_el(self, el_to_add, index, tree):
        if index > 0 and not el_to_add.on_new_line:
            tree[index-1].remove_endl()

        el = el_to_add.copy()
        el.new = True
        # Add endl for code proxy lists
        endl = isinstance(el_to_add.associated_sep, nodes.EndlNode)
        if el_to_add.associated_sep:
            endl = endl or bool(el_to_add.associated_sep.endl)

        if endl:
            tree.insert_with_new_line(index, el)
        else:
            tree.insert(index, el)

        self.added.append(el)

        set_cursor(tree, el)

        # Handle comma separated lists and such that don't add a new line
        # by default
        if el_to_add.on_new_line and not el.on_new_line:
            tree.put_on_new_line(el)


class AddEls(BaseAddEls):
    pass


class AddChangeEl(BaseAddEls):
    def __init__(self, to_add, changes, context, after_context=None):
        super().__init__([to_add], context, after_context=after_context)
        self.changes = changes or []

    def apply(self, tree):
        conflicts = super().apply(tree)
        if conflicts:
            return conflicts
        return apply_changes(self.added[0], self.changes)


class ReplaceEls(BaseAddEls):
    def __init__(self, to_add, to_remove, context):
        self.to_remove = to_remove
        super().__init__(to_add=to_add, context=context)

    def __repr__(self):
        return "<%s\nto_add:\n* %s\nto_remove:\n* %s\ncontext:\n* %s\n>" % (
            self.__class__.__name__,
            '\n* '.join(short_display_el(el).lstrip(" ") for el in self.to_add),
            '\n* '.join(short_display_el(el).lstrip(" ") for el in self.to_remove),
            '\n* '.join(line.lstrip(" ") for line in short_context(self.context).split("|")))

    def match_to_remove_at_index(self, tree, index):
        if index >= len(tree):
            return False
        if tree[index].hidden:
            return False

        offset = 0
        # match all to_remove items
        for el in self.to_remove:
            while index+offset < len(tree) and tree[index+offset].hidden:
                offset += 1
            try:
                if not same_el_guess(tree[index+offset], el):
                    if offset > 0 and isinstance(tree[index+offset], nodes.CommentNode):
                        continue
                    return False
            except IndexError:
                return False
            offset += 1

        return True

    def _look_for_context(self, tree):
        matches = find_context_with_reduction(tree, self.context)
        return [index for index in matches
                if self.match_to_remove_at_index(tree, index)]

    def _look_for_els(self, tree):
        return [index for index in range(len(tree))
                if self.match_to_remove_at_index(tree, index)]

    def apply(self, tree):
        logging.debug("replacing els")
        logging.debug(". context %r", short_context(self.context))

        indexes = self._look_for_context(tree)
        if not indexes:
            logging.debug(". cannot match context")
            indexes = self._look_for_els(tree)
        else:
            logging.debug(". matched context")

        if not indexes:
            logging.debug(". cannot match els")
            matches = find_context_with_reduction(tree, self.context)
            if len(matches) == 1:
                indexes = matches
        else:
            logging.debug(". matched els")

        if not indexes:
            logging.debug(". cannot match reduced context")
            add_conflicts(tree, [Conflict(self.to_remove, self,
                                        reason="Cannot match els")])
            return []
        else:
            logging.debug(". matched reduced context")

        index = indexes[0]
        if len(indexes) > 1:
            index = first_index_after_cursor(tree, indexes)

        logging.debug(". adding els")
        for el_to_add in self.to_add:
            logging.debug(".. adding %r", short_display_el(el_to_add))
            self._insert_el(el_to_add, index, tree)
            index += 1

        logging.debug(". removing els")
        offset = 0
        for el_to_remove in self.to_remove:
            try:
                el = tree[index+offset]
            except IndexError:
                # End of tree, we can only assume the other elements
                # are already removed
                break
            if (offset > 0 and isinstance(el, nodes.CommentNode) and
                    not isinstance(el_to_remove, nodes.CommentNode)):
                tree.hide(el)
                el = el.next
                offset += 1

            if not same_el_guess(el, el_to_remove):
                logging.debug("... el not matching")
                continue

            logging.debug(".. removing %r @ %d", short_display_el(el), el.index_on_parent)
            tree.hide(el)
            set_cursor(tree, el)
            offset += 1

        return []


class Replace:
    def __init__(self, new_value, old_value):
        self.new_value = new_value
        self.old_value = old_value

    def apply(self, tree):
        if tree.dumps() != self.new_value.dumps():
            if tree.dumps() != self.old_value.dumps():
                return [Conflict([tree], self,
                                 reason="Different from old value %r" %
                                        short_display_el(self.old_value))]
        tree.replace(self.new_value.copy())
        return []

    def __repr__(self):
        return "<%s new_value=%r>" % (self.__class__.__name__,
                                      short_display_el(self.new_value))


class ReplaceTarget(Replace):
    def apply(self, tree):
        tree.target = self.new_value
        return []


class ReplaceAttr:
    def __init__(self, attr_name, attr_value):
        self.attr_name = attr_name
        self.attr_value = attr_value

    def apply(self, tree):
        logging.debug("changing %s to %s", self.attr_name, self.value_str)
        setattr(tree, self.attr_name, self.attr_value)
        return []

    @property
    def value_str(self):
        try:
            self.attr_value.dumps
        except AttributeError:
            value = self.attr_value
        else:
            value = short_display_el(self.attr_value)
        return value

    def __repr__(self):
        return "<%s %s=%r>" % (self.__class__.__name__, self.attr_name,
                               self.value_str)


class ReplaceAnnotation:
    def __init__(self, new_value):
        self.new_value = new_value

    def apply(self, tree):
        if self.new_value is not None and tree.annotation is None:
            tree.annotation_second_formatting = self.new_value.parent.annotation_second_formatting
        if self.new_value is not None:
            tree.annotation = self.new_value.copy()
        else:
            tree.annotation = None
        return []

    def __repr__(self):
        return "<%s new_value=%r>" % (self.__class__.__name__,
                                      short_display_el(self.new_value))


class RemoveAllDecoratorArgs(BaseEl):
    def apply(self, tree):
        tree.call = None
        return []


class AddAllDecoratorArgs(BaseEl):
    def apply(self, tree):
        tree.call = self.el.copy()
        return []


class ChangeEl(BaseEl):
    write_conflicts = True

    def __init__(self, el, changes, context=None):
        super().__init__(el)
        self.changes = changes
        self.context = context

    def __repr__(self):
        changes_str = "\n".join(indent_str(str(change), ".")
                                for change in self.changes)
        return "<%s el=\"%s\" context=%r> changes=\n%s" % (
            self.__class__.__name__, short_display_el(self.el),
            short_context(self.context), changes_str)

    def apply(self, tree):
        logging.debug("changing %s context %s", short_display_el(self.el),
                      short_context(self.context))
        el = find_el(tree, self.el, self.context)
        if el is None:
            logging.debug(". not found")
            add_conflicts(tree, [Conflict([self.el], self, 'el not found')])
        else:
            logging.debug(". found")
            conflicts = apply_changes(el, self.changes)

            set_cursor(tree, el)

            if self.write_conflicts:
                add_conflicts(el, conflicts)
            else:
                return conflicts
        return []


class ChangeAttr:
    def __init__(self, attr_name, changes):
        self.attr_name = attr_name
        self.changes = changes

    def __repr__(self):
        changes_str = "\n".join(indent_str(str(change), ".")
                                for change in self.changes)
        return "<%s el=\"%s\" changes=\n%s>" % (
            self.__class__.__name__, self.attr_name, changes_str)

    def apply(self, tree):
        try:
            attr = getattr(tree, self.attr_name)
        except AttributeError:
            return [Conflict([], self,
                             "element has no attr %s" % self.attr_name)]
        return apply_changes(attr, self.changes)


class ChangeValue(ChangeEl):
    write_conflicts = False

    def apply(self, tree):
        return apply_changes(tree.value, self.changes)


class ChangeReturn(ChangeEl):
    def apply(self, tree):
        logging.debug(". changing %s", short_display_el(tree))
        conflicts = apply_changes(tree.value, self.changes)
        add_conflicts(tree, conflicts)
        return []


class ChangeCall(ChangeEl):
    pass


class ChangeDecoratorArgs(ChangeEl):
    def apply(self, tree):
        return apply_changes(tree.call, self.changes)


class ChangeArg(ChangeEl):
    def apply(self, tree):
        return apply_changes(tree.value, self.changes)


class ChangeAnnotation(ChangeEl):
    def apply(self, tree):
        return apply_changes(tree.annotation, self.changes)


class ChangeDefArg(ChangeEl):
    def get_args(self, tree):
        return tree.arguments

    def apply(self, tree):
        logging.debug(". changing arg %s", short_display_el(self.el))
        for arg in self.get_args(tree):
            if id_from_arg(arg) == id_from_arg(self.el):
                logging.debug(".. found")
                return apply_changes(arg, self.changes)
        logging.debug(".. not found")
        return []

    def __repr__(self):
        return "<%s el=%r changes=%r>" % (self.__class__.__name__,
                                          short_display_el(self.el),
                                          self.changes)


class ChangeCallArg(ChangeDefArg):
    def get_args(self, tree):
        return tree


class ArgOnNewLine:
    def __init__(self, indentation=None):
        self.indentation = indentation

    def __repr__(self):
        return "<%s indent=\"%s\">" % (self.__class__.__name__, self.indentation)

    def apply(self, tree):
        logging.debug(". putting arg %s on a new line", short_display_el(tree))
        tree.parent.put_on_new_line(tree, indentation=self.indentation)
        return []


class ArgRemoveNewLine:
    def __repr__(self):
        return "<%s>" % self.__class__.__name__

    def apply(self, tree):
        logging.debug(". remove arg %s new line", short_display_el(tree))
        tree.parent.put_on_same_line(tree)
        return []


class RemoveCallEndl:
    def __repr__(self):
        return "<%s>" % (self.__class__.__name__)

    def apply(self, tree):
        logging.debug(". removing new line before brackets")
        tree[-1].associated_sep = []
        tree.value.footer = []
        tree.value._synchronise()
        return []


class Conflict:
    def __init__(self, els, change, reason='', insert_before=True):
        self.els = els
        self.change = change
        self.reason = reason
        self.insert_before = insert_before

    def __repr__(self):
        return "<%s els=\"%s\" change=%r reason=%r>" % (
            self.__class__.__name__,
            ', '.join(short_display_el(el) for el in self.els),
            self.change, self.reason)


class ChangeFun(ChangeEl):
    def apply(self, tree):
        logging.debug("changing fun %r", short_display_el(self.el))
        el = find_func(tree, self.el)
        if not el and hasattr(self.el, 'old_name'):
            tmp_el = self.el.copy()
            tmp_el.name = self.el.old_name
            el = find_func(tree, tmp_el)

        if el:
            logging.debug(". found")
            conflicts = apply_changes(el, self.changes)

            add_conflicts(el, conflicts)

        return []


class ChangeImport(ChangeEl):
    def __init__(self, el, changes, can_be_added_as_is=False, context=None):
        super().__init__(el, changes=changes, context=context)
        self.can_be_added_as_is = can_be_added_as_is

    def __repr__(self):
        return "<%s el=\"%s\" changes=%r context=%r>" % (
            self.__class__.__name__, short_display_el(self.el), self.changes,
            short_context(self.context))

    def apply(self, tree):
        logging.debug("changing import %r", short_display_el(self.el))

        els = find_imports(tree, self.el)
        if els:
            logging.debug(". found")
            el = els[0]
            if len(els) > 1:
                logging.debug(". merging imports")
                merge_imports(els)
                logging.debug(". done merging")
        else:
            logging.debug(". not found")
            if not any(isinstance(c, AddImports) for c in self.changes):
                return []

            logging.debug(". adding")
            conflicts = AddEls([self.el], context=self.context).apply(tree)
            if conflicts:
                # Context not found, insert at the beginning
                tree.insert_with_new_line(0, self.el.copy())
            if self.can_be_added_as_is:
                # all the imports in self.el are to be added
                return []
            el = find_import(tree, self.el)
            el.targets.clear()
            el.targets.remove_brackets()

        return apply_changes(el, self.changes)


class ChangeClass(ChangeEl):
    def __init__(self, el, changes, context=None, old_name=None):
        super().__init__(el, changes=changes, context=context)
        self.old_name = old_name

    def __repr__(self):
        return "<%s el=\"%s\" changes=%r context=%r old_name=%r>" % (
            self.__class__.__name__, short_display_el(self.el), self.changes,
            short_context(self.context), self.old_name)

    def apply(self, tree):
        el = find_class(tree, self.el)
        if not el and self.old_name:
            tmp_el = self.el.copy()
            tmp_el.name = self.old_name
            el = find_class(tree, tmp_el)

        if el:
            logging.debug("changing class %r", short_display_el(el))
            conflicts = apply_changes(el, self.changes)
            add_conflicts(el, conflicts)
        else:
            logging.debug("    not found %r", short_display_el(self.el))
        return []


class EnsureEmptyLines:
    def __init__(self, lines):
        self.lines = lines

    def __repr__(self):
        return "<%s %r>" % (self.__class__.__name__,
                                        self.lines)

    def apply(self, tree):
        index = tree.index_on_parent + 1
        parent = tree.parent

        # no new lines at the end
        if not tree.next:
            return []

        for _ in self.lines:
            if not isinstance(parent.get(index, None), nodes.EmptyLineNode):
                new_line = nodes.EmptyLineNode()
                new_line.new = True
                parent.insert_with_new_line(index, new_line)
            index += 1
        return []


class MoveElWithId(ChangeEl):
    def __init__(self, el, changes, context=None, old_empty_lines=None):
        super().__init__(el, changes=changes, context=context)
        self.old_empty_lines = old_empty_lines or []

    def __repr__(self):
        return "<%s el=\"%s\" changes=%r context=%r empty_lines=%r>" % (
            self.__class__.__name__, short_display_el(self.el), self.changes,
            short_context(self.context), self.old_empty_lines)

    def apply(self, tree):
        fun = self.finder(tree, self.el)

        # If function still exists, move it then apply changes
        if not fun:
            return []

        if gather_context(fun) == self.context:
            logging.debug("fun already in position %r", short_display_el(fun))
            return []

        logging.debug("moving fun %r", short_display_el(fun))
        indexes = find_context_with_reduction(tree, self.context)
        if len(indexes) == 1:
            index = indexes[0]
            tree.hide(fun)
            line = fun.next
            for _ in self.old_empty_lines:
                if not isinstance(line, nodes.EmptyLineNode):
                    break
                tree.hide(line)
                line = line.next

            try:
                while isinstance(tree[index], nodes.EmptyLineNode):
                    index += 1
            except IndexError:
                pass
            new_fun = fun.copy()
            new_fun.new = True
            tree.insert(index, new_fun)
        else:
            new_fun = fun

        conflicts = apply_changes(new_fun, self.changes)
        add_conflicts(tree, conflicts)
        return []


class MoveFun(MoveElWithId):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.finder = find_func


class MoveClass(MoveElWithId):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.finder = find_class


class ChangeAssignment(ChangeEl):
    def apply(self, tree):
        return apply_changes(tree.value, self.changes)


class ChangeAtomTrailer(ChangeEl):
    def apply(self, tree):
        if (not isinstance(tree, nodes.AtomtrailersNode)
                or len(tree.value.node_list) != len(self.el.value.node_list)):
            tree.replace(self.el.copy())
            return []
        return apply_changes(tree, self.changes)


class ChangeAtomtrailersEl(ChangeEl):
    def __init__(self, el, changes, index):
        super().__init__(el, changes=changes)
        self.index = index

    def apply(self, tree):
        if not isinstance(tree, nodes.AtomtrailersNode):
            return [Conflict([self.el], self, 'tree is not atom trailer node')]
        try:
            el = tree[self.index]
        except IndexError:
            return [Conflict([self.el], self, 'calls elements not matching')]

        return apply_changes(el, self.changes)


class ChangeAtomtrailersCall(ChangeEl):
    def __init__(self, el, changes, index):
        super().__init__(el, changes=changes)
        self.index = index

    def apply(self, tree):
        calls_els = get_call_els(tree)
        try:
            el = calls_els[self.index]
        except IndexError:
            return [Conflict([self.el], self, 'calls elements not matching')]

        return apply_changes(el, self.changes)


class ChangeDecorator(ChangeEl):
    def __init__(self, el, changes, context=None):
        assert isinstance(el, nodes.DecoratorNode)
        super().__init__(el, changes=changes, context=context)

    def apply(self, tree):
        for decorator in tree.decorators:
            if id_from_el(decorator) == id_from_el(self.el):
                return apply_changes(decorator, self.changes)
        return []


class AddFunArg:
    def __init__(self, arg, context, on_new_line):
        self.arg = arg
        self.context = context
        self.on_new_line = on_new_line

    def __repr__(self):
        return "<%s arg=%r context=%r>" % (self.__class__.__name__,
                                           short_display_el(self.arg),
                                           short_context(self.context))

    def get_args(self, tree):
        return tree.arguments

    def apply(self, tree):
        if not isinstance(tree, (nodes.DefNode, nodes.CallNode)):
            return [Conflict([self.arg], self, 'tree is not a def node')]

        args = self.get_args(tree)
        arg = self.arg.copy()

        if id_from_el(arg) in get_args_names(args):
            logging.debug(". arg %r already exists",
                          short_display_el(self.arg))
            return []

        logging.debug(". adding arg %r to %r, new_line=%r",
                      short_display_el(self.arg), short_display_el(args),
                      self.on_new_line)

        if not insert_at_context_coma_list(arg, self.context, args,
                                           on_new_line=self.on_new_line):
            args.append(arg)
        return []

    def make_conflict(self, reason):
        el = self.arg.parent.parent.copy()
        el.decorators.clear()
        el.value.clear()
        return Conflict([el], self, reason=reason)


class AddCallArg(AddFunArg):
    def get_args(self, tree):
        return tree

    def make_conflict(self, reason):
        return Conflict([self.arg.parent.parent], self, reason=reason)


class AddDecorator(ElWithContext):
    def apply(self, tree):
        decorator = self.el.copy()
        logging.debug(". adding decorator %r to %r",
                      short_display_el(self.el), short_display_el(tree))
        context = self.context.copy()
        if isinstance(context[0], nodes.EndlNode):
            del context[0]
        logging.debug(".. context %s", short_context(context))
        indexes = find_context(self.get_elements(tree), context)
        if indexes:
            index = indexes[0]
            logging.debug(".. inserting at %d", index)
            self.get_elements(tree).insert(index, decorator)
        else:
            logging.debug(".. context not found, appending")
            self.get_elements(tree).append(decorator)
        return []

    @staticmethod
    def get_elements(tree):
        return tree.decorators


class AddBase(AddDecorator):
    @staticmethod
    def get_elements(tree):
        return tree.inherit_from


class RemoveFunArgs:
    def __init__(self, args):
        self.args = args

    def __repr__(self):
        return "<%s args=%r>" % (self.__class__.__name__,
                                 [id_from_el(arg) for arg in self.args])

    def get_args(self, tree):
        return tree.arguments

    def apply(self, tree):
        to_remove_values = set(id_from_el(el) for el in self.args)
        args = self.get_args(tree)
        for el in list(args):
            if id_from_el(el) in to_remove_values:
                logging.debug(". removing arg %r from %r",
                              short_display_el(el), short_display_el(args))
                if el.endl:
                    el.put_on_new_line()
                args.remove(el)
        return []


class RemoveCallArgs(RemoveFunArgs):
    def get_args(self, tree):
        return tree


class RemoveDecorators(RemoveFunArgs):
    def get_args(self, tree):
        return tree.decorators

    def apply(self, tree):
        to_remove_values = set(id_from_el(el) for el in self.args)
        args = self.get_args(tree)
        for el in args:
            if id_from_el(el) in to_remove_values:
                args.remove(el)
        return []


class RemoveBases(RemoveDecorators):
    def get_args(self, tree):
        return tree.inherit_from

    def apply(self, tree):
        to_remove_values = set(id_from_el(el) for el in self.args)
        args = self.get_args(tree)
        for el in args:
            if id_from_el(el) in to_remove_values:
                args.remove(el)
        return []


class RemoveWith(ElWithContext):
    def apply(self, tree):
        logging.debug('removing "with"')
        el_node_as = as_from_contexts(self.el.contexts)

        # Similar
        same_with_nodes = []
        similar_with_nodes = []
        context_with_nodes = []
        previous_el = None
        for el in tree:
            if isinstance(el, nodes.WithNode):
                with_node_as = as_from_contexts(el.contexts)
                similiarity = code_block_similarity(el.value, self.el.value)
                if with_node_as == el_node_as or similiarity == 1:
                    same_with_nodes += [el]
                if with_node_as & el_node_as or similiarity > CODE_BLOCK_SIMILARITY_THRESHOLD:
                    similar_with_nodes += [el]
                    if self.context:
                        if (self.context[-1] is None and previous_el is None or
                           (self.context[-1] and
                                same_el(previous_el, self.context[-1]))):
                            context_with_nodes += [el]
            if not isinstance(el, nodes.EndlNode):
                previous_el = el

        if not similar_with_nodes:
            logging.debug('. no nodes found')
            # No with node at all, probably already removed
            return []
        elif len(same_with_nodes) == 1:
            logging.debug('. same node found')
            with_node = same_with_nodes[0]
        elif len(similar_with_nodes) == 1:
            logging.debug('. similar node found')
            with_node = similar_with_nodes[0]
        elif len(context_with_nodes) == 1:
            logging.debug('. similar with context node found')
            with_node = context_with_nodes[0]
        elif len(same_with_nodes) > 1:
            indexes = [el.index_on_parent for el in same_with_nodes]
            index = first_index_after_cursor(tree, indexes)
            with_node = tree[index]
        elif len(similar_with_nodes) > 1:
            indexes = [el.index_on_parent for el in similar_with_nodes]
            index = first_index_after_cursor(tree, indexes)
            with_node = tree[index]
        else:
            add_conflict(tree, Conflict([self.el], self,
                                        reason="Multiple with nodes found",
                                        insert_before=False))
            return []

        added_els = remove_with(with_node)
        assert added_els[-1] in tree
        set_cursor(tree, with_node[-1])
        return []


class ChangeIndentation:
    def __init__(self, relative_indentation):
        self.relative_indentation = relative_indentation

    def apply(self, tree):
        if isinstance(tree, NodeList):
            if not tree:
                logging.debug('. empty list, skipping')
                return []
            logging.debug('. found list, using first el')
            tree = tree[0]

        logging.debug('. indentation %d delta %d',
                      len(tree.indentation), self.relative_indentation)

        if self.relative_indentation >= 0:
            tree.indentation += self.relative_indentation * " "
        else:
            tree.indentation = tree.indentation[:self.relative_indentation]

        return []

    def __repr__(self):
        return "<%s relative_indentation=\"%s\">" % (self.__class__.__name__,
                                                     self.relative_indentation)


class AddDictItem(BaseAddEls):
    def __init__(self, el, previous_item):
        super().__init__([el], context=[previous_item])

    @property
    def el(self):
        return self.to_add[0]

    @property
    def previous_item(self):
        return self.context[0]

    def apply(self, tree):
        if not isinstance(tree, nodes.DictNode):
            return [Conflict([tree], self,
                             reason="Invalid type %s, expected dict" %
                                                                   type(tree))]

        if find_key(self.el.key, tree):
            logging.debug("key %s already exists",
                          short_display_el(self.el.key))
            return []

        if self.previous_item:
            logging.debug("adding key %s after %s",
                          short_display_el(self.el.key),
                          short_display_el(self.previous_item.key))

            previous_key = find_key(self.previous_item.key, tree)
            if not previous_key:
                index = len(tree.value)
            else:
                index = tree.index(previous_key) + 1
        else:
            logging.debug("adding key %s at the beginning",
                          short_display_el(self.el.key))
            index = 0

        self._insert_el(self.el, index, tree)

        return []


class RemoveDictItem(BaseEl):
    def apply(self, tree):
        logging.debug("removing key %s", short_display_el(self.el))

        if not isinstance(tree, nodes.DictNode):
            return [Conflict([tree], self,
                             reason="Invalid type %s, expected dict" %
                                                                   type(tree))]

        item = find_key(self.el.key, tree)
        if item is not None:
            tree.remove(item)
        return []


class ChangeDictValue(ChangeEl):
    def apply(self, tree):
        logging.debug("changing key %s", short_display_el(self.el.key))

        if not isinstance(tree, nodes.DictNode):
            return [Conflict([tree], self,
                             reason="Invalid type %s, expected dict" %
                                                                   type(tree))]

        item = find_key(self.el.key, tree)
        if not item:
            return []
        return apply_changes(item.value, self.changes)


class ChangeDictItem(ChangeEl):
    def apply(self, tree):
        logging.debug("changing key %s", short_display_el(self.el.key))

        if not isinstance(tree, nodes.DictNode):
            return [Conflict([tree], self,
                             reason="Invalid type %s, expected dict" %
                                                                   type(tree))]

        item = find_key(self.el.key, tree)
        if not item:
            return []
        return apply_changes(item, self.changes)


class ChangeAssociatedSep:
    def __repr__(self):
        return "<%s changes=%r>" % (self.__class__.__name__, self.changes)

    def __init__(self, changes):
        assert changes
        self.changes = tuple(changes)

    def apply(self, tree):
        logging.debug("changing associated sep")

        if isinstance(self.changes[0], Replace):
            changes = list(self.changes)
            tree.associated_sep = changes.pop(0).new_value
        else:
            changes = self.changes

        if not changes:
            return []

        return apply_changes(tree.associated_sep, changes,
                             skip_checks=True)


class ReplaceDictComment(BaseEl):
    def __init__(self, el, new_value):
        super().__init__(el)
        self.new_value = new_value

    def apply(self, tree):
        logging.debug("changing dict comment %s", short_display_el(self.el))

        item = find_key(self.el.key, tree)
        if not item:
            return []

        item.associated_sep = self.new_value
        return []


class RenameClass(BaseEl):
    def apply(self, tree):
        logging.debug("renaming class %s to %s", tree.name, self.el.name)
        tree.name = self.el.name
        return []


class RenameDef(BaseEl):
    def apply(self, tree):
        logging.debug("renaming def %s to %s", tree.name, self.el.name)
        tree.name = self.el.name
        return []


class MoveArg:
    def __init__(self, context):
        self.context = context

    def __repr__(self):
        return "<%s context=%r>" % (self.__class__.__name__,
                                    short_context(self.context))

    def apply(self, tree):
        logging.debug(".. moving %s after %s",
                      short_display_el(tree), self.context[0])
        if tree.previous is None and self.context[0] is None:
            logging.debug("... already at the beginning")
            return []
        if (tree.previous and
                self.context[0] and
                same_arg_guess(self.context[0], tree.previous)):
            logging.debug("... already in place")
            return []

        assert tree in tree.parent

        if self.context[0] is None:
            tree.parent.remove(tree)
            tree.parent.insert(0, tree)
            return []

        for el in tree.parent:
            if same_arg_guess(self.context[0], el):
                tree.parent.remove(tree)
                el.insert_after(tree)
                return []

        assert tree in tree.parent
        return [Conflict([tree], self, reason="Context not found")]


def get_anchors(el):
    return el.__dict__.setdefault("anchored_elements", [])


def anchor(el, to):
    get_anchors(to).append(el)


def move_anchored(el):
    for anchored_el in get_anchors(el):
        anchored_el.move_after(el)
        move_anchored(anchored_el)


def copy_and_transfer_anchors(el):
    new_el = el.copy()
    new_el.new = True
    new_el.anchored_elements = get_anchors(el)
    el.anchored_elements = []
    return new_el


class MoveEl(ElWithContext):
    conflict_if_missing = True

    def apply(self, tree):
        logging.debug(".. moving %s after %s",
                      short_display_el(tree), self.context[0])

        if self.context[0] is None:
            indexes = [0]
        else:
            indexes = find_context_with_reduction(tree.parent, self.context)
        if not indexes:
            msg = "Context not found"
            logging.debug(".. %s", msg.lower())
            if self.conflict_if_missing:
                return [Conflict([tree], self, reason=msg)]
            else:
                return []

        if indexes[0] == tree.index_on_parent:
            return []

        tree.hidden = True
        new_el = copy_and_transfer_anchors(tree)
        tree.parent.insert_with_new_line(indexes[0], new_el)
        move_anchored(new_el)
        if new_el.previous:
            anchor(new_el, to=new_el.previous)
        return []


class MoveImport(MoveEl):
    conflict_if_missing = True


class ChangeHeader:
    def __init__(self, changes):
        self.changes = changes

    def apply(self, tree):
        logging.debug(".. changing header")
        return apply_changes(tree.value.header, self.changes)


class MakeInline:
    def apply(self, tree):
        logging.debug(".. making inline")
        if not tree.value.header:
            logging.debug(".. already inline")
        tree.value.header = []
        tree.value._synchronise()

        if isinstance(tree, nodes.ClassNode):
            tree.sixth_formatting = [" "]
        return []


class MakeMultiline:
    def apply(self, tree):
        logging.debug(".. making multiline")
        if tree.value.header:
            logging.debug(".. already multiline")
        tree.value.header = [nodes.EndlNode(parent=tree)]
        tree.value._synchronise()

        if isinstance(tree, nodes.ClassNode):
            tree.sixth_formatting = []
        return []


class SameEl(BaseEl):
    def apply(self, tree):
        from .differ import look_ahead

        if isinstance(tree, CodeBlockMixin):
            max_ahead = 10 if not isinstance(self.el, nodes.EmptyLineNode) else 1
            el = look_ahead(tree_after_cursor(tree), self.el,
                            max_ahead=max_ahead)
            if el:
                set_cursor(tree, el)

        return []


class ChangeElseNode:
    def __init__(self, changes):
        self.changes = changes

    def apply(self, tree):
        logging.debug(". changing else")

        if not tree.else_:
            logging.debug(".. else has been removed, ignoring changes")
            return []

        return apply_changes(tree.else_, self.changes)


class AddElseNode:
    def __init__(self, new_else):
        self.new_else = new_else

    def apply(self, tree):
        logging.debug(". adding else")

        if tree.else_:
            logging.debug(".. else already added")
            return [Conflict(self.new_else, self,
                             reason="else already added")]

        tree.else_ = self.new_else
        return []


class RemoveElseNode:
    def apply(self, tree):
        logging.debug(". removing else")

        if not tree.else_:
            logging.debug(".. else already removed")

        tree.else_ = None
        return []


class ChangeNumberValue:
    def __init__(self, new_value):
        self.new_value = new_value

    def apply(self, tree):
        tree.value = self.new_value
        return []

    def __repr__(self):
        return "<%s new_value=%r>" % (self.__class__.__name__, self.new_value)


class ChangeExceptsNode:
    def __init__(self, index, changes):
        self.index = index
        self.changes = changes

    def apply(self, tree):
        logging.debug(". changing excepts")
        try:
            except_node = tree.excepts[self.index]
        except IndexError:
            logging.debug(". number of excepts has changed, ignoring changes")
            return []

        return apply_changes(except_node, self.changes)

    def __repr__(self):
        return "<%s index=%r changes=%r>" % (self.__class__.__name__,
                                             self.index, self.changes)


class ChangeString(ChangeEl):
    def __repr__(self):
        return "<%s el=\"%s\" context=%r>" % (
            self.__class__.__name__, short_display_el(self.el),
            short_context(self.context))

    def apply(self, tree):
        dmp = diff_match_patch()
        patches = dmp.patch_fromText(self.changes)
        patched, _ = dmp.patch_apply(patches, tree.value)
        tree.value = patched
        return []


class RemoveSepComment:
    def apply(self, tree):
        sep = tree.associated_sep
        if sep:
            sep.second_formatting = []
        return []

    def __repr__(self):
        return "<%s>" % (self.__class__.__name__)


class AddSepComment(BaseEl):
    @property
    def comments(self):
        return self.el.associated_sep.second_formatting

    def apply(self, tree):
        sep = tree.associated_sep
        if sep:
            sep.second_formatting = self.comments.copy()
        # Add some point add handling for third_formatting for last comment
        return []

    def __repr__(self):
        return "<%s>" % (self.__class__.__name__)


class ChangeSepComment(ChangeEl):
    def __init__(self, changes):
        super().__init__(None, changes)

    @property
    def comments(self):
        return self.el.associated_sep.second_formatting

    def apply(self, tree):
        sep = tree.associated_sep
        if sep:
            return apply_changes(sep.second_formatting, self.changes)
        # Add some point add handling for third_formatting for last comment
        return []

    def __repr__(self):
        return "<%s>" % (self.__class__.__name__)
