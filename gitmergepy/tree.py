import logging

from redbaron import nodes

from .applyier import (apply_changes,
                       insert_at_context)
from .matcher import (find_context,
                      find_el,
                      find_func,
                      find_with_node,
                      same_el)
from .tools import (append_coma_list,
                    apply_diff_to_list,
                    get_call_el,
                    iter_coma_list,
                    short_display_el,
                    sort_imports)


class NoDefault:
    pass


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
            short_display_el(self.context[-1]) if self.context[-1] else None)


class RemoveEl:
    def __init__(self, to_remove, context):
        self.to_remove = to_remove
        self.context = context

    def __repr__(self):
        return "<%s to_remove=\"%s\" context=%r>" % (
            self.__class__.__name__, ', '.join(short_display_el(el) for el in self.to_remove),
            short_display_el(self.context[-1]) if self.context[-1] else None)

    def apply(self, tree):
        for el_to_remove in self.to_remove:
            logging.debug("removing el %r", short_display_el(el_to_remove))
            if not self.context[-1]:
                logging.debug("    at beginning")
                for el in tree:
                    if not isinstance(el_to_remove, nodes.EndlNode) and isinstance(el, nodes.EndlNode):
                        continue
                    logging.debug("    first el in tree %r", short_display_el(el))
                    if same_el(el, el_to_remove):
                        logging.debug("    removing")
                        tree.remove(el)
                    else:
                        logging.debug("    not matching")
                continue

            el = find_context(tree, self.context[-1])
            if el:
                # not working everywhere
                # el_next = el.next
                el_next = tree[tree.index(el)+1]
                if same_el(el_next, el_to_remove):
                    tree.remove(el_next)
                    return

            # Default to brute force
            for el in tree:
                if same_el(el, el_to_remove):
                    tree.remove(el)
                    break


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


class RemoveImports:
    def __init__(self, imports):
        self.imports = imports

    def __repr__(self):
        return "<%s imports=%r>" % (self.__class__.__name__, self.imports)

    def apply(self, tree):
        apply_diff_to_list(tree.targets, to_add=[], to_remove=self.imports,
                           key_getter=lambda t: t.value)


class AddEl:
    def __init__(self, to_add, context):
        self.to_add = to_add
        self.context = context

    def __repr__(self):
        return "<%s to_add=\"%s\" context=%r>" % (
            self.__class__.__name__, ', '.join(short_display_el(el) for el in self.to_add),
            short_display_el(self.context[-1]) if self.context[-1] else None)

    def add_el(self, el):
        self.to_add.append(el)

    def apply(self, tree):
        if self.context and self.context[-1]:
            logging.debug("adding els %r", short_display_el(self.context[-1]))
            el = find_context(tree, self.context[-1])
            if el:
                # not working everywhere
                # el.insert_after(el_to_add)
                for el_to_add in reversed(self.to_add):
                    tree.insert(tree.index(el)+1, el_to_add)
            else:
                tree.extend(self.to_add)
        else:
            for el_to_add in reversed(self.to_add):
                tree.insert(0, el_to_add)


class ChangeValue:
    def __init__(self, new_value):
        self.new_value = new_value

    def apply(self, tree):
        tree.value = self.new_value

    def __repr__(self):
        return "<%s new_value=%r>" % (self.__class__.__name__, self.new_value)


class ChangeAttr:
    def __init__(self, attr_name, attr_value):
        self.attr_name = attr_name
        self.attr_value = attr_value

    def apply(self, tree):
        setattr(tree, self.attr_name, self.attr_value)

    def __repr__(self):
        return "<%s %s=%r>" % (self.__class__.__name__,
                               self.attr_name, self.attr_value)


class ChangeArgDefault(BaseEl):

    def get_args(self, tree):
        return tree.arguments

    def apply(self, tree):
        for arg in self.get_args(tree):
            if arg.name.value == self.el.name.value:
                arg.value.value = self.el.value.value

    def __repr__(self):
        return "<%s new_param_default=%r>" % (self.__class__.__name__,
                                              self.el)


class ChangeCallArgDefault(ChangeArgDefault):
    def get_args(self, tree):
        return get_call_el(tree)


class ChangeEl(BaseEl):
    def __init__(self, el, changes, context=None):
        super().__init__(el)
        self.changes = changes
        self.context = context

    def __repr__(self):
        return "<%s el=\"%s\" changes=%r context=%r>" % (
            self.__class__.__name__, short_display_el(self.el),
            self.changes, short_display_el(self.context))

    def apply(self, tree):
        el = find_el(tree, self.el, self.context)
        if el:
            apply_changes(el, self.changes)


class ChangeFun(ChangeEl):
    def __init__(self, el, changes, context=None, old_name=None):
        super().__init__(el, changes=changes, context=context)
        self.old_name = old_name

    def __repr__(self):
        return "<%s el=\"%s\" changes=%r context=%r old_name=%r>" % (
            self.__class__.__name__, short_display_el(self.el), self.changes,
            short_display_el(self.context), self.old_name)

    def apply(self, tree):
        el = find_func(tree, self.el)
        if not el and self.old_name:
            tmp_el = self.el.copy()
            tmp_el.name = self.old_name
            el = find_func(tree, tmp_el)

        if el:
            apply_changes(el, self.changes)


class MoveFunction(ChangeEl):
    def apply(self, tree):
        fun = find_func(tree, self.el)
        # If function still exists, move it then apply changes
        if fun:
            tree.remove(fun)
            insert_at_context(fun, self.context, tree)
            apply_changes(fun, self.changes)


class ChangeAssignmentNode(ChangeEl):
    def apply(self, tree):
        print(tree.value)
        apply_changes(tree.value, self.changes)


class AddFunArg:
    def __init__(self, arg, context):
        self.arg = arg
        self.context = context

    def __repr__(self):
        return "<%s arg=%r>" % (self.__class__.__name__, self.arg)

    def get_args(self, tree):
        return tree.arguments

    def apply(self, tree):
        args = self.get_args(tree)
        if self.context and self.context[-1]:
            el = find_context(args, self.context[-1])
            if el:
                args.insert(args.index(el)+1, self.arg)
            else:
                args.append(self.arg)
        else:
            args.insert(0, self.arg)


class AddCallArg(AddFunArg):
    def get_args(self, tree):
        return get_call_el(tree)

    def apply(self, tree):
        args = self.get_args(tree)
        if self.context and self.context[-1]:
            el = find_context(args, self.context[-1])
            if el:
                args.insert(args.index(el)+1, self.arg)
            else:
                args.append(self.arg)
        else:
            args.insert(0, self.arg)


class RemoveFunArgs:
    def __init__(self, args):
        self.args = args

    def __repr__(self):
        return "<%s args=%r>" % (self.__class__.__name__,
                                 [arg.name.value for arg in self.args])

    def get_args(self, tree):
        return tree.arguments

    def apply(self, tree):
        apply_diff_to_list(self.get_args(tree), to_add=[], to_remove=self.args,
                           key_getter=lambda t: t.name.value)


class RemoveCallArgs(RemoveFunArgs):
    def get_args(self, tree):
        return get_call_el(tree)


class RemoveWith(BaseEl):
    def apply(self, tree):
        with_node = find_with_node(tree, self.el)
        with_node.decrease_indentation(4)
        for el in reversed(with_node):
            with_node.insert_after(el)
        tree.remove(with_node)
