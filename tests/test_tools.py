from redbaron import node

from gitmergepy.tools import id_from_el


def test_id_from_fun():
    def_node = node("def a():\n   pass")
    assert id_from_el(def_node) == "a"


def test_id_from_class():
    def_node = node("class A:\n   pass")
    assert id_from_el(def_node) == "A"
