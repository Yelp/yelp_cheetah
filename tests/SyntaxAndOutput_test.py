# -*- coding: UTF-8 -*-
# pylint:disable=no-self-use,too-many-public-methods
from __future__ import absolute_import
from __future__ import unicode_literals

import unittest
import warnings

import markupsafe
import pytest

from Cheetah import filters
from Cheetah.compile import compile_to_class
from Cheetah.legacy_parser import ParseError


def dummydecorator(func):
    return func


class DummyClass(object):
    callArg = None

    def meth(self, arg="arff"):
        return str(arg)

    def meth1(self, arg="doo"):
        return arg

    def methWithPercentSignDefaultArg(self, arg1="110%"):
        return str(arg1)


def dummyFunc(arg="Scooby"):
    return arg

defaultTestNamespace = {
    'aStr': 'blarg',
    'anInt': 1,
    'aFloat': 1.5,
    'aList': [str('item0'), str('item1'), str('item2')],
    'aDict': {
        'one': 'item1',
        'two': 'item2',
        'nestedDict': {
            1: 'nestedItem1',
            'two': 'nestedItem2'
        },
        'nestedFunc': dummyFunc,
    },
    'aFunc': dummyFunc,
    'anObj': DummyClass(),
    'aMeth': DummyClass().meth1,
    'none': None,
    'emptyString': '',
    'numOne': 1,
    'numTwo': 2,
    'zero': 0,
    'listOfLambdas': [lambda x: x, lambda x: x, lambda x: x],
    'letterList': ['a', 'b', 'c'],
    '_': lambda x: 'Translated: ' + x,
    'unicodeData': 'aoeu12345\u1234',
}


class OutputTest(unittest.TestCase):
    report = '''
Template output mismatch:

    Input Template =
%(template)s%(end)s

    Expected Output =
%(expected)s%(end)s

    Actual Output =
%(actual)s%(end)s'''

    def verify(self, input_str, expectedOutput):
        templateClass = compile_to_class(input_str)
        templateObj = templateClass(defaultTestNamespace)

        output = templateObj.respond()
        if output != expectedOutput:
            raise AssertionError(self.report % {
                'template': input_str.replace('\n', '*eol*'),
                'expected': expectedOutput.replace('\n', '*eol*'),
                'actual': output.replace('\n', '*eol*'),
                'end': '(end)',
            })


class EmptyTemplate(OutputTest):
    def test1(self):
        """an empty string for the template"""

        filters_copy = warnings.filters[:]
        warnings.filterwarnings('error',
                                'You supplied an empty string for the source!',
                                UserWarning)
        with pytest.raises(UserWarning):
            self.verify("", "")

        with pytest.raises(NotImplementedError):
            self.verify("#implements foo", "")

        self.verify("#implements respond", "")

        # Restore the old filters.
        warnings.filters[:] = filters_copy


class Backslashes(OutputTest):
    def test1(self):
        """ a single \\ using rawstrings"""
        self.verify(r"\ ",
                    r"\ ")

    def test2(self):
        """ a single \\ using rawstrings and lots of lines"""
        self.verify(r"\ " + "\n\n\n\n\n\n\n\n\n",
                    r"\ " + "\n\n\n\n\n\n\n\n\n")

    def test3(self):
        """ a single \\ without using rawstrings"""
        self.verify(r"\ \ ",
                    r"\ \ ")

    def test4(self):
        """ single line from an apache conf file"""
        self.verify(r'\#LogFormat "%h %l %u %t \"%r\" %>s %b"',
                    r'#LogFormat "%h %l %u %t \"%r\" %>s %b"')

    def test5(self):
        """ single line from an apache conf file with many NEWLINES

        The NEWLINES are used to make sure that MethodCompiler.commitStrConst()
        is handling long and short strings in the same fashion.  It uses
        triple-quotes for strings with lots of \\n in them and repr(theStr) for
        shorter strings with only a few newlines."""

        self.verify(r'\#LogFormat "%h %l %u %t \"%r\" %>s %b"' + '\n\n\n\n\n\n\n',
                    r'#LogFormat "%h %l %u %t \"%r\" %>s %b"' + '\n\n\n\n\n\n\n')

    def test7(self):
        """ a single \\ without using rawstrings plus many NEWLINES"""
        self.verify(r"\ \ " + "\n\n\n\n\n\n\n\n\n",
                    r"\ \ " + "\n\n\n\n\n\n\n\n\n")

    def test8(self):
        """ single line from an apache conf file with single quotes and many NEWLINES
        """

        self.verify(r"""\#LogFormat '%h %l %u %t \"%r\" %>s %b'""" + '\n\n\n\n\n\n\n',
                    r"""#LogFormat '%h %l %u %t \"%r\" %>s %b'""" + '\n\n\n\n\n\n\n')


class NonTokens(OutputTest):
    def test1(self):
        """dollar signs not in Cheetah $vars"""
        self.verify("$ $$ $5 $. $ test",
                    "$ $$ $5 $. $ test")

    def test2(self):
        """hash not in #directives"""
        self.verify(r"# \# #5 ",
                    "# # #5 ")

    def test3(self):
        """escapted comments"""
        self.verify(r"  \#\#escaped comment  ",
                    "  ##escaped comment  ")

    def test5(self):
        """1 dollar sign"""
        self.verify("$",
                    "$")

    def test6(self):
        """1 dollar sign followed by hash"""
        self.verify("\n$#\n",
                    "\n$#\n")


