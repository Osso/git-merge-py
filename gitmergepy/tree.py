import logging

from redbaron import nodes

from .applyier import (PLACEHOLDER,
                       add_conflict,
                       add_conflicts,
                       apply_changes,
                       insert_at_context,
                       insert_at_context_coma_list)
from .matcher import (find_class,
                      find_context,
                      find_el,
                      find_func,
                      same_el)
from .tools import (FIRST,
                    LAST,
                    append_coma_list,
                    apply_diff_to_list,
                    as_from_contexts,
                    get_call_els,
                    id_from_el,
                    iter_coma_list,
                    make_indented,
                    short_context,
                    short_display_el,
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
            self.__class__.__name__,
            ', '.join(short_display_el(el) for el in self.to_remove),
            short_context(self.context))

    def apply(self, tree):
        if self.context is FIRST:
            logging.debug("    at beginning")
            index = 0
            while isinstance(tree[index], nodes.EndlNode) and not isinstance(self.to_remove[0], nodes.EndlNode):
                index += 1
                if index >= len(tree):
                    break
        elif self.context is LAST:
            index = len(tree) - len(self.to_remove)
            if same_el(tree[-1], PLACEHOLDER):
                index -= 1
        else:
            el = find_context(tree, self.context[-1])
            if el:
                logging.debug("    found context")
                # el.next not working everywhere
                # Workaround:
                index = tree.index(el) + 1
            else:
                logging.debug("    context not found")
                index = tree.index(self.to_remove[0])

        for el_to_remove in self.to_remove:
            logging.debug("removing el %r", short_display_el(el_to_remove))
            if same_el(tree[index], el_to_remove):
                logging.debug("    removing")
                del tree[index]
            else:
                logging.debug("    not matching %r", short_display_el(tree[index]))
                return []

        return []


class AddImports:
    def __init__(self, imports):
        self.imports = imports

    def __repr__(self):
        return "<%s imports=%r>" % (self.__class__.__name__,
                                    ', '.join(short_display_el(el)
                                              for el in self.imports))

    def apply(self, tree):
        existing_imports = set(el.value for el in iter_coma_list(tree.targets))
        make_indented(tree.targets, handle_brackets=True)

        for import_el in self.imports:
            if import_el.value not in existing_imports:
                append_coma_list(tree.targets, import_el)
        sort_imports(tree.targets)
        return []


class RemoveImports:
    def __init__(self, imports):
        self.imports = imports

    def __repr__(self):
        return "<%s imports=%r>" % (self.__class__.__name__, self.imports)

    def apply(self, tree):
        apply_diff_to_list(tree.targets, to_add=[], to_remove=self.imports,
                           key_getter=lambda t: t.value)
        return []


class AddEls:
    def __init__(self, to_add, context):
        self.to_add = to_add
        self.context = context

    def __repr__(self):
        return "<%s to_add=\"%s\" context=%r>" % (
            self.__class__.__name__, ', '.join(short_display_el(el) for el in self.to_add),
            short_context(self.context))

    def add_el(self, el):
        self.to_add.append(el)

    def apply(self, tree):
        if self.context is FIRST:
            logging.debug("    adding els %r at the beginning", self.to_add)
            for el_to_add in reversed(self.to_add):
                tree.insert(0, el_to_add)
        else:
            el = find_context(tree, self.context[-1])
            if el:
                logging.debug("    adding els %r after %r", self.to_add, el)
                for el_to_add in reversed(self.to_add):
                    # Workaround redbaron insert_after bug
                    tree.insert(tree.index(el)+1, el_to_add)
            else:
                tree.extend(self.to_add)
                return [Conflict(self.to_add, self)]
        return []


class ChangeValue:
    def __init__(self, new_value):
        self.new_value = new_value

    def apply(self, tree):
        tree.value = self.new_value
        return []

    def __repr__(self):
        return "<%s new_value=%r>" % (self.__class__.__name__,
                                      short_display_el(self.new_value))


class Replace(ChangeValue):
    def apply(self, tree):
        tree.replace(self.new_value)
        return []


class ChangeTarget(ChangeValue):
    def apply(self, tree):
        tree.target = self.new_value
        return []


class ChangeAttr:
    def __init__(self, attr_name, attr_value):
        self.attr_name = attr_name
        self.attr_value = attr_value

    def apply(self, tree):
        setattr(tree, self.attr_name, self.attr_value)
        return []

    def __repr__(self):
        return "<%s %s=%r>" % (self.__class__.__name__,
                               self.attr_name, self.attr_value)


class RemoveAllDecoratorArgs(BaseEl):
    def apply(self, tree):
        tree.call = None


class AddAllDecoratorArgs(BaseEl):
    def apply(self, tree):
        tree.call = self.el.copy()


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
        el = find_el(tree, self.el, self.context)
        if el:
            conflicts = apply_changes(el, self.changes)
            if self.write_conflicts:
                add_conflicts(el, conflicts)
            else:
                return conflicts
        return []


