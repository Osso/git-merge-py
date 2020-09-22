import logging

from redbaron import nodes

from .applyier import (PLACEHOLDER,
                       apply_changes,
                       insert_at_context)
from .matcher import (find_context,
                      find_el,
                      find_func,
                      find_with_node,
                      id_from_el,
                      same_el)
from .tools import (FIRST,
                    LAST,
                    append_coma_list,
                    apply_diff_to_list,
                    get_call_el,
                    iter_coma_list,
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
                return [Conflict(tree, self)]

        for el_to_remove in self.to_remove:
            logging.debug("removing el %r", short_display_el(el_to_remove))
            if same_el(tree[index], el_to_remove):
                logging.debug("    removing")
                del tree[index]
            else:
                print(tree)
                print(index)
                logging.debug("    not matching %r", short_display_el(tree[index]))
                return [Conflict(tree, self)]

        return []


class AddImports:
    def __init__(self, imports):
        self.imports = imports

    def __repr__(self):
        return "<%s imports=%r>" % (self.__class__.__name__, self.imports)

    def apply(self, tree):
        existing_imports = set(el.value for el in iter_coma_list(tree.targets))
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
            for el_to_add in reversed(self.to_add):
                tree.insert(0, el_to_add)
        else:
            logging.debug("adding els %r", short_display_el(self.context[-1]))
            el = find_context(tree, self.context[-1])
            if el:
                # not working everywhere
                # el.insert_after(el_to_add)
                for el_to_add in reversed(self.to_add):
                    tree.insert(tree.index(el)+1, el_to_add)
            else:
                tree.extend(self.to_add)
                return [Conflict(tree, self)]
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
            return apply_changes(el, self.changes)
        return []


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


class Conflict(BaseEl):
    def __init__(self, el, change, reason=''):
        super().__init__(el)
        self.change = change
        self.reason = reason

    def __repr__(self):
        return "<%s el=\"%s\" change=%r reason=%r>" % (
            self.__class__.__name__, short_display_el(self.el),
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
            return apply_changes(el, self.changes)
        return []


class MoveFunction(ChangeEl):
    def apply(self, tree):
        conflicts = []
        fun = find_func(tree, self.el)
        # If function still exists, move it then apply changes
        if fun:
            tree.remove(fun)
            if not insert_at_context(fun, self.context, tree):
                return [Conflict(tree, self)]
            conflicts += apply_changes(fun, self.changes)
        return conflicts


class ChangeAssignmentNode(ChangeEl):
    def apply(self, tree):
        return apply_changes(tree.value, self.changes)


class ChangeAtomtrailersCall(ChangeEl):
    def apply(self, tree):
        el = get_call_el(tree)
        if el is None:
            return [Conflict(tree, self, 'call element not found')]
        return apply_changes(el, self.changes)


class ChangeDecorator(ChangeEl):
    def apply(self, tree):
        for decorator in tree.decorators:
            if decorator.name.value == self.el.name.value:
                return apply_changes(decorator, self.changes)
        return []


class AddFunArg:
    def __init__(self, arg, context):
        self.arg = arg
        self.context = context

    def __repr__(self):
        return "<%s arg=%r context=%r>" % (self.__class__.__name__,
                                           short_display_el(self.arg),
                                           short_context(self.context))

    def get_args(self, tree):
        return tree.arguments

    def apply(self, tree):
        args = self.get_args(tree)
        arg = self.arg.copy()
        logging.debug("    adding arg %r to %r", self.arg, args)
        if self.context is FIRST:
            args.insert(0, arg)
        elif self.context is LAST:
            args.append(arg)
        else:
            el = find_context(args, self.context[-1])
            if el:
                args.insert(args.index(el)+1, arg)
            else:
                return [Conflict(tree, self)]
        return []


class AddCallArg(AddFunArg):
    def get_args(self, tree):
        return tree


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


class AddDecorator(AddFunArg):
    def get_args(self, tree):
        return tree.decorators


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


class RemoveWith(BaseEl):
    def apply(self, tree):
        with_node = find_with_node(tree, self.el)
        if not with_node:
            return [Conflict(tree, self)]
        with_node.decrease_indentation(4)
        for el in reversed(with_node):
            with_node.insert_after(el)
        tree.remove(with_node)
        return []
