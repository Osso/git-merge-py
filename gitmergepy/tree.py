from .applyier import (apply_changes,
                       insert_at_context)
from .matcher import (find_context,
                      find_el,
                      find_func,
                      find_with_node,
                      gather_context,
                      same_el)
from .tools import (apply_diff_to_list,
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
            self.context[-1].dumps() if self.context[-1] else None)
        # short_display_el(self.context[-1]))


class RemoveEl(ElWithContext):
    def apply(self, tree):
        if not self.context[-1]:
            if same_el(tree[0], self.el):
                tree.remove(tree[0])
            return

        el = find_context(tree, self.context[-1])
        if el:
            # not working everywhere
            # el_next = el.next
            el_next = tree[tree.index(el)+1]
            if same_el(el_next, self.el):
                tree.remove(el_next)
                return

        # Default to brute force
        for el in tree:
            if same_el(el, self.el):
                tree.remove(el)
                break


class AddImports:
    def __init__(self, imports):
        self.imports = imports

    def __repr__(self):
        return "<%s imports=%r>" % (self.__class__.__name__, self.imports)

    def apply(self, tree):
        apply_diff_to_list(tree.targets, to_add=self.imports, to_remove=[],
                           key_getter=lambda t: t.value)
        sort_imports(tree.targets)


class RemoveImports:
    def __init__(self, imports):
        self.imports = imports

    def __repr__(self):
        return "<%s imports=%r>" % (self.__class__.__name__, self.imports)

    def apply(self, tree):
        apply_diff_to_list(tree.targets, to_add=[], to_remove=self.imports,
                           key_getter=lambda t: t.value)


class AddEl(ElWithContext):
    def apply(self, tree):
        if self.context and self.context[-1]:
            el = find_context(tree, self.context[-1])
            if el:
                # not working everywhere
                # el.insert_after(self.el)
                print(tree)
                tree.insert(tree.index(el)+1, self.el)
                print(tree)
            else:
                tree.append(self.el)
        else:
            tree.insert(0, self.el)


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

    def apply(self, tree):
        for arg in tree.arguments:
            if arg.name.value == self.el.name.value:
                arg.value.value = self.el.value.value

    def __repr__(self):
        return "<%s new_param_default=%r>" % (self.__class__.__name__,
                                              self.el)


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


class AddFunArg:
    def __init__(self, arg, context):
        self.arg = arg
        self.context = context

    def __repr__(self):
        return "<%s arg=%r>" % (self.__class__.__name__, self.arg)

    def apply(self, tree):
        if self.context and self.context[-1]:
            el = find_context(tree.arguments, self.context[-1])
            if el:
                tree.arguments.insert(tree.arguments.index(el)+1, self.arg)
            else:
                tree.arguments.append(self.arg)
        else:
            tree.arguments.insert(0, self.arg)


class RemoveFunArgs:
    def __init__(self, args):
        self.args = args

    def __repr__(self):
        return "<%s args=%r>" % (self.__class__.__name__, self.args)

    def apply(self, tree):
        apply_diff_to_list(tree.arguments, to_add=[], to_remove=self.args,
                           key_getter=lambda t: t.name.value)


class RemoveWith(BaseEl):
    def apply(self, tree):
        with_node = find_with_node(tree, self.el)
        with_node.decrease_indentation(4)
        for el in reversed(with_node):
            with_node.insert_after(el)
        tree.remove(with_node)
