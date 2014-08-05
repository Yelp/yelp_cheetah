from __future__ import absolute_import
from __future__ import unicode_literals

import markupsafe

from Cheetah import five


def unicode_filter(val):
    if val is None:
        return ''
    elif isinstance(val, five.text):
        return val
    elif isinstance(val, bytes):
        return val.decode('UTF-8')
    else:
        return five.text(val)


def markup_filter(val):
    val = unicode_filter(val)
    return markupsafe.Markup.escape(val)


filters = {
    'MarkupFilter': markup_filter,
    'UnicodeFilter': unicode_filter,
}
