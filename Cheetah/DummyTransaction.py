"""Provides Transactional buffering support for cheetah."""

import io


class DummyTransaction(object):
    """The DummyTransaction is used to provide transactional support for
    templates.
    """
    def __init__(self):
        self._response = None

    def response(self, resp=None):
        if self._response is None:
            self._response = resp or io.StringIO()
        return self._response
