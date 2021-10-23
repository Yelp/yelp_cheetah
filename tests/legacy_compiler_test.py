from Cheetah.legacy_compiler import get_defined_method_names


def test_get_method_names_trivial():
    assert get_defined_method_names('') == set()


def test_get_method_names_a_method():
    assert get_defined_method_names('#def foo(): 1') == {'foo'}
