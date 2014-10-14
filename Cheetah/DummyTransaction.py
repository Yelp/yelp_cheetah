"""Provides Transactional buffering support for cheetah."""
from __future__ import unicode_literals


class DummyTransaction(object):
    def __init__(self):
        self._chunks = []

    def write(self, value):
        self._chunks.append(value)

    def getvalue(self):
        return ''.join(self._chunks)
