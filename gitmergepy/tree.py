import logging

from redbaron import nodes
from redbaron.base_nodes import NodeList

from .applyier import (add_conflict,
                       add_conflicts,
                       apply_changes,
                       insert_at_context,
                       insert_at_context_coma_list)
from .context import (AfterContext,
                      find_context,
                      gather_after_context)
from .matcher import (find_class,
                      find_el,
                      find_func,
                      find_import,
                      find_key)
from .tools import (apply_diff_to_list,
                    as_from_contexts,
                    get_call_els,
                    id_from_el,
                    same_el,
                    short_context,
                    short_display_el,
                    short_display_list,
                    skip_context_endl,
                    sort_imports)


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

    def apply(self, tree):
        logging.debug("removing els %s", short_display_list(self.to_remove))
        logging.debug(". context %r", short_context(self.context))

        # We modify this
        to_remove = self.to_remove.copy()

        anchor_el = None
        for el_to_remove in to_remove:
            logging.debug(". looking for el %r",
                          short_display_el(el_to_remove))
            anchor_el = find_el(tree, el_to_remove, self.context)
            if anchor_el is not None:
                logging.debug(". el found")
                break
            else:
                logging.debug(". el not found")
                to_remove.remove(el_to_remove)

        if anchor_el is None:
            return []

        index = tree.index(anchor_el)
        for el_to_remove in to_remove:
            try:
                el = tree[index]
            except IndexError:
                # End of tree, we can only assume the other elements
                # are already removed
                break
            logging.debug(". removing el %r", short_display_el(el_to_remove))
            if same_el(el, el_to_remove):
                tree.hide(el)
                index += 1
            else:
                logging.debug(".. not matching %r", short_display_el(el))
                break

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
        existing_imports = set(el.value for el in tree.targets)

        if self.add_brackets:
            tree.targets.add_brackets()

        for import_el in self.imports:
            if import_el.value not in existing_imports:
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
        return "<%s imports=%r>" % (self.__class__.__name__, self.imports)

    def apply(self, tree):
        apply_diff_to_list(tree.targets, to_add=[], to_remove=self.imports,
                           key_getter=lambda t: t.value)
        if len(tree.targets) == 1:
            tree.targets.remove_brackets()

        return []


class BaseAddEls:
    def __init__(self, to_add, context):
        assert context
        self.to_add = to_add
        self.context = context

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
                logging.debug("    at the end")
                index = len(tree)
            else:
                logging.debug("    at the beginning")
                index = skip_context_endl(tree, self.context)
        else:
            logging.debug("    context %r", short_context(self.context))
            index = find_context(tree, self.context)
            if index is None:
                # Try smaller context
                smaller_context = self.context.copy()
                while isinstance(smaller_context[0], nodes.EndlNode):
                    del smaller_context[0]
                logging.debug("    smaller_context %r", short_context(smaller_context))
                index = find_context(tree, smaller_context)
                if index is None:
                    logging.debug("    context not found")
                    return [Conflict(self.to_add, self,
                                     reason="context not found")]
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
            tree.value._data[index-1][1] = None

        el = el_to_add.copy()

        # Add endl for code proxy lists
        endl = isinstance(el_to_add.associated_sep, nodes.EndlNode)
        if el_to_add.associated_sep:
            endl = endl or bool(el_to_add.associated_sep.endl)

        if endl:
            tree.insert_with_new_line(index, el)
        else:
            tree.insert(index, el)

        # Handle comma separated lists and such that don't add a new line
        # by default
        if el_to_add.on_new_line and not el.on_new_line:
            tree.put_on_new_line(el)


class AddEls(BaseAddEls):
    pass


class ReplaceEls(BaseAddEls):
    def __init__(self, to_add, to_remove, context):
        self.to_remove = to_remove
        super().__init__(to_add=to_add, context=context)

    def __repr__(self):
        return "<%s to_add=\"%s\" to_remove=\"%s\" context=%r>" % (
            self.__class__.__name__,
            ', '.join(short_display_el(el) for el in self.to_add),
            ', '.join(short_display_el(el) for el in self.to_remove),
            short_context(self.context))

    def _look_for_context(self, tree):
        index = 0  # to silence pylint

        # First use context
        for index in range(len(tree) + 1):
            if self.context.match(tree, index):
                # match all to_remove items
                for offset, el in enumerate(self.to_remove):
                    try:
                        if not same_el(tree[index+offset], el):
                            break
                    except IndexError:
                        break
                else:
                    return index

        return None

    def apply(self, tree):
        logging.debug("replacing els")
        logging.debug("    context %r", short_context(self.context))

        index = self._look_for_context(tree)
        if index is None:
            return [Conflict([tree], self, reason="Cannot match context")]

        for el_to_add in self.to_add:
            logging.debug("    el %r", short_display_el(el_to_add))
            self._insert_el(el_to_add, index, tree)
            index += 1

        for el_to_add in self.to_remove:
            del tree[index]

        return []


class Replace:
    def __init__(self, new_value, old_value):
        self.new_value = new_value
        self.old_value = old_value

    def apply(self, tree):
        if tree.dumps() != self.new_value.dumps():
            if tree.dumps() != self.old_value.dumps():
                return [Conflict([tree], self,
                                 reason="Different from old value")]
        tree.replace(self.new_value)
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
        return "<%s el=\"%s\" changes=%r context=%r>" % (
            self.__class__.__name__, short_display_el(self.el),
            self.changes, short_context(self.context))

    def apply(self, tree):
        logging.debug("changing %s context %s", short_display_el(self.el),
                      short_context(self.context))

        el = find_el(tree, self.el, self.context)
        if el is None:
            logging.debug(". not found")
        else:
            logging.debug(". found")
            conflicts = apply_changes(el, self.changes)
            if self.write_conflicts:
                add_conflicts(el, conflicts)
            else:
                return conflicts
        return []