class Comments_SingleLine(OutputTest):
    def test1(self):
        """## followed by WS"""
        self.verify("##    ",
                    "")

    def test2(self):
        """## followed by NEWLINE"""
        self.verify("##\n",
                    "")

    def test3(self):
        """## followed by text then NEWLINE"""
        self.verify("## oeuao aoe uaoe \n",
                    "")

    def test4(self):
        """## gobbles leading WS"""
        self.verify("    ## oeuao aoe uaoe \n",
                    "")

    def test5(self):
        """## followed by text then NEWLINE, + leading WS"""
        self.verify("    ## oeuao aoe uaoe \n",
                    "")

    def test6(self):
        """## followed by EOF"""
        self.verify("##",
                    "")

    def test7(self):
        """## followed by EOF with leading WS"""
        self.verify("    ##",
                    "")

    def test8(self):
        """## gobble line
        with text on previous and following lines"""
        self.verify("line1\n   ## aoeu 1234   \nline2",
                    "line1\nline2")

    def test9(self):
        """## don't gobble line
        with text on previous and following lines"""
        self.verify("line1\n 12 ## aoeu 1234   \nline2",
                    "line1\n 12 \nline2")

    def test10(self):
        """## containing $placeholders
        """
        self.verify("##$a$b $c($d)",
                    "")

    def test11(self):
        """## containing #for directive"""
        self.verify("##for i in range(15)",
                    "")


class Placeholders(OutputTest):
    def test1(self):
        """1 placeholder"""
        self.verify("$aStr", "blarg")

    def test2(self):
        """2 placeholders"""
        self.verify("$aStr $anInt", "blarg 1")

    def test3(self):
        """2 placeholders, back-to-back"""
        self.verify("$aStr$anInt", "blarg1")

    def test4(self):
        """1 placeholder enclosed in ()"""
        self.verify("$(aStr)", "blarg")

    def test5(self):
        """1 placeholder enclosed in {}"""
        self.verify("${aStr}", "blarg")

    def test6(self):
        """1 placeholder enclosed in []"""
        self.verify("$[aStr]", "blarg")

    def test7(self):
        """1 placeholder enclosed in () + WS

        Test to make sure that $(<WS><identifier>.. matches
        """
        self.verify("$( aStr   )", "blarg")

    def test8(self):
        """1 placeholder enclosed in {} + WS"""
        self.verify("${ aStr   }", "blarg")

    def test9(self):
        """1 placeholder enclosed in [] + WS"""
        self.verify("$[ aStr   ]", "blarg")

    def test19(self):
        """1 placeholder surrounded by single quotes and multiple newlines"""
        self.verify("""'\n\n\n\n'$aStr'\n\n\n\n'""",
                    """'\n\n\n\n'blarg'\n\n\n\n'""")


class Placeholders_Vals(OutputTest):
    def test1(self):
        """string"""
        self.verify("$aStr", "blarg")

    def test2(self):
        """string - with whitespace"""
        self.verify(" $aStr ", " blarg ")

    def test3(self):
        """empty string - with whitespace"""
        self.verify("$emptyString", "")

    def test4(self):
        """int"""
        self.verify("$anInt", "1")

    def test5(self):
        """float"""
        self.verify("$aFloat", "1.5")

    def test6(self):
        """list"""
        self.verify(
            "$aList",
            markupsafe.Markup.escape("['item0', 'item1', 'item2']")
        )

    def test7(self):
        """None

        The default output filter is ReplaceNone.
        """
        self.verify("$none", "")

    def test8(self):
        """True, False"""
        self.verify("$True $False", "%s %s" % (repr(True), repr(False)))

    def test9(self):
        """$_"""
        self.verify("$_('foo')", "Translated: foo")


class UnicodeStrings(OutputTest):
    def test1(self):
        """unicode data in placeholder"""
        self.verify(u"$unicodeData", defaultTestNamespace['unicodeData'])

    def test2(self):
        """unicode data in body"""
        self.verify(u"aoeu12345\u1234", u"aoeu12345\u1234")


class Placeholders_Esc(OutputTest):
    def test1(self):
        """1 escaped placeholder"""
        self.verify(r"\$var",
                    "$var")

    def test2(self):
        """2 escaped placeholders"""
        self.verify(r"\$var \$_",
                    "$var $_")

    def test3(self):
        """2 escaped placeholders - back to back"""
        self.verify(r"\$var\$_",
                    "$var$_")

    def test4(self):
        """2 escaped placeholders - nested"""
        self.verify(r"\$var(\$_)",
                    "$var($_)")

    def test5(self):
        """2 escaped placeholders - nested and enclosed"""
        self.verify(r"\$(var(\$_)",
                    "$(var($_)")


class Placeholders_Calls(OutputTest):
    def test2(self):
        """func placeholder - with ()"""
        self.verify("$aFunc()",
                    "Scooby")

    def test3(self):
        r"""func placeholder - with (\n\n)"""
        self.verify("$aFunc(\n\n)",
                    "Scooby")

    def test4(self):
        r"""func placeholder - with (\n\n) and $() enclosure"""
        self.verify("$(aFunc(\n\n))",
                    "Scooby")

    def test5(self):
        r"""func placeholder - with (\n\n) and ${} enclosure"""
        self.verify("${aFunc(\n\n)}",
                    "Scooby")

    def test6(self):
        """func placeholder - with (int)"""
        self.verify("$aFunc(1234)",
                    "1234")

    def test7(self):
        r"""func placeholder - with (\nint\n)"""
        self.verify("$aFunc(\n1234\n)",
                    "1234")

    def test8(self):
        """func placeholder - with (string)"""
        self.verify("$aFunc('aoeu')",
                    "aoeu")

    def test9(self):
        """func placeholder - with ('''string''')"""
        self.verify("$aFunc('''aoeu''')",
                    "aoeu")

    def test10(self):
        r"""func placeholder - with ('''\nstring\n''')"""
        self.verify("$aFunc('''\naoeu\n''')",
                    "\naoeu\n")

    def test11(self):
        r"""func placeholder - with ('''\nstring'\n''')"""
        self.verify("$aFunc('''\naoeu'\n''')",
                    markupsafe.Markup.escape("\naoeu'\n"))

    def test12(self):
        r'''func placeholder - with ("""\nstring\n""")'''
        self.verify('$aFunc("""\naoeu\n""")',
                    "\naoeu\n")

    def test13(self):
        """func placeholder - with (string * int)"""
        self.verify("$aFunc('aoeu' * 2)",
                    "aoeuaoeu")

    def test14(self):
        """func placeholder - with (int * int)"""
        self.verify("$aFunc(2 * 2)",
                    "4")

    def test15(self):
        """func placeholder - with (int * float)"""
        self.verify("$aFunc(2 * 2.0)",
                    "4.0")

    def test16(self):
        r"""func placeholder - with (int\n*\nfloat)"""
        self.verify("$aFunc(2\n*\n2.0)",
                    "4.0")

    def test18(self):
        """func placeholder - with (arg=float)"""
        self.verify("$aFunc(arg=4.0)",
                    "4.0")

    def test26(self):
        """a function call with the Python None kw."""
        self.verify("$aFunc(None)",
                    "")