class ChangeCall(ChangeEl):
    write_conflicts = True


class ChangeDecoratorArgs(ChangeEl):
    def apply(self, tree):
        return apply_changes(tree.call, self.changes)


class ChangeArg(ChangeEl):
    def apply(self, tree):
        return apply_changes(tree.value, self.changes)


class ChangeArgDefault(ChangeEl):
    def get_args(self, tree):
        return tree.arguments

    def apply(self, tree):
        for arg in self.get_args(tree):
            if id_from_el(arg) == id_from_el(self.el):
                return apply_changes(arg, self.changes)
        return []

    def __repr__(self):
        return "<%s el=%r changes=%r>" % (self.__class__.__name__,
                                          short_display_el(self.el),
                                          self.changes)


class ChangeCallArgValue(ChangeArgDefault):
    def get_args(self, tree):
        return tree


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
        el = find_func(tree, self.el)
        if not el and self.old_name:
            tmp_el = self.el.copy()
            tmp_el.name = self.old_name
            el = find_func(tree, tmp_el)

        if el:
            conflicts = apply_changes(el, self.changes)
            add_conflicts(el, conflicts)

        return []


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
            conflicts = apply_changes(el, self.changes)
            add_conflicts(el, conflicts)

        return []


class MoveFunction(ChangeEl):
    def apply(self, tree):
        fun = find_func(tree, self.el)
        # If function still exists, move it then apply changes
        if fun:
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
    def apply(self, tree):
        for decorator in tree.decorators:
            if decorator.name.value == self.el.name.value:
                return apply_changes(decorator, self.changes)
        return []


class AddFunArg:
    def __init__(self, arg, context, new_line):
        self.arg = arg
        self.context = context
        self.new_line = new_line

    def __repr__(self):
        return "<%s arg=%r context=%r>" % (self.__class__.__name__,
                                           short_display_el(self.arg),
                                           short_context(self.context))

    def get_args(self, tree):
        return tree.arguments

    def apply(self, tree):
        args = self.get_args(tree)
        arg = self.arg.copy()
        logging.debug("    adding arg %r to %r",
                      short_display_el(self.arg), short_display_el(args))
        if not insert_at_context_coma_list(arg, self.context, args,
                                           new_line=self.new_line):
            return [self.make_conflict("Argument context has changed")]
        return []

    def make_conflict(self, reason):
        el = self.arg.parent.copy()
        el.decorators.clear()
        el.node_list.clear()
        return Conflict([el], self, reason=reason)


class AddCallArg(AddFunArg):
    def get_args(self, tree):
        return tree

    def make_conflict(self, reason):
        return Conflict([self.arg.parent.parent], self, reason=reason)


class AddDecorator(ElWithContext):
    def apply(self, tree):
        decorator = self.el.copy()
        logging.debug("    adding decorator %r to %r", self.el, tree)
        if not insert_at_context(decorator, self.context, tree.decorators):
            tree.decorators.append(decorator)
        return []


class RemoveFunArgs:
    def __init__(self, args):
        self.args = args

    def __repr__(self):
        return "<%s args=%r>" % (self.__class__.__name__,
                                 [arg.name.value for arg in self.args])

    def get_args(self, tree):
        return tree.arguments

    def apply(self, tree):
        to_remove_values = set(id_from_el(el) for el in self.args)
        args = self.get_args(tree)
        for el in args:
            if id_from_el(el) in to_remove_values:
                if len(args) == 1:
                    args.node_list.remove(el)
                else:
                    args.remove(el)
        return []


class RemoveCallArgs(RemoveFunArgs):
    def get_args(self, tree):
        return tree


class RemoveDecorators(RemoveFunArgs):
    def get_args(self, tree):
        return tree.decorators

    def apply(self, tree):
        to_remove_values = set(el.name.value for el in self.args)
        args = self.get_args(tree)
        for el in args:
            if el.name.value in to_remove_values:
                args.remove(el)
        if not tree.decorators and tree.decorators.node_list:
            tree.decorators.node_list.clear()
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
                        if (self.context is FIRST and previous_el is None) or \
                                self.context and same_el(previous_el, self.context[-1]):
                            context_with_nodes += [el]
            previous_el = el

        if not similar_with_nodes:
            logging.debug('.no nodes found')
            # No with node at all, probably already removed
            return []
        elif len(same_with_nodes) == 1:
            logging.debug('.same node found')
            with_node = same_with_nodes[0]
        elif len(similar_with_nodes) == 1:
            logging.debug('.similar node found')
            with_node = similar_with_nodes[0]
        elif len(context_with_nodes) == 1:
            logging.debug('.similar with context node found')
            with_node = context_with_nodes[0]
        else:
            add_conflict(tree, Conflict([self.el], self,
                                        reason="Multiple with nodes found",
                                        insert_before=False))
            return []

        with_node.decrease_indentation(4)
        for el in reversed(with_node):
            with_node.insert_after(el)
        tree.remove(with_node)
        return []
