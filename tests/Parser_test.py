# -*- coding: UTF-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import pytest

from Cheetah.compile import compile_to_class
from Cheetah.legacy_parser import ArgList
from Cheetah.legacy_parser import ParseError
from Cheetah.legacy_parser import UnknownDirectiveError
from testing.util import assert_raises_exactly


def test_ArgList_merge1():
    """Testing the ArgList case results from
    Template.Preprocessors.test_complexUsage
    """
    arglist = ArgList()
    arglist.add_argument('arg')
    assert arglist.merge() == [('arg', None)]


def test_ArgList_merge2():
    """Testing the ArgList case results from
    SyntaxAndOutput.BlockDirective.test4
    """
    arglist = ArgList()
    arglist.add_argument('a')
    arglist.add_default('999')
    arglist.next()
    arglist.add_argument('b')
    arglist.add_default('444')

    assert arglist.merge() == [('a', '999'), ('b', '444')]


def test_merge3():
    """Testing the ArgList case results
    from SyntaxAndOutput.BlockDirective.test13
    """
    arglist = ArgList()
    arglist.add_argument('arg')
    arglist.add_default("'This is my block'")
    assert arglist.merge() == [('arg', "'This is my block'")]


def test_unknown_directive_name():
    with assert_raises_exactly(
        UnknownDirectiveError,
        '\n\n'
        'Bad directive name: "foo". You may want to escape that # sign?\n'
        'Line 1, column 2\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#foo\n'
        '      ^\n',
    ):
        compile_to_class('#foo\n')


def test_malformed_triple_quotes():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'Malformed triple-quoted string\n'
        'Line 1, column 3\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |${"""}\n'
        '       ^\n',
    ):
        compile_to_class('${"""}')


def test_unclosed_directives():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'Some #directives are missing their corresponding #end ___ tag: if\n'
        'Line 1, column 9\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#if True\n'
        '             ^\n'
    ):
        compile_to_class('#if True\n')


def test_invalid_identifier():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'Invalid identifier\n'
        'Line 1, column 5\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#def\n'
        '         ^\n'
    ):
        compile_to_class('#def\n')


def test_end_but_nothing_to_end():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        '#end found, but nothing to end\n'
        'Line 1, column 8\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#end if\n'
        '            ^\n'
    ):
        compile_to_class('#end if\n')


def test_invalid_end_directive():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'Invalid end directive\n'
        'Line 1, column 5\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#end\n'
        '         ^\n'
    ):
        compile_to_class('#end\n')


def test_invalid_nesting_directives():
    # TODO: this one is off by a bit on the exception message
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        '#end if found, expected #end for\n'
        'Line 4, column 1\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#if True\n'
        '2   |#for i in range(5)\n'
        '3   |#end if\n'
        '4   |#end for\n'
        '     ^\n'
    ):
        compile_to_class(
            '#if True\n'
            '#for i in range(5)\n'
            '#end if\n'
            '#end for\n'
        )


def test_parse_error_for_implements_argspec():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'yelp_cheetah does not support argspecs for #implements\n'
        'Line 1, column 16\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#implements foo(bar)\n'
        '                    ^\n'
    ):
        compile_to_class('#implements foo(bar)')


def test_parse_error_for_multiple_inheritance():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'yelp_cheetah does not support multiple inheritance\n'
        'Line 1, column 33\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#extends Cheetah.Template, object\n'
        '                                     ^\n'
    ):
        compile_to_class('#extends Cheetah.Template, object')


def test_parse_error_long_file():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        "EOF was reached before a matching ')' was found for the '('\n"
        'Line 5, column 5\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '2   |2\n'
        '3   |3\n'
        '4   |4\n'
        '5   |$foo(\n'
        '         ^\n'
        '6   |6\n'
        '7   |7\n'
        '8   |8\n'
    ):
        compile_to_class('1\n2\n3\n4\n$foo(\n6\n7\n8\n')


def test_unclosed_enclosure():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        "EOF was reached before a matching '}' was found for the '{'\n"
        'Line 1, column 2\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |${hai +\n'
        '      ^\n'
    ):
        compile_to_class('${hai +')


def test_parse_error_on_attr_with_var():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'Invalid #attr directive. It should contain simple Python literals.\n'
        'Line 1, column 13\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#attr foo = $bar\n'
        '                 ^\n'
    ):
        compile_to_class('#attr foo = $bar\n')


def test_parse_error_on_attr_with_dollar_sign():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        '#attr directive must not contain `$`\n'
        'Line 1, column 7\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#attr $foo = "hai"\n'
        '           ^\n'
    ):
        compile_to_class('#attr $foo = "hai"\n')


def test_invalid_line_continuation():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'Line ending expected\n'
        'Line 1, column 20\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#py foo = "bar" + \\hi, not a new line\n'
        '                        ^\n'
    ):
        compile_to_class('#py foo = "bar" + \\hi, not a new line')


def test_close_wrong_enclosure():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        "A ']' was found at line 1, col 4 before a matching '}' was found for the '{'\n"
        'Line 1, column 2\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |${a]\n'
        '      ^\n'
    ):
        compile_to_class('${a]')


def test_reach_eof():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        "EOF was reached before a matching ')' was found for the '('\n"
        'Line 1, column 7\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#super(\n'
        '           ^\n'
    ):
        compile_to_class('#super(')