def test_placeholder_addition():
    # To restore coverage
    cls = compile_to_class(
        '#py x = 1\n'
        '#py y = 2\n'
        '${x + y}'
    )
    assert cls().respond() == '3'


class NameMapper(OutputTest):
    def test1(self):
        """calling"""
        self.verify("$aFunc()! $aFunc().",
                    "Scooby! Scooby.")

    def test2(self):
        """nested calling"""
        self.verify("$aFunc($aFunc()).",
                    "Scooby.")

    def test3(self):
        """list subscription"""
        self.verify("$aList[0]",
                    "item0")

    def test4(self):
        """list slicing"""
        self.verify(
            "$aList[:2]",
            markupsafe.Markup.escape("['item0', 'item1']")
        )

    def test5(self):
        """list slicing and subcription combined"""
        self.verify("$aList[:2][0]",
                    "item0")

    def test7(self):
        """dictionary access - Python style"""
        self.verify("$aDict['one']",
                    "item1")

    def test9(self):
        """dictionary access combined with string method"""
        self.verify("$aDict['one'].upper()",
                    "ITEM1")

    def test11(self):
        """nested dictionary access - Python style"""
        self.verify("$aDict['nestedDict']['two']",
                    "nestedItem2")

    def test13(self):
        """nested dictionary access using method"""
        self.verify("$aDict.get('nestedDict')['two']", "nestedItem2")

    def test14(self):
        self.verify("$aDict['nestedDict']['two'].upper()",
                    "NESTEDITEM2")

    def test16(self):
        self.verify("${aDict['nestedDict']['two'].upper()[:4]}",
                    "NEST")

    def test17(self):
        """nested dictionary access - Python style using a soft-coded key"""
        self.verify("$aDict[$anObj.meth('nestedDict')]['two']",
                    "nestedItem2")

    def test18(self):
        """object method access"""
        self.verify("$anObj.meth1()",
                    "doo")

    def test19(self):
        """object method access, followed by complex slice"""
        self.verify("${anObj.meth1()[0: ((4//4*2)*2)//$anObj.meth1(2) ]}",
                    "do")

    def test20(self):
        """object method access, followed by a very complex slice
        If it can pass this one, it's safe to say it works!!"""
        self.verify("$( anObj.meth1()[0:\n (\n(4//4*2)*2)//$anObj.meth1(2)\n ] )",
                    "do")

    def test21(self):
        """object method access with % in the default arg for the meth.

        This tests a bug that Jeff Johnson found and submitted a patch to SF
        for."""

        self.verify("$anObj.methWithPercentSignDefaultArg()",
                    "110%")

    def test22a(self):
        with pytest.raises(AttributeError):
            self.verify('$aDict.nestedDict.two', '')

    def test22b(self):
        self.verify("$aDict['nestedDict']['two']", "nestedItem2")


def test_one_line_compiler_settings():
    cls = compile_to_class(
        '#compiler-settings# useLegacyImportMode = False #end compiler-settings#foo\n'
        '#try\n'
        '#import foo\n'
        '#except ImportError\n'
        'importerror\n'
        '#end try\n'
    )
    assert cls().respond() == 'foo\nimporterror\n'


class CallDirective(OutputTest):
    def test1(self):
        r"""simple #call """
        self.verify("#call int:\n$anInt#end call",
                    "1")
        # single line version
        self.verify("#call int: $anInt",
                    "1")
        self.verify("#call int: 10\n$aStr",
                    "10\nblarg")

    def test2(self):
        r"""simple #call + WS"""
        self.verify("#call int\n$anInt  #end call",
                    "1")

    def test3(self):
        r"""a longer #call"""
        self.verify('''\
#def meth(arg)
$arg.upper()#slurp
#end def
#call $meth
$(1234 + 1) foo#slurp
#end call''',
                    "1235 FOO")

    def test6(self):
        """#call with python kwargs and cheetah output for the 1s positional
        arg"""

        self.verify('''\
#def meth(arg1, arg2)
$arg1.upper() - $arg2.lower()#slurp
#end def
#call self.meth arg2="UPPER"
$(1234 + 1) foo#slurp
#end call''',
                    "1235 FOO - upper")

    def test9(self):
        """nested #call directives"""
        self.verify('''\
#def meth(arg1)
$arg1#slurp
#end def
#def meth2(x,y)
$x$y#slurp
#end def
##
#call self.meth
1#slurp
#call self.meth
2#slurp
#call self.meth
3#slurp
#end call 3
#py two = 2
#call self.meth2 y=int(10/two)
4#slurp
#end call 4
#end call 2
#end call 1''',
                    "12345")


class SlurpDirective(OutputTest):
    def test1(self):
        r"""#slurp with 1 \n """
        self.verify("#slurp\n",
                    "")

    def test2(self):
        r"""#slurp with 1 \n, leading whitespace
        Should gobble"""
        self.verify("       #slurp\n",
                    "")

    def test3(self):
        r"""#slurp with 1 \n, leading content
        Shouldn't gobble"""
        self.verify(" 1234 #slurp\n",
                    " 1234 ")

    def test4(self):
        r"""#slurp with WS then \n, leading content
        Shouldn't gobble"""
        self.verify(" 1234 #slurp    \n",
                    " 1234 ")

    def test5(self):
        r"""#slurp with garbage chars then \n, leading content
        Should eat the garbage"""
        self.verify(" 1234 #slurp garbage   \n",
                    " 1234 ")


