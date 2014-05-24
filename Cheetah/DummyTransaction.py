"""Provides Transactional buffering support for cheetah."""

import logging


class DummyResponse(object):
    def __init__(self):
        self._outputChunks = []

    def safeConvert(self, chunk):
        # Exceptionally gross, but the safest way
        # I've found to ensure I get a legit unicode object
        if not chunk:
            return u''
        if isinstance(chunk, unicode):
            return chunk
        try:
            return chunk.decode('utf-8', 'strict')
        except UnicodeDecodeError:
            try:
                return chunk.decode('latin-1', 'strict')
            except UnicodeDecodeError:
                return chunk.decode('ascii', 'ignore')
        except AttributeError:
            return unicode(chunk, errors='ignore')
        return chunk

    def write(self, value):
        self._outputChunks.append(value)

    def getvalue(self, outputChunks=None):
        chunks = outputChunks or self._outputChunks
        try:
            return u''.join(chunks)
        except UnicodeDecodeError:
            logging.debug('Trying to work around a UnicodeDecodeError in getvalue()')
            logging.debug('...perhaps you could fix "%s" while you\'re debugging')
            return ''.join((self.safeConvert(c) for c in chunks))


class DummyTransaction(object):
    '''
        A dummy Transaction class is used by Cheetah in place of real Webware
        transactions when the Template obj is not used directly as a Webware
        servlet.

        It only provides a response object and method.  All other methods and
        attributes make no sense in this context.
    '''
    def __init__(self, *args, **kwargs):
        self._response = None

    def response(self, resp=None):
        if self._response is None:
            self._response = resp or DummyResponse()
        return self._response
