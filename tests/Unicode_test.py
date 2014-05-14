# -*- coding: utf-8 -*-

import imp
import io
import os
import os.path
import pytest

from Cheetah.CheetahCompile import compile_template
from Cheetah.Template import Template


@pytest.yield_fixture
def template_compiler(tmpdir):
    class TemplateCompiler(object):
        def __init__(self, path):
            self.path = path
            self.template_number = 0

        def compile(self, src):
            module_name = 'a{0}'.format(self.template_number)
            self.template_number += 1
            tmpl_path = os.path.join(self.path, '{0}.tmpl'.format(module_name))
            py_path = os.path.join(self.path, '{0}.py'.format(module_name))

            with io.open(tmpl_path, 'w') as tmpl_file:
                tmpl_file.write(src)

            compile_template(tmpl_path)
            module = imp.load_source('__tmpl_mod', py_path)
            return getattr(module, module_name)

    yield TemplateCompiler(tmpdir.strpath)


def test_JBQ_UTF8_Test1():
    t = Template.compile(source="""Main file with |$v|

    $other""")

    otherT = Template.compile(source="Other template with |$v|")
    other = otherT()
    t.other = other

    t.v = u'Unicode String'
    t.other.v = u'Unicode String'

    assert unicode(t())


def test_JBQ_UTF8_Test2():
    t = Template.compile(source="""Main file with |$v|

    $other""")

    otherT = Template.compile(source="Other template with |$v|")
    other = otherT()
    t.other = other

    t.v = u'Unicode String with eacute é'
    t.other.v = u'Unicode String'

    assert unicode(t())


def test_JBQ_UTF8_Test3():
    t = Template.compile(source="""Main file with |$v|

    $other""")

    otherT = Template.compile(source="Other template with |$v|")
    other = otherT()
    t.other = other

    t.v = u'Unicode String with eacute é'
    t.other.v = u'Unicode String and an eacute é'

    assert unicode(t())


def test_JBQ_UTF8_Test4():
    t = Template.compile(source="""#encoding utf-8
    Main file with |$v| and eacute in the template é""")

    t.v = 'Unicode String'

    assert unicode(t())


def test_JBQ_UTF8_Test5():
    t = Template.compile(source="""#encoding utf-8
    Main file with |$v| and eacute in the template é""")

    t.v = u'Unicode String'
    assert unicode(t())


def test_JBQ_UTF8_Test6():
    source = """#encoding utf-8
    #set $someUnicodeString = u"Bébé"
    Main file with |$v| and eacute in the template é"""
    t = Template.compile(source=source)

    t.v = u'Unicode String'

    assert unicode(t())


def test_JBQ_UTF8_Test7(template_compiler):
    source = u"""#encoding utf-8
    #set $someUnicodeString = u"Bébé"
    Main file with |$v| and eacute in the template é"""

    template = template_compiler.compile(source)
    template.v = u'Unicode String'

    assert unicode(template())


def test_JBQ_UTF8_Test8_StaticCompile(template_compiler):
    source = u"""#encoding utf-8
#set $someUnicodeString = u"Bébé"
$someUnicodeString"""

    template = template_compiler.compile(source)()

    a = unicode(template).encode("utf-8")
    assert "Bébé" == a


def test_JBQ_UTF8_Test8_DynamicCompile():
    source = """#encoding utf-8
#set $someUnicodeString = u"Bébé"
$someUnicodeString"""

    template = Template(source=source)

    a = unicode(template).encode("utf-8")
    assert "Bébé" == a


def test_EncodeUnicodeCompatTest():
    """Taken initially from Red Hat's bugzilla #529332
    https://bugzilla.redhat.com/show_bug.cgi?id=529332
    """
    t = Template("Foo ${var}", filter='EncodeUnicode')
    t.var = u"Text with some non-ascii characters: åäö"

    rc = t.respond()
    assert isinstance(rc, unicode), ('Template.respond() should return unicode', rc)

    rc = str(t)
    assert isinstance(rc, str), ('Template.__str__() should return a UTF-8 encoded string', rc)


def test_Unicode_in_SearchList_BasicASCII(template_compiler):
    source = u'This is $adjective'

    template = template_compiler.compile(source)
    assert template and issubclass(template, Template)
    template = template(searchList=[{'adjective': u'neat'}])
    assert template.respond()


def test_Unicode_in_SearcList_Thai(template_compiler):
    # The string is something in Thai
    source = u'This is $foo $adjective'
    template = template_compiler.compile(source)
    assert template and issubclass(template, Template)
    template = template(searchList=[{
        'foo': 'bar',
        'adjective': u'\u0e22\u0e34\u0e19\u0e14\u0e35\u0e15\u0e49\u0e2d\u0e19\u0e23\u0e31\u0e1a',
    }])
    assert template.respond()


def test_Unicode_in_SearchList_Thai_utf8(template_compiler):
    utf8 = (
        '\xe0\xb8\xa2\xe0\xb8\xb4\xe0\xb8\x99\xe0\xb8\x94\xe0\xb8\xb5\xe0'
        '\xb8\x95\xe0\xb9\x89\xe0\xb8\xad\xe0\xb8\x99\xe0\xb8\xa3\xe0\xb8'
        '\xb1\xe0\xb8\x9a'
    )

    source = u'This is $adjective'
    template = template_compiler.compile(source)
    assert template and issubclass(template, Template)
    template = template(searchList=[{'adjective': utf8}])
    assert template.respond()


@pytest.yield_fixture
def spanish_template_contents():
    yield '''
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <title>Pagina del vendedor</title>
  </head>
  <body>
    $header
    <h2>Bienvenido $nombre.</h2>
    <br /><br /><br />
    <center>
      Usted tiene $numpedidos_noconf <a href="">pedidós</a> sin confirmar.
      <br /><br />
      Bodega tiene fecha para $numpedidos_bodega <a href="">pedidos</a>.
    </center>
  </body>
</html>
    '''


def test_failure(spanish_template_contents):
    """Test a template lacking a proper #encoding tag"""
    with pytest.raises(UnicodeDecodeError):
        Template(
            spanish_template_contents,
            searchList=[{
                'header': '',
                'nombre': '',
                'numpedidos_bodega': '',
                'numpedidos_noconf': ''
            }],
        )


def test_success(spanish_template_contents):
    """Test a template with a proper #encoding tag"""
    template = '#encoding utf-8\n{0}'.format(spanish_template_contents)
    template = Template(
        template,
        searchList=[{
            'header': '',
            'nombre': '',
            'numpedidos_bodega': '',
            'numpedidos_noconf': '',
        }]
    )
    assert unicode(template)