def test_non_ending_compiler_settings():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'Some #directives are missing their corresponding #end ___ tag: compiler-settings\n'
        'Line 2, column 26\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#compiler-settings\n'
        '2   |useLegacyImportMode = True\n'
        '                              ^\n'
    ):
        compile_to_class('#compiler-settings\nuseLegacyImportMode = True')


def test_weird_close_call():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        "Expected a ')' before an end '}'\n"
        'Line 1, column 6\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |$foo(}\n'
        '          ^\n'
    ):
        compile_to_class('$foo(}')


def test_invalid_syntax_in_super():
    # I'm not sure this error is actually correct
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        '$ is not allowed here.\n'
        'Line 1, column 12\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#super(foo=${bar})\n'
        '                ^\n'
    ):
        compile_to_class('#super(foo=${bar})')


def test_invalid_syntax_in_call():
    # I'm not sure this error is actually correct
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        "Long-form placeholders - ${}, $(), $[], etc. are not valid inside "
        "expressions. Use them in top-level $placeholders only.\n"
        'Line 1, column 11\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |$herp(foo=${bar})\n'
        '               ^\n'
    ):
        compile_to_class('$herp(foo=${bar})')


def test_expected_identifier_after_star():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'Expected an identifier.\n'
        'Line 1, column 9\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#super(*)\n'
        '             ^\n'
    ):
        compile_to_class('#super(*)')


def test_unexpected_character_parse_error():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'Unexpected character.\n'
        'Line 1, column 8\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#super(☃)\n'
        '            ^\n'
    ):
        compile_to_class('#super(☃)')


def test_def_with_dollar_sign_invalid():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'use #def func() instead of #def $func()\n'
        'Line 1, column 6\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#def $foo()\n'
        '          ^\n'
        '2   |#end def\n'
    ):
        compile_to_class(
            '#def $foo()\n'
            '#end def\n'
        )


def test_def_without_arglist_invalid():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        '#def must contain an argspec (at least ())\n'
        'Line 1, column 9\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#def foo\n'
        '             ^\n'
        '2   |#end def\n'
    ):
        compile_to_class(
            '#def foo\n'
            '#end def\n'
        )


def test_block_with_an_argspec_invalid():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        '#block must not have an argspec, did you mean #def?\n'
        'Line 1, column 11\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#block foo(bar)\n'
        '               ^\n'
        '2   |#end block\n'
    ):
        compile_to_class(
            '#block foo(bar)\n'
            '#end block\n'
        )


def test_self_in_arglist_invalid():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'Do not specify `self` in an arglist, it is assumed\n'
        'Line 1, column 10\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#def foo(self, bar)\n'
        '              ^\n'
        '2   |#end def\n'
    ):
        compile_to_class(
            '#def foo(self, bar)\n'
            '#end def\n'
        )


def test_set_with_dollar_signs_raises():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        "SyntaxError: can't assign to function call (<unknown>, line 1)\n\n"
        'Line 1, column 13\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#py $foo = 1\n'
        '                 ^\n'
    ):
        compile_to_class('#py $foo = 1\n')


@pytest.mark.parametrize('decorator', ('@classmethod', '@staticmethod'))
def test_classmethod_staticmethod_not_allowed(decorator):
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        '@classmethod / @staticmethod are not supported\n'
        'Line 1, column 2\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#{}\n'
        '      ^\n'
        '2   |#def foo(bar)\n'
        '3   |    #return bar + 1\n'
        '4   |#end def\n'.format(decorator)
    ):
        compile_to_class(
            '#{}\n'
            '#def foo(bar)\n'
            '    #return bar + 1\n'
            '#end def\n'.format(decorator)
        )


def test_lvalue_for():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'lvalue of for must not contain a `$`\n'
        'Line 1, column 6\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#for $foo in bar\n'
        '          ^\n'
        '2   |$foo\n'
        '3   |#end for\n'
    ):
        compile_to_class(
            '#for $foo in bar\n'
            '$foo\n'
            '#end for\n',
        )


def test_uncaught_syntax_error():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        "SyntaxError: can't assign to function call (<unknown>, line 1)\n\n"
        'Line 3, column 15\n\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |Hello\n'
        '2   |World\n'
        '3   |#py x = $y = 1\n'
        '                   ^\n'
    ):
        compile_to_class('Hello\nWorld\n#py x = $y = 1\n')


def test_errors_on_invalid_setting():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        "UnexpectedSettingName: not_a_real_setting\n\n"
        'Line 3, column 23\n\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#compiler-settings\n'
        '2   |not_a_real_setting = True\n'
        '3   |#end compiler-settings\n'
        '                           ^\n'
    ):
        compile_to_class(
            '#compiler-settings\n'
            'not_a_real_setting = True\n'
            '#end compiler-settings\n'
        )


def test_errors_on_blinged_kwarg():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'kwargs should not start with $\n'
        'Line 1, column 6\n\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |$foo($bar=$baz)\n'
        '          ^\n'
    ):
        compile_to_class(
            '$foo($bar=$baz)'
        )


def test_errors_garbage_after_end_directive():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'Invalid garbage after #end directive\n'
        'Line 2, column 15\n\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#block foo\n'
        '2   |#end block foo\n'
        '                   ^\n'
    ):
        compile_to_class(
            '#block foo\n'
            '#end block foo\n'
        )