class ReturnDirective(OutputTest):

    def test1(self):
        """#return'ing an int """
        self.verify("""1
$str($test()-6)
3
#def test()
#if 1
#return (3   *2)  \
  + 2
#else
aoeuoaeu
#end if
#end def
""",
                    "1\n2\n3\n")

    def test2(self):
        """#return'ing an string """
        self.verify("""1
$str($test()[1])
3
#def test()
#if 1
#return '123'
#else
aoeuoaeu
#end if
#end def
""",
                    "1\n2\n3\n")

    def test3(self):
        """#return'ing an string AND streaming other output via the transaction"""
        self.verify("""1
$str($test()[1])
3
#def test()
1.5
#if 1
#return '123'
#else
aoeuoaeu
#end if
#end def
""",
                    "1\n1.5\n2\n3\n")


class YieldDirective(OutputTest):
    def test1(self):
        """simple #yield """

        src1 = """#for i in range(10)\n#yield i\n#end for"""
        src2 = (
            "#def iterator()\n"
            "#for i in range(10)\n#yield i\n#end for\n"
            "#end def\n"
            "#for i in $iterator()\n$i#end for"
        )

        for src in (src1, src2):
            klass = compile_to_class(src)
            iterator = klass().respond()
            output = [str(i) for i in iterator]
            assert ''.join(output) == '0123456789'


class ForDirective(OutputTest):
    def test1(self):
        """#for loop with one local var"""
        self.verify("#for i in range(5)\n$i\n#end for",
                    "0\n1\n2\n3\n4\n")

        self.verify("#for i in range(5):\n$i\n#end for",
                    "0\n1\n2\n3\n4\n")

        self.verify("#for i in range(5): ##comment\n$i\n#end for",
                    "0\n1\n2\n3\n4\n")

        self.verify("#for i in range(5) ##comment\n$i\n#end for",
                    "0\n1\n2\n3\n4\n")

    def test2(self):
        """#for loop with WS in loop"""
        self.verify("#for i in range(5)\n$i \n#end for",
                    "0 \n1 \n2 \n3 \n4 \n")

    def test3(self):
        """#for loop gobble WS"""
        self.verify("   #for i in range(5)   \n$i \n   #end for   ",
                    "0 \n1 \n2 \n3 \n4 \n")

    def test4(self):
        """#for loop over list"""
        self.verify("#for i, j in [(0,1),(2,3)]\n$i,$j\n#end for",
                    "0,1\n2,3\n")

    def test5(self):
        """#for loop over list, with #slurp"""
        self.verify("#for i, j in [(0,1),(2,3)]\n$i,$j#slurp\n#end for",
                    "0,12,3")

    def test6(self):
        """#for loop with explicit closures"""
        self.verify("#for i in range(5)#$i#end for#",
                    "01234")

    def test7(self):
        """#for loop with explicit closures and WS"""
        self.verify("  #for i in range(5)#$i#end for#  ",
                    "  01234  ")

    def test8(self):
        """#for loop using another $var"""
        self.verify("  #for i in range($aFunc(5))#$i#end for#  ",
                    "  01234  ")

    def test9(self):
        """test methods in for loops"""
        self.verify("#for func in $listOfLambdas\n$func($anInt)\n#end for",
                    "1\n1\n1\n")

    def test10(self):
        """#for loop over list, using methods of the items"""
        self.verify("#for i, j in [('aa','bb'),('cc','dd')]\n$i.upper(),$j.upper()\n#end for",
                    "AA,BB\nCC,DD\n")
        self.verify("#for i, j in [('aa','bb'),('cc','dd')]\n$i.upper(),$j.upper()\n#end for",
                    "AA,BB\nCC,DD\n")

    def test11(self):
        """#for loop over list, using (i, j) style target list"""
        self.verify("#for (i, j) in [('aa','bb'),('cc','dd')]\n$i.upper(),$j.upper()\n#end for",
                    "AA,BB\nCC,DD\n")

    def test12(self):
        """#for loop over list, using i, (j,k) style target list"""
        self.verify("#for i, (j, k) in enumerate([('aa','bb'),('cc','dd')])\n$j.upper(),$k.upper()\n#end for",
                    "AA,BB\nCC,DD\n")

    def test13(self):
        """single line #for"""
        self.verify("#for i in range($aFunc(5)): $i",
                    "01234")

    def test14(self):
        """single line #for with 1 extra leading space"""
        self.verify("#for i in range($aFunc(5)):  $i",
                    " 0 1 2 3 4")

    def test15(self):
        """2 times single line #for"""
        self.verify("#for i in range($aFunc(5)): $i#slurp\n" * 2,
                    "01234" * 2)

    def test16(self):
        """false single line #for """
        self.verify("#for i in range(5): \n$i\n#end for",
                    "0\n1\n2\n3\n4\n")


class AttrDirective(OutputTest):

    def test1(self):
        """#attr with int"""
        self.verify("#attr test = 1234\n$test",
                    "1234")

    def test2(self):
        """#attr with string"""
        self.verify("#attr test = 'blarg'\n$test",
                    "blarg")

    def test3(self):
        """#attr with expression"""
        self.verify("#attr test = 'blarg'.upper()*2\n$test",
                    "BLARGBLARG")

    def test4(self):
        """#attr with string + WS
        Should gobble"""
        self.verify("     #attr test = 'blarg'   \n$test",
                    "blarg")

    def test5(self):
        """#attr with string + WS + leading text
        Shouldn't gobble"""
        self.verify("  --   #attr test = 'blarg'   \n$test",
                    "  --   \nblarg")

    def test_attr_with_unicode(self):
        self.verify(
            "#attr test = u'☃'\n"
            '$test\n',
            '☃\n'
        )


