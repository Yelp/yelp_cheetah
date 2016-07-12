from __future__ import unicode_literals

import mock
import pytest

from Cheetah.compile import compile_to_class
from Cheetah.NameMapper import NotFound
from Cheetah.NameMapper import py_value_from_frame_or_namespace
from Cheetah.NameMapper import py_value_from_namespace
from Cheetah.NameMapper import py_value_from_search_list
from Cheetah.NameMapper import value_from_frame_or_namespace
from Cheetah.NameMapper import value_from_namespace
from Cheetah.NameMapper import value_from_search_list


vfns_tests = pytest.mark.parametrize(
    'vfns', (py_value_from_namespace, value_from_namespace),
)
vffns_tests = pytest.mark.parametrize(
    'vffns',
    (py_value_from_frame_or_namespace, value_from_frame_or_namespace),
)
vfsl_tests = pytest.mark.parametrize(
    'vfsl', (py_value_from_search_list, value_from_search_list),
)


@vfsl_tests
def test_VFSL_failure_typeerror(vfsl):
    class C(object):
        attr = object()

    with pytest.raises((AttributeError, NotFound)):
        vfsl('a', C, 'a')


@vfsl_tests
def test_VFSL_failure(vfsl):
    with pytest.raises(NotFound):
        vfsl('a', object(), {})


@vfsl_tests
def test_VFSL_dictionaries(vfsl):
    obj = {'a': object()}
    assert vfsl('a', object(), obj) is obj['a']


@vfsl_tests
def test_VFSL_objects(vfsl):
    class C(object):
        attr = object()

    assert vfsl('attr', C, {}) is C.attr


@vfns_tests
def test_VFNS_failure_typeerror(vfns):
    with pytest.raises((AttributeError, NotFound)):
        vfns('a', 'a')


@vfns_tests
def test_VFNS_failure(vfns):
    with pytest.raises(NotFound):
        vfns('a', {})


@vfns_tests
def test_VFNS_dict(vfns):
    ns = {'a': object()}
    assert vfns('a', ns) is ns['a']


@vffns_tests
def test_VFFNS_locals_first(vffns):
    loc = object()
    glob = object()
    ns_var = object()
    # Intentionally mask builtin `int`
    locals().update({'int': loc})
    with mock.patch.dict(globals(), {'int': glob}):
        assert vffns('int', locals(), globals(), {'int': ns_var}) is loc


@vffns_tests
def test_VFFNS_globals_next(vffns):
    glob = object()
    ns_var = object()
    with mock.patch.dict(globals(), {'int': glob}):
        assert vffns('int', locals(), globals(), {'int': ns_var}) is glob


@vffns_tests
def test_VFFNS_builtins_next(vffns):
    ns_var = object()
    assert vffns('int', locals(), globals(), {'int': ns_var}) is int


@vffns_tests
def test_VFFNS_and_finally_searchlist(vffns):
    ns_var = object()
    assert vffns('bar', locals(), globals(), {'bar': ns_var}) is ns_var


def test_map_builtins_int():
    template_cls = compile_to_class(
        '''
        #def intify(val)
            #return $int(val)
        #end def
        ''',
    )
    assert 5 == template_cls().intify('5')
