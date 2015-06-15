from __future__ import unicode_literals

import mock
import pytest

from Cheetah.compile import compile_to_class
from Cheetah.NameMapper import NotFound
from Cheetah.NameMapper import value_from_frame_or_search_list as VFFSL
from Cheetah.NameMapper import value_from_search_list as VFSL


def test_VFSL_failure_typeerror():
    class C(object):
        attr = object()

    with pytest.raises(AttributeError):
        VFSL('a', C, 'a')


def test_VFSL_failure():
    with pytest.raises(NotFound):
        VFSL('a', object(), {})


def test_VFSL_dictionaries():
    obj = {'a': object()}
    assert VFSL('a', object(), obj) is obj['a']


def test_VFSL_objects():
    class C(object):
        attr = object()

    assert VFSL('attr', C, {}) is C.attr


def test_VFFSL_locals_first():
    local_var = object()
    global_var = object()
    sl_var = object()
    # Intentionally mask builtin `int`
    locals().update({'int': local_var})
    with mock.patch.dict(globals(), {'int': global_var}):
        assert VFFSL(
            'int', locals(), globals(), object(), {'int': sl_var},
        ) is local_var


def test_VFFSL_globals_next():
    global_var = object()
    sl_var = object()
    with mock.patch.dict(globals(), {'int': global_var}):
        assert VFFSL(
            'int', locals(), globals(), object(), {'int': sl_var},
        ) is global_var


def test_VFFSL_builtins_next():
    sl_var = object()
    assert VFFSL(
        'int', locals(), globals(), object(), {'int': sl_var},
    ) is int


def test_VFFSL_and_finally_searchlist():
    sl_var = object()
    assert VFFSL(
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