class DefDirective(OutputTest):

    def test1(self):
        self.verify("#def testMeth()\n1234\n#end def\n$testMeth()",
                    "1234\n")

        self.verify("#def testMeth() ## comment\n1234\n#end def\n$testMeth()",
                    "1234\n")

        self.verify("#def testMeth(): ## comment\n1234\n#end def\n$testMeth()",
                    "1234\n")

    def test2(self):
        """#def, gobble WS"""
        self.verify("   #def testMeth()  \n1234\n    #end def   \n$testMeth()",
                    "1234\n")

    def test3(self):
        """#def with argstring, gobble WS"""
        self.verify("  #def testMeth(a=999)   \n1234-$a\n  #end def\n$testMeth()",
                    "1234-999\n")

    def test4(self):
        """#def with argstring, gobble WS, string used in call"""
        self.verify("  #def testMeth(a=999)   \n1234-$a\n  #end def\n$testMeth('ABC')",
                    "1234-ABC\n")

    def test5(self):
        """#def with argstring, gobble WS, list used in call"""
        self.verify("  #def testMeth(a=999)   \n1234-$a\n  #end def\n$testMeth([1,2,3])",
                    "1234-[1, 2, 3]\n")

    def test6(self):
        """#def with 2 args, gobble WS, list used in call"""
        self.verify("  #def testMeth(a, b='default')   \n1234-$a$b\n  #end def\n$testMeth([1,2,3])",
                    "1234-[1, 2, 3]default\n")

    def test7(self):
        """#def with *args, gobble WS"""
        self.verify("  #def testMeth(*args)   \n1234-$args\n  #end def\n$testMeth()",
                    "1234-()\n")

    def test8(self):
        """#def with **KWs, gobble WS"""
        self.verify("  #def testMeth(**KWs)   \n1234-$KWs\n  #end def\n$testMeth()",
                    "1234-{}\n")

    def test9(self):
        """#def with *args + **KWs, gobble WS"""
        self.verify("  #def testMeth(*args, **KWs)   \n1234-$args-$KWs\n  #end def\n$testMeth()",
                    "1234-()-{}\n")

    def test10(self):
        """#def with *args + **KWs, gobble WS"""
        self.verify(
            "  #def testMeth(*args, **KWs)   \n1234-$args-$KWs['a']\n  #end def\n$testMeth(1,2, a=1)",
            "1234-(1, 2)-1\n")

    def test11(self):
        """single line #def with extra WS"""
        self.verify(
            "#def testMeth(): aoeuaoeu\n- $testMeth() -",
            "- aoeuaoeu -")

    def test12(self):
        """single line #def with extra WS and nested $placeholders"""
        self.verify(
            "#def testMeth(): $anInt $aFunc(1234)\n- $testMeth() -",
            "- 1 1234 -")

    def test13(self):
        """single line #def escaped $placeholders"""
        self.verify(
            "#def testMeth(): \\$aFunc(\\$anInt)\n- $testMeth() -",
            "- $aFunc($anInt) -")

    def test14(self):
        """single line #def 1 escaped $placeholders"""
        self.verify(
            "#def testMeth(): \\$aFunc($anInt)\n- $testMeth() -",
            "- $aFunc(1) -")

    def test15(self):
        """single line #def 1 escaped $placeholders + more WS"""
        self.verify(
            "#def testMeth    (): \\$aFunc($anInt)\n- $testMeth() -",
            "- $aFunc(1) -")

    def test19(self):
        """#def that extends over two lines with arguments"""
        self.verify("#def testMeth(arg=1234,\n" +
                    "  arg2=5678)\n" +
                    "$arg $arg2\n" +
                    "#end def\n" +
                    "$testMeth()",
                    "1234 5678\n")


class DecoratorDirective(OutputTest):
    def test1(self):
        """single line #def with decorator"""

        self.verify("#@ blah", "#@ blah")
        self.verify("#@23 blah", "#@23 blah")
        self.verify("#@@TR: comment", "#@@TR: comment")

        self.verify(
            "#from tests.SyntaxAndOutput_test import dummydecorator\n"
            "#@dummydecorator"
            "\n#def testMeth():1234\n$testMeth()",
            "1234"
        )

        self.verify(
            "#from tests.SyntaxAndOutput_test import dummydecorator\n"
            "#@dummydecorator"
            "\n#block testMeth:1234",
            "1234",
        )

        with pytest.raises(ParseError):
            self.verify(
                "#from tests.SyntaxAndOutput_test import dummydecorator\n"
                "#@dummydecorator\n sdf"
                "\n#def testMeth():1234\n$testMeth()",
                "1234"
            )

    def test2(self):
        """#def with multiple decorators"""
        self.verify(
            "#from tests.SyntaxAndOutput_test import dummydecorator\n"
            "#@dummydecorator\n"
            "#@dummydecorator\n"
            "#def testMeth()\n"
            "1234\n"
            "#end def\n"
            "$testMeth()",
            "1234\n"
        )


class BlockDirective(OutputTest):
    def test1(self):
        """#block"""
        self.verify("#block testBlock\n1234\n#end block",
                    "1234\n")

        self.verify("#block testBlock ##comment\n1234\n#end block",
                    "1234\n")

    def test2(self):
        """#block, gobble WS"""
        self.verify("  #block testBlock   \n1234\n  #end block  ",
                    "1234\n")

    def test5(self):
        """#block with 2 nested blocks

        Blocks can be nested to any depth and the name of the block is optional
        for the #end block part: #end block OR #end block [name] """

        self.verify("""#block testBlock
this is a test block
#block outerNest
outer
#block innerNest
inner
#end block innerNest
#end block outerNest
---
#end block testBlock
""",
                    "this is a test block\nouter\ninner\n---\n")

    def test6(self):
        """single line #block """
        self.verify(
            "#block testMeth: This is my block",
            "This is my block")

    def test7(self):
        """single line #block with WS"""
        self.verify(
            "#block testMeth: This is my block",
            "This is my block")

    def test8(self):
        """single line #block 1 escaped $placeholders"""
        self.verify(
            r"#block testMeth: \$aFunc($anInt)",
            "$aFunc(1)")

    def test9(self):
        """single line #block 1 escaped $placeholders + WS"""
        self.verify(
            r"#block testMeth: \$aFunc( $anInt )",
            "$aFunc( 1 )")

    def test10(self):
        """single line #block 1 escaped $placeholders + more WS"""
        self.verify(
            r"#block testMeth  : \$aFunc( $anInt )",
            "$aFunc( 1 )")

    def test14(self):
        """single line #block with None for content"""
        self.verify(
            """#block testMeth: $None\ntest $testMeth()-""",
            "test -")

    def test15(self):
        """single line #block with nothing for content"""
        self.verify(
            """#block testMeth: \nfoo\n#end block\ntest $testMeth()-""",
            "foo\ntest foo\n-")


