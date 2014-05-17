from __future__ import unicode_literals

from Cheetah.compile import compile_to_class
from Cheetah.Template import Template


def test_TryExceptImportTestFailCase():
    """Test situation where an inline #import statement will get relocated"""
    source = '''
        #def myFunction()
            Ahoy!
            #try
                #import sys
            #except ImportError
                $print "This will never happen!"
            #end try
        #end def
    '''
    # This should raise an IndentationError (if the bug exists)
    compile_to_class(
        source, settings={'useLegacyImportMode': False},
    )


def test_ClassMethodSupport_BasicDecorator():
    template = '''
        #@classmethod
        #def myClassMethod()
            #return '$foo = %s' % $foo
        #end def
    '''
    template = compile_to_class(template)
    rc = template.myClassMethod(foo='bar')
    assert rc == '$foo = bar'


def test_StaticMethodSupport_BasicDecorator():
    template = '''
        #@staticmethod
        #def myStaticMethod()
            #return '$foo = %s' % $foo
        #end def
    '''
    template = compile_to_class(template)
    rc = template.myStaticMethod(foo='bar')
    assert rc == '$foo = bar'


def test_SubclassSearchListTest():
    """Verify that if we subclass Template, we can still use attributes on
    that subclass in the searchList
    """
    class Sub(Template):
        greeting = 'Hola'
    tmpl = Sub('When we meet, I say "${greeting}"')
    assert unicode(tmpl) == 'When we meet, I say "Hola"'
