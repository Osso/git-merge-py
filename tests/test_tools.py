from redbaron import node

from gitmergepy.tools import id_from_el


def test_id_from_fun():
    def_node = node("def a():\n   pass")
    assert id_from_el(def_node) == "a"


def test_id_from_class():
    def_node = node("class A:\n   pass")
    assert id_from_el(def_node) == "A"


def test_diff_match_patch():
    from diff_match_patch import diff_match_patch
    dmp = diff_match_patch()
    old = """
bacon
eggs
ham
guido
"""
    new = """
python
eggs
ham
guido
"""
    patches = dmp.patch_make(old, new)
    patched, _ = dmp.patch_apply(patches, old)
    assert patched == new
