import markupsafe


def unicode_filter(val):
    if val is None:
        return ''
    elif isinstance(val, str):
        return val
    elif isinstance(val, bytes):
        return val.decode()
    else:
        return str(val)


def markup_filter(val):
    val = unicode_filter(val)
    return markupsafe.Markup.escape(val)
