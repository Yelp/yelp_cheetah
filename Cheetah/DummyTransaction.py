"""Provides Transactional buffering support for cheetah."""
from __future__ import unicode_literals


class DummyResponse(object):
    def __init__(self):
        self._outputChunks = []

    def write(self, value):
        self._outputChunks.append(value)

    def getvalue(self):
        return ''.join(self._outputChunks)


class DummyTransaction(object):
    '''
        A dummy Transaction class is used by Cheetah in place of real Webware
        transactions when the Template obj is not used directly as a Webware
        servlet.

        It only provides a response object and method.  All other methods and
        attributes make no sense in this context.
    '''
    def __init__(self):
        self._response = None

    def response(self, resp=None):
        if self._response is None:
            self._response = resp or DummyResponse()
        return self._response