def test_del_directive():
    cls = compile_to_class(
        "#py foo = {'a': '1', 'b': '2'}\n"
        "#del foo['a']\n"
        '$len($foo.keys()) ${list(foo.keys())[0]}'
    )
    assert cls().respond() == "1 b"


class IfDirective(OutputTest):

    def test1(self):
        """simple #if block"""
        self.verify("#if 1\n$aStr\n#end if\n",
                    "blarg\n")

        self.verify("#if 1:\n$aStr\n#end if\n",
                    "blarg\n")

        self.verify("#if 1:   \n$aStr\n#end if\n",
                    "blarg\n")

        self.verify("#if 1: ##comment \n$aStr\n#end if\n",
                    "blarg\n")

        self.verify("#if 1 ##comment \n$aStr\n#end if\n",
                    "blarg\n")

        self.verify("#if 1##for i in range(10)#$i#end for##end if",
                    '0123456789')

        self.verify("#if 1: #for i in range(10)#$i#end for",
                    '0123456789')

        self.verify("#if 1: #for i in range(10):$i",
                    '0123456789')

    def test2(self):
        """simple #if block, with WS"""
        self.verify("   #if 1\n$aStr\n  #end if  \n",
                    "blarg\n")

    def test3(self):
        """simple #if block, with WS and explicit closures"""
        self.verify("   #if 1#\n$aStr\n  #end if #--\n",
                    "   \nblarg\n  --\n")

    def test4(self):
        """#if block using $numOne"""
        self.verify("#if $numOne\n$aStr\n#end if\n",
                    "blarg\n")

    def test5(self):
        """#if block using $zero"""
        self.verify("#if $zero\n$aStr\n#end if\n",
                    "")

    def test6(self):
        """#if block using $emptyString"""
        self.verify("#if $emptyString\n$aStr\n#end if\n",
                    "")

    def test7(self):
        """#if ... #else ... block using a $emptyString"""
        self.verify("#if $emptyString\n$anInt\n#else\n$anInt - $anInt\n#end if",
                    "1 - 1\n")

    def test8(self):
        """#if ... #elif ... #else ... block using a $emptyString"""
        self.verify("#if $emptyString\n$c\n#elif $numOne\n$numOne\n#else\n$c - $c\n#end if",
                    "1\n")

    def test9(self):
        """#if 'not' test, with #slurp"""
        self.verify("#if not $emptyString\n$aStr#slurp\n#end if\n",
                    "blarg")

    def test10(self):
        """#if block using $*emptyString

        This should barf
        """
        with pytest.raises(ParseError):
            self.verify("#if $*emptyString\n$aStr\n#end if\n",
                        "")

    def test11(self):
        """#if block using invalid top-level $(placeholder) syntax - should barf"""

        for badSyntax in (
                "#if $*5*emptyString\n$aStr\n#end if\n",
                "#if ${emptyString}\n$aStr\n#end if\n",
                "#if $(emptyString)\n$aStr\n#end if\n",
                "#if $[emptyString]\n$aStr\n#end if\n",
                "#if $!emptyString\n$aStr\n#end if\n",
        ):
            with pytest.raises(ParseError):
                self.verify(badSyntax, "")

    def test12(self):
        """#if ... #else if ... #else ... block using a $emptyString
        Same as test 8 but using else if instead of elif"""
        self.verify("#if $emptyString\n$c\n#else if $numOne\n$numOne\n#else\n$c - $c\n#end if",
                    "1\n")

    def test13(self):
        """#if# ... #else # ... block using a $emptyString with """
        self.verify("#if $emptyString# $anInt#else#$anInt - $anInt#end if",
                    "1 - 1")

    def test17(self):
        """single-line #if:  """
        self.verify("#if 1: foo\n#if 0: bar\n#if 1: foo",
                    "foo\nfoo")

        self.verify("#if 1: foo\n#if 0: bar\n#if 1: foo",
                    "foo\nfoo")

    def test18(self):
        """single-line #if: \n#else: """
        self.verify("#if 1: foo\n#elif 0: bar",
                    "foo\n")

        self.verify("#if 1: foo\n#elif 0: bar\n#else: blarg\n",
                    "foo\n")

        self.verify("#if 0: foo\n#elif 0: bar\n#else: blarg\n",
                    "blarg\n")


class WhileDirective(OutputTest):
    def test1(self):
        """simple #while with a counter"""
        self.verify("#py i = 0\n#while $i < 5\n$i#slurp\n#py i += 1\n#end while",
                    "01234")


class ContinueDirective(OutputTest):
    def test1(self):
        """#continue with a #while"""
        self.verify("""#py i = 0
#while $i < 5
#if $i == 3
  #py i += 1
  #continue
#end if
$i#slurp
#py i += 1
#end while""",
                    "0124")

    def test2(self):
        """#continue with a #for"""
        self.verify("""#for i in range(5)
#if $i == 3
  #continue
#end if
$i#slurp
#end for""",
                    "0124")


class BreakDirective(OutputTest):
    def test1(self):
        """#break with a #while"""
        self.verify("""#py i = 0
#while $i < 5
#if $i == 3
  #break
#end if
$i#slurp
#py i += 1
#end while""",
                    "012")

    def test2(self):
        """#break with a #for"""
        self.verify("""#for i in range(5)
#if $i == 3
  #break
#end if
$i#slurp
#end for""",
                    "012")


class TryDirective(OutputTest):

    def test1(self):
        """simple #try
        """
        self.verify("#try\n1234\n#except\nblarg\n#end try",
                    "1234\n")

    def test2(self):
        """#try / #except with #raise
        """
        self.verify("#try\n#raise ValueError\n#except\nblarg\n#end try",
                    "blarg\n")

    def test3(self):
        """#try / #except with #raise + WS

        Should gobble
        """
        self.verify("  #try  \n  #raise ValueError \n  #except \nblarg\n  #end try",
                    "blarg\n")

    def test4(self):
        """#try / #except with #raise + WS and leading text

        Shouldn't gobble
        """
        self.verify("--#try  \n  #raise ValueError \n  #except \nblarg\n  #end try#--",
                    "--\nblarg\n  --")

    def test5(self):
        """nested #try / #except with #raise
        """
        self.verify("""#try
  #raise ValueError
#except
  #try
   #raise ValueError
  #except
blarg
  #end try
#end try""",
                    "blarg\n")


