from __future__ import absolute_import
from __future__ import unicode_literals

import markupsafe
import six


def unicode_filter(val):
    if val is None:
        return ''
    elif isinstance(val, six.text_type):
        return val
    elif isinstance(val, bytes):
        return val.decode('UTF-8')
    else:
        return six.text_type(val)


def markup_filter(val):
    val = unicode_filter(val)
    return markupsafe.Markup.escape(val)
