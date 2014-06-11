from __future__ import unicode_literals

from Cheetah import five
from Cheetah.compile import compile_to_class
from Cheetah.Template import Template


def test_raises_using_reserved_variable():
    cls = compile_to_class('foo')

    template_var_name = 'getVar'

    assert hasattr(Template, template_var_name)

    try:
        # Should raise, getVar is a member of Template
        cls(searchList=[{template_var_name: 'lol'}])
    except AssertionError as e:
        assert template_var_name in five.text(e)
        return

    raise AssertionError('Should have raised `AssertionError`')


def test_instantiate_with_tuple():
    cls = compile_to_class('$foo $bar')
    ret = cls(searchList=({'foo': 'foo_val', 'bar': 'bar_val'},)).respond()
    assert ret == 'foo_val bar_val'


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
        #def myClassMethod(foo)
            #return '$foo = %s' % $foo
        #end def
    '''
    template = compile_to_class(template)
    rc = template.myClassMethod(foo='bar')
    assert rc == '$foo = bar'


def test_StaticMethodSupport_BasicDecorator():
    template = '''
        #@staticmethod
        #def myStaticMethod(foo)
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
    tmpl_cls = compile_to_class(
        """
        #extends testing.templates.subclass_searchlist
        #implements respond
        When we meet, I say "${greeting}"
        """
    )
    assert tmpl_cls().respond().strip() == 'When we meet, I say "Hola"'