class FinallyDirective(OutputTest):
    def test(self):
        self.verify(
            '#try\n'
            '    before\n'
            '    #raise ValueError\n'
            '#except ValueError\n'
            '    in except\n'
            '#finally\n'
            '    in finally\n'
            '#end try\n',
            '    before\n'
            '    in except\n'
            '    in finally\n'
        )


class PassDirective(OutputTest):
    def test1(self):
        """#pass in a #try / #except block
        """
        self.verify("#try\n#raise ValueError\n#except\n#pass\n#end try",
                    "")

    def test2(self):
        """#pass in a #try / #except block + WS
        """
        self.verify("  #try  \n  #raise ValueError  \n  #except  \n   #pass   \n   #end try",
                    "")


class AssertDirective(OutputTest):
    def test1(self):
        """simple #assert
        """
        self.verify("#py x = 1234\n#assert $x == 1234",
                    "")

    def test2(self):
        """simple #assert that fails
        """
        with pytest.raises(AssertionError):
            self.verify('#py x = 1234\n#assert $x == 999', '')

    def test3(self):
        """simple #assert with WS
        """
        self.verify("#py x = 1234\n   #assert $x == 1234   ",
                    "")


class RaiseDirective(OutputTest):
    def test1(self):
        """simple #raise ValueError

        Should raise ValueError
        """
        with pytest.raises(ValueError):
            self.verify('#raise ValueError', '')

    def test2(self):
        """#raise ValueError in #if block

        Should raise ValueError
        """

        def test(self=self):
            self.verify("#if 1\n#raise ValueError\n#end if\n",
                        "")
        self.failUnlessRaises(ValueError, test)

    def test3(self):
        """#raise ValueError in #if block

        Shouldn't raise ValueError
        """
        self.verify("#if 0\n#raise ValueError\n#else\nblarg#end if\n",
                    "blarg\n")


class ImportDirective(OutputTest):
    def test1(self):
        """#import math
        """
        self.verify("#import math",
                    "")

    def test2(self):
        """#import math + WS

        Should gobble
        """
        self.verify("    #import math    ",
                    "")

    def test3(self):
        """#import math + WS + leading text

        Shouldn't gobble
        """
        self.verify("  --  #import math    ",
                    "  --  ")

    def test4(self):
        """#from math import syn
        """
        self.verify("#from math import cos",
                    "")

    def test5(self):
        """#from math import cos  + WS
        Should gobble
        """
        self.verify("    #from math import cos  ",
                    "")

    def test6(self):
        """#from math import cos  + WS + leading text
        Shouldn't gobble
        """
        self.verify("  --  #from math import cos  ",
                    "  --  ")

    def test7(self):
        """#from math import cos -- use it
        """
        self.verify("#from math import cos\n$cos(0)",
                    "1.0")

    def test8(self):
        """#from math import cos,tan,sin -- and use them
        """
        self.verify("#from math import cos, tan, sin\n$cos(0)-$tan(0)-$sin(0)",
                    "1.0-0.0-0.0")

    def test9(self):
        """#import os.path -- use it
        """

        self.verify("#import os.path\n$os.path.exists('.')",
                    repr(True))

    def test10(self):
        """#import os.path -- use it with NameMapper turned off
        """
        self.verify("""##
#compiler-settings
useNameMapper=False
#end compiler-settings
#import os.path
$os.path.exists('.')""",
                    repr(True))

    def test11(self):
        """#from math import *
        """

        self.verify("#from math import *\n$pow(1,2) $log10(10)",
                    "1.0 1.0")


def test_extends():
    ret = compile_to_class(
        '#extends testing.templates.extends_test_template\n'
        '#implements respond\n'
        '$spacer()\n'
    )().respond()
    assert ret == '<img src="spacer.gif" width="1" height="1" alt="" />\n'


def test_extends_with_partial_baseclass_import():
    cls = compile_to_class(
        '#import testing\n'
        '#extends testing.templates.extends_test_template\n'
        '#implements respond\n'
        '$spacer()\n'
    )
    assert cls().respond() == (
        '<img src="spacer.gif" width="1" height="1" alt="" />\n'
    )


def test_super_directive():
    # pylint:disable=no-name-in-module,import-error
    from testing.templates.src.super_child import YelpCheetahTemplate
    ret = YelpCheetahTemplate().respond()
    assert ret.strip() == (
        'this is base foo    This is child foo\n'
        'this is base foo    super-1234\n'
        ' super-99 super-20'
    )


class ImportantExampleCases(OutputTest):
    def test1(self):
        """how to make a comma-delimited list"""
        self.verify("""#py sep = ''
#for letter in $letterList
$sep$letter#slurp
#py sep = ', '
#end for
""",
                    "a, b, c")


class VarExists(OutputTest):
    def test2(self):
        self.verify("$varExists('anInt')",
                    repr(True))

    def test3(self):
        self.verify("$varExists('bogus')",
                    repr(False))

    def test4(self):
        self.verify("#if $varExists('bogus')\n1234\n#else\n999\n#end if",
                    "999\n")

    def test5(self):
        self.verify("#if $varExists('anInt')\n1234\n#else\n999#end if",
                    "1234\n")


class GetVar(OutputTest):
    def test2(self):
        self.verify("$getVar('anInt')",
                    "1")

    def test3(self):
        self.verify("$self.getVar('anInt')",
                    "1")

    def test4(self):
        self.verify("$getVar('bogus',  1234)",
                    "1234")


class MiscComplexSyntax(OutputTest):
    def test1(self):
        """Complex use of {},[] and () in a #py expression
        ----
        #py c = {'A':0}[{}.get('a', {'a' : 'A'}['a'])]
        $c
        """
        self.verify("#py c = {'A':0}[{}.get('a', {'a' : 'A'}['a'])]\n$c",
                    "0")


