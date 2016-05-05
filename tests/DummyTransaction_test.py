from __future__ import absolute_import
from __future__ import unicode_literals

from Cheetah.DummyTransaction import DummyTransaction


def test_importable_for_backwards_compatibility():
    x = DummyTransaction()
    x.write('foo')
    assert x.getvalue() == 'foo'
