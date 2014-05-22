'''
    Filters for the #filter directive

    #filter results in output filters Cheetah's $placeholders .
'''


class BaseFilter(object):
    """A baseclass for the Cheetah Filters."""

    def __init__(self, template=None):
        """Setup a reference to the template that is using the filter instance.
        This reference isn't used by any of the standard filters, but is
        available to BaseFilter subclasses, should they need it.

        Subclasses should call this method.
        """
        self.template = template

    def filter(self, val, encoding=None, str=str, **kw):
        '''
            Pass Unicode strings through unmolested, unless an encoding is specified.
        '''
        if val is None:
            return u''
        if isinstance(val, unicode):
            # ignore the encoding and return the unicode object
            return val
        else:
            try:
                return unicode(val)
            except UnicodeDecodeError:
                # we could put more fallbacks here, but we'll just pass the str
                # on and let DummyTransaction worry about it
                return str(val)
