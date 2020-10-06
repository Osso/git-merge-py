from redbaron import RedBaron

from gitmergepy.tools import (iter_coma_list,
                              remove_coma_list)


def test_remove_coma_list_to_empty():
    fun = RedBaron("def fun(arg):\n    pass\n")[0]
    args = fun.arguments
    remove_coma_list(args, args[0])
    assert args.dumps() == ""


def test_remove_coma_list_first():
    fun = RedBaron("def fun(arg1, arg2):\n    pass\n")[0]
    args = fun.arguments
    remove_coma_list(args, args[0])
    assert args.dumps() == "arg2"


def test_remove_coma_list_last():
    fun = RedBaron("def fun(arg1, arg2):\n    pass\n")[0]
    args = fun.arguments
    remove_coma_list(args, args[-1])
    assert args.dumps() == "arg1"


def test_iter_coma_list_empty():
    fun = RedBaron("def fun():\n    pass\n")[0]
    args = fun.arguments
    assert list(iter_coma_list(args)) == []


def test_iter_coma_list_one():
    fun = RedBaron("def fun(arg):\n    pass\n")[0]
    args = fun.arguments
    assert list(iter_coma_list(args)) == [args[0]]


def test_iter_coma_list_two():
    fun = RedBaron("def fun(arg1, arg2):\n    pass\n")[0]
    args = fun.arguments
    assert list(iter_coma_list(args)) == [args[0], args[1]]