def test_comment_directive_ambiguity():
    cls = compile_to_class(
        '#py foo = 1##py bar = 2\n'
        '$foo $bar\n'
    )
    assert cls().respond().strip() == '1 2'


def test_nested_defs_with_calls():
    """Fails with unbound local `trans` referenced before assignment."""
    cls = compile_to_class(
        '#def callfn1(arg)\n'
        'Arg fn1: $arg\n'
        '#end def\n'
        '\n'
        '#def callfn2(arg)\n'
        'Arg fn2: $arg\n'
        '#end def\n'
        '\n'
        '#def foo()\n'
        '    #call $callfn1\n'
        '        #def bar()\n'
        '            #call $callfn2\n'
        '                val\n'
        '            #end call\n'
        '        #end def\n'
        '        $bar()\n'
        '    #end call\n'
        '#end def\n'
        '$foo()\n'
    )
    ret = ' '.join(cls().respond().strip().split())
    assert ret == 'Arg fn1: Arg fn2: val'


def test_trivial_implements_template():
    cls = compile_to_class('#implements respond')
    assert cls().respond() == ''


def test_bytes():
    cls = compile_to_class("#py foo = b'bar'\n$foo")
    assert cls().respond() == 'bar'


def test_default_argument_multipart_expression():
    cls = compile_to_class(
        '#def foo(bar=1 + 1)\n'
        '$bar\n'
        '#end def\n'
        '$foo()'
    )
    assert cls().respond() == '2\n'


def test_default_argument_boolean_expression():
    cls = compile_to_class(
        '#py herp = "derp"\n'
        '#def foo(bar)\n'
        '$bar\n'
        '#end def\n'
        '$foo("baz" if $herp == "derp" else "buz")'
    )
    assert cls().respond() == 'baz\n'


def test_default_is_dict():
    cls = compile_to_class(
        '#def foo(bar={"baz": "womp"})\n'
        "$bar['baz']\n"
        '#end def\n'
        '$foo()'
    )
    assert cls().respond() == 'womp\n'


def test_line_continuation():
    cls = compile_to_class(
        '#py foo = "bar baz " + \\\n'
        '    "womp"\n'
        '$foo'
    )
    assert cls().respond() == 'bar baz womp'


def test_identifier_ending_in_dot():
    cls = compile_to_class(
        '#py foo = "bar"\n'
        '$foo.'
    )
    assert cls().respond() == 'bar.'


def test_with_statement_yields_value():
    cls = compile_to_class(
        '#import contextlib\n'
        '\n'
        '#@contextlib.contextmanager\n'
        '#def my_context_manager(herp)\n'
        'Ctx Before\n'
        '$herp\n'
        '#yield 9001\n'
        'Ctx After\n'
        '#end def\n'
        '\n'
        'Before\n'
        '#with $my_context_manager(1337) as val:\n'
        'Ctx Inside\n'
        '$val\n'
        '#end with\n'
        'After\n'
    )
    assert cls().respond().strip() == (
        'Before\n'
        'Ctx Before\n'
        '1337\n'
        'Ctx Inside\n'
        '9001\n'
        'Ctx After\n'
        'After'
    )


def test_with_statement_yield_no_value():
    cls = compile_to_class(
        '#import contextlib\n'
        '\n'
        '#@contextlib.contextmanager\n'
        '#def my_context_manager(herp)\n'
        'Ctx Before\n'
        '$herp\n'
        '#yield\n'
        'Ctx After\n'
        '#end def\n'
        '\n'
        'Before\n'
        '#with $my_context_manager(1234)\n'
        'Ctx inside\n'
        '#end with\n'
        'After\n'
    )
    assert cls().respond().strip() == (
        'Before\n'
        'Ctx Before\n'
        '1234\n'
        'Ctx inside\n'
        'Ctx After\n'
        'After'
    )


def test_with_statement_short_form():
    cls = compile_to_class(
        '#import contextlib\n'
        '\n'
        '#@contextlib.contextmanager\n'
        '#def ctx()\n'
        'Ctx Before\n'
        '#yield\n'
        'Ctx After\n'
        '#end def\n'
        '\n'
        'Before\n'
        '#with $ctx():Ctx inside\n'
        'After\n'
    )
    assert cls().respond().strip() == (
        'Before\n'
        'Ctx Before\n'
        'Ctx inside\n'
        'Ctx After\n'
        'After'
    )


def js_filter(obj):
    return '<js_filtered>%r</js_filtered>' % str(obj)


def test_with_statement_filter():
    cls = compile_to_class('''
    #import contextlib
    #from tests.SyntaxAndOutput_test import js_filter

    #@contextlib.contextmanager
    #def sets_filter():
        #with self.set_filter(js_filter)
            #yield
        #end with
    #end def


    #with self.sets_filter()
        #py foo = 'bar'
        $foo
    #end with
    ''')

    inst = cls(filter_fn=filters.unicode_filter)
    assert inst.respond().strip() == "<js_filtered>'bar'</js_filtered>"


def test_with_statement_call():
    cls = compile_to_class('''
    #import contextlib

    #def embolden(arg)
        <b>$arg.strip()</b>
    #end def

    #@contextlib.contextmanager
    #def bold():
        before.
        #call self.embolden
            #yield
        #end call xxx
        after.
    #end def

    begin.
    #with $bold()
        mycontent!
    #end with
    end.
    ''')

    result = ' '.join(cls().respond().strip().split())
    assert result == "begin. before. <b>mycontent!</b> after. end."


def test_with_filter():
    cls = compile_to_class(
        '#from Cheetah.filters import unicode_filter\n'
        '#py var = "<>"\n'
        '$var\n'
        '#with self.set_filter(unicode_filter)\n'
        '$var\n'
        '#end with\n'
        '$var\n'
    )
    assert cls().respond() == '&lt;&gt;\n<>\n&lt;&gt;\n'


def test_list_comp_with_cheetah_var():
    # Regression test for v0.11.0
    cls = compile_to_class('${[$x for x in (1, 2, 3)][0]}')
    assert cls().respond() == '1'
