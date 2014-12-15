from __future__ import absolute_import
from __future__ import unicode_literals

import functools
import inspect
import sys
import types

from Cheetah.Template import Template


NO_ARGUMENT = object()


class PartialMethodNotCalledFromTemplate(TypeError):
    pass


def _raise_not_called_from_template():
    raise PartialMethodNotCalledFromTemplate(
        "Couldn't find a template. "
        'Please either pass a Template as the first argument ($self), '
        'or call this function from inside a cheetah template.'
    )


def default_self(func):
    """Decorates the given template function.

    If explicit 'self' is passed into the function it is used.
    Otherwise the function looks for self in the previous stack frame.
    """

    @functools.wraps(func)
    def default_self_wrapper(self=NO_ARGUMENT, *args, **kwargs):
        if not isinstance(self, Template):
            if not (
                    self is NO_ARGUMENT or
                    (
                        isinstance(self, type) and
                        issubclass(self, Template) and
                        self.__name__ == func.__name__
                    )
            ):
                args = (self,) + args
            try:
                self = inspect.currentframe().f_back.f_locals['self']
            except KeyError:
                _raise_not_called_from_template()
        try:
            return func(self, *args, **kwargs)

        # There are a lot of exceptions that can occur here
        # due to an instance of self being passed through
        # that is not a template.  These could also change
        # or we could catch exceptions that we don't necessarily
        # want to.  By capturing all of the exceptions and
        # raising our own _only_ in the case we actually care
        # and re-raising in all other cases seems the most sensible
        # way to approach this.
        # Otherwise we'd have to track down every possible exception
        # that could be raised due to the incorrectly typed instance
        # being passed in.
        except Exception:
            if isinstance(self, Template):
                raise
            else:
                _raise_not_called_from_template()
        finally:
            del self

    return default_self_wrapper


class PartialTemplateType(type):
    """Metaclass for partial templates.

    This metaclass wraps each of the methods with a wrapper that uses introspection
    to inspect the previous stack frame determine the calling template object.

    The metaclass appends each function from the class onto the module level, leaving the class's
    functions intact.
    """

    def __new__(mcs, name, bases, attrs):
        # The purpose of any metaclass is to instantiate a class.
        result = cls = super(PartialTemplateType, mcs).__new__(mcs, name, bases, attrs)
        module = sys.modules[attrs['__module__']]
        module.PARTIAL_TEMPLATE_CLASS = cls

        for attrname, value in attrs.items():
            if isinstance(value, types.FunctionType):
                # Wraps the function in a decorator that either takes an explicit self
                # or searches the stack for a self that is a Template instance
                # Then appends the function as a module level function, leaving the class
                # function intact.
                default_self_function = default_self(value)
                setattr(module, attrname, default_self_function)

                assert name != attrname
        return result


# Roughly stolen from six.with_metaclass
YelpCheetahTemplate = type.__new__(
    PartialTemplateType, str('partial_template'), (Template,), {},
)