class ChangeValue(ChangeEl):
    write_conflicts = False

    def apply(self, tree):
        return apply_changes(tree.value, self.changes)


class ChangeReturn(ChangeEl):
    def apply(self, tree):
        logging.debug(". changing %s", short_display_el(tree))
        # Most of the time we don't need a conflict but it is safer to have one
        if not isinstance(tree.value, type(self.el.value)):
            logging.debug(". skipping types differ")
            return []

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
            if id_from_el(arg) == id_from_el(self.el):
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
    def __init__(self, el, changes, context=None, old_name=None):
        super().__init__(el, changes=changes, context=context)
        self.old_name = old_name

    def __repr__(self):
        return "<%s el=\"%s\" changes=%r context=%r old_name=%r>" % (
            self.__class__.__name__, short_display_el(self.el), self.changes,
            short_context(self.context), self.old_name)

    def apply(self, tree):
        logging.debug("changing fun %r", short_display_el(self.el))
        el = find_func(tree, self.el)
        if not el and self.old_name:
            tmp_el = self.el.copy()
            tmp_el.name = self.old_name
            el = find_func(tree, tmp_el)

        if el:
            logging.debug(". found")
            conflicts = apply_changes(el, self.changes)

            add_conflicts(el, conflicts)

        return []


class ChangeImport(ChangeEl):
    def __init__(self, el, changes, context=None):
        super().__init__(el, changes=changes, context=context)

    def __repr__(self):
        return "<%s el=\"%s\" changes=%r context=%r>" % (
            self.__class__.__name__, short_display_el(self.el), self.changes,
            short_context(self.context))

    def apply(self, tree):
        logging.debug("changing import %r", short_display_el(self.el))
        if self.el:
            el = find_import(tree, self.el)
            if el:
                logging.debug(". found")
                return apply_changes(el, self.changes)

        logging.debug(". not found, adding")
        return AddEls([self.el], context=self.context).apply(tree)


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


class MoveFunction(ChangeEl):
    def apply(self, tree):
        fun = find_func(tree, self.el)
        # If function still exists, move it then apply changes
        if fun:
            logging.debug("moving fun %r", short_display_el(fun))
            tree.remove(fun)
            if not insert_at_context(fun, self.context, tree):
                tree.append(fun)
                add_conflict(tree, Conflict([], self,
                                            reason="Context not found, added at the end"))
                return []
            conflicts = apply_changes(fun, self.changes)
            add_conflicts(tree, conflicts)
        return []


class ChangeAssignmentNode(ChangeEl):
    def apply(self, tree):
        return apply_changes(tree.value, self.changes)


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
        args = self.get_args(tree)
        arg = self.arg.copy()
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
        index = find_context(self.get_elements(tree), context)
        if index is not None:
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
        for el in args:
            if id_from_el(el) in to_remove_values:
                logging.debug(". removing arg %r from %r",
                              short_display_el(el), short_display_el(args))
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
        el_node_as = as_from_contexts(self.el.contexts)

        # Similar
        same_with_nodes = []
        similar_with_nodes = []
        context_with_nodes = []
        previous_el = None
        for el in tree:
            if isinstance(el, nodes.WithNode):
                with_node_as = as_from_contexts(el.contexts)
                if with_node_as == el_node_as:
                    same_with_nodes += [el]
                if with_node_as & el_node_as:
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
        else:
            add_conflict(tree, Conflict([self.el], self,
                                        reason="Multiple with nodes found",
                                        insert_before=False))
            return []

        with_node.decrease_indentation()
        index = with_node.parent.index(with_node) + 1
        for el, sep in with_node.value._data:
            el.parent = with_node.parent
            if sep:
                sep.parent = with_node.parent
        with_node.parent._data[index:index] = with_node.value._data
        with_node.parent._synchronise()
        tree.remove(with_node)
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
        if find_key(self.el.key, tree):
            logging.debug("key %s already exists",
                          short_display_el(self.el.key))
            return []

        if self.previous_item:
            logging.debug("adding key %s after %s",
                          short_display_el(self.el.key),
                          short_display_el(self.previous_item.key))
        else:
            logging.debug("adding key %s at the beginning",
                          short_display_el(self.el.key))

        if self.previous_item:
            previous_key = find_key(self.previous_item.key, tree)
        else:
            previous_key = None

        if not previous_key:
            index = len(tree.value)
        else:
            index = tree.index(previous_key) + 1

        self._insert_el(self.el, index, tree)

        return []


class RemoveDictItem(BaseEl):
    def apply(self, tree):
        logging.debug("removing key %s", short_display_el(self.el))
        item = find_key(self.el.key, tree)
        if item is not None:
            tree.remove(item)
        return []


class ChangeDictItem(BaseEl):
    def __init__(self, key, changes):
        super().__init__(key)
        self.changes = changes

    def __repr__(self):
        return "<%s el=\"%s\" changes=%r>" % (
            self.__class__.__name__, short_display_el(self.el), self.changes)

    def apply(self, tree):
        logging.debug("changing key %s", short_display_el(self.el.key))

        item = find_key(self.el.key, tree)
        if not item:
            return []
        return apply_changes(item.value, self.changes)
