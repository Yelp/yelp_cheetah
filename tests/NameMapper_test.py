from __future__ import unicode_literals

import mock
import pytest

from Cheetah.compile import compile_to_class
from Cheetah.NameMapper import NotFound
from Cheetah.NameMapper import py_value_from_frame_or_search_list
from Cheetah.NameMapper import py_value_from_search_list
from Cheetah.NameMapper import value_from_frame_or_search_list
from Cheetah.NameMapper import value_from_search_list


vfsl_tests = pytest.mark.parametrize(
    'vfsl', (py_value_from_search_list, value_from_search_list),
)
vffsl_tests = pytest.mark.parametrize(
    'vffsl',
    (py_value_from_frame_or_search_list, value_from_frame_or_search_list),
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


@vffsl_tests
def test_VFFSL_locals_first(vffsl):
    local_var = object()
    global_var = object()
    sl_var = object()
    # Intentionally mask builtin `int`
    locals().update({'int': local_var})
    with mock.patch.dict(globals(), {'int': global_var}):
        assert vffsl(
            'int', locals(), globals(), object(), {'int': sl_var},
        ) is local_var


@vffsl_tests
def test_VFFSL_globals_next(vffsl):
    global_var = object()
    sl_var = object()
    with mock.patch.dict(globals(), {'int': global_var}):
        assert vffsl(
            'int', locals(), globals(), object(), {'int': sl_var},
        ) is global_var


@vffsl_tests
def test_VFFSL_builtins_next(vffsl):
    sl_var = object()
    assert vffsl(
        'int', locals(), globals(), object(), {'int': sl_var},
    ) is int


@vffsl_tests
def test_VFFSL_and_finally_searchlist(vffsl):
    sl_var = object()
    assert vffsl(
        'bar', locals(), globals(), object(), {'bar': sl_var},
    ) is sl_var


def test_map_builtins_int():
    template_cls = compile_to_class(
        '''
        #def intify(val)
            #return $int(val)
        #end def
        ''',
    )
    assert 5 == template_cls().intify('5')
