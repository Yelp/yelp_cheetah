from __future__ import unicode_literals

import mock
import pytest

from Cheetah.compile import compile_to_class
from Cheetah.NameMapper import NotFound
from Cheetah.NameMapper import valueFromFrameOrSearchList as VFFSL
from Cheetah.NameMapper import valueFromSearchList as VFSL


def test_VFSL_failure_typeerror():
    class C(object):
        attr = object()

    with pytest.raises(TypeError):
        VFSL(C, 'a')


def test_VFSL_failure():
    with pytest.raises(NotFound):
        VFSL([], 'a')


def test_VFSL_failure_some_items():
    with pytest.raises(NotFound):
        VFSL([{}], 'a')


def test_VFSL_dictionaries():
    obj = {'a': object()}
    # Will autokey for first level in namespace
    assert VFSL([obj], 'a') is obj['a']


def test_VFSL_objects():
    class C(object):
        attr = object()

    assert VFSL([C], 'attr') is C.attr


def test_VFSL_raises_autokey():
    obj = {'a': {'b': object()}}
    with pytest.raises(NotFound):
        VFSL([obj], 'a.b')


def test_VFSL_iterator():
    obj = {'a': object()}
    assert VFSL(iter([obj]), 'a') is obj['a']


def test_VFSL_multiple_namespaces():
    class C(object):
        attr = object()

    class D(object):
        attr = object()

    assert VFSL([C, D], 'attr') is C.attr


def test_VFFSL_locals_first():
    local_var = object()
    global_var = object()
    sl_var = object()
    # Intentionally mask builtin `int`
    locals().update({'int': local_var})
    with mock.patch.dict(globals(), {'int': global_var}):
        assert VFFSL([{'int': sl_var}], 'int') is local_var


def test_VFFSL_globals_next():
    global_var = object()
    sl_var = object()
    with mock.patch.dict(globals(), {'int': global_var}):
        assert VFFSL([{'int': sl_var}], 'int') is global_var


def test_VFFSL_builtins_next():
    sl_var = object()
    assert VFFSL([{'int': sl_var}], 'int') is int


def test_VFFSL_and_finally_searchlist():
    sl_var = object()
    assert VFFSL([{'bar': sl_var}], 'bar') is sl_var


def test_map_builtins_int():
    template_cls = compile_to_class(
        '''
        #def intify(val)
            #return $int(val)
        #end def
        ''',
    )
    assert 5 == template_cls().intify('5')
