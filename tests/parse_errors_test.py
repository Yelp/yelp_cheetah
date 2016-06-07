# -*- coding: UTF-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import pytest

from Cheetah.compile import compile_source
from Cheetah.legacy_parser import ParseError
from Cheetah.legacy_parser import UnknownDirectiveError
from testing.util import assert_raises_exactly


def assert_parse_error(error, source, cls=ParseError):
    with assert_raises_exactly(cls, error):
        compile_source(source)


def test_unknown_directive_name():
    assert_parse_error(
        '\n\n'
        'Bad directive name: "foo". You may want to escape that # sign?\n'
        'Line 1, column 2\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#foo\n'
        '      ^\n',

        '#foo\n',
        cls=UnknownDirectiveError,
    )


def test_malformed_triple_quotes():
    assert_parse_error(
        '\n\n'
        'Malformed triple-quoted string\n'
        'Line 1, column 3\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |${"""}\n'
        '       ^\n',

        '${"""}',
    )


def test_unclosed_directives():
    assert_parse_error(
        '\n\n'
        'Some #directives are missing their corresponding #end ___ tag: if\n'
        'Line 1, column 9\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#if True\n'
        '             ^\n',

        '#if True\n',
    )


def test_invalid_identifier():
    assert_parse_error(
        '\n\n'
        'Invalid identifier\n'
        'Line 1, column 5\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#def\n'
        '         ^\n',

        '#def\n',
    )


def test_end_but_nothing_to_end():
    assert_parse_error(
        '\n\n'
        '#end found, but nothing to end\n'
        'Line 1, column 8\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#end if\n'
        '            ^\n',

        '#end if\n',
    )


def test_invalid_end_directive():
    assert_parse_error(
        '\n\n'
        'Invalid end directive\n'
        'Line 1, column 5\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#end\n'
        '         ^\n',

        '#end\n',
    )


def test_invalid_nesting_directives():
    # TODO: this one is off by a bit on the exception message
    assert_parse_error(
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
        '     ^\n',

        '#if True\n'
        '#for i in range(5)\n'
        '#end if\n'
        '#end for\n',
    )


def test_parse_error_for_implements_argspec():
    assert_parse_error(
        '\n\n'
        'yelp_cheetah does not support argspecs for #implements\n'
        'Line 1, column 16\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#implements foo(bar)\n'
        '                    ^\n',

        '#implements foo(bar)',
    )


def test_parse_error_for_multiple_inheritance():
    assert_parse_error(
        '\n\n'
        'yelp_cheetah does not support multiple inheritance\n'
        'Line 1, column 33\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#extends Cheetah.Template, object\n'
        '                                     ^\n',

        '#extends Cheetah.Template, object',
    )


def test_parse_error_long_file():
    assert_parse_error(
        '\n\n'
        "EOF while searching for ')' (to match '(')\n"
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
        '8   |8\n',

        '1\n2\n3\n4\n$foo(\n6\n7\n8\n',
    )


def test_unclosed_enclosure():
    assert_parse_error(
        '\n\n'
        "EOF while searching for '}' (to match '{')\n"
        'Line 1, column 2\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |${hai +\n'
        '      ^\n',

        '${hai +',
    )


def test_parse_error_on_attr_with_var():
    assert_parse_error(
        '\n\n'
        'Invalid Syntax\n'
        'Line 1, column 13\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#attr foo = $bar\n'
        '                 ^\n',

        '#attr foo = $bar\n',
    )


def test_parse_error_on_attr_with_dollar_sign():
    assert_parse_error(
        '\n\n'
        '#attr directive must not contain `$`\n'
        'Line 1, column 7\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#attr $foo = "hai"\n'
        '           ^\n',

        '#attr $foo = "hai"\n',
    )


def test_invalid_line_continuation():
    assert_parse_error(
        '\n\n'
        'Invalid Syntax\n'
        'Line 1, column 19\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#py foo = "bar" + \\hi, not a new line\n'
        '                       ^\n',

        '#py foo = "bar" + \\hi, not a new line',
    )


def test_close_wrong_enclosure():
    assert_parse_error(
        '\n\n'
        "Mismatched token. Found ']' while searching for '}'\n"
        'Line 1, column 2\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |${a]\n'
        '      ^\n',

        '${a]',
    )


def test_reach_eof():
    assert_parse_error(
        '\n\n'
        "EOF while searching for ')' (to match '(')\n"
        'Line 1, column 7\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#super(\n'
        '           ^\n',

        '#super(',
    )


def test_non_ending_compiler_settings():
    assert_parse_error(
        '\n\n'
        'Some #directives are missing their corresponding #end ___ tag: compiler-settings\n'
        'Line 2, column 26\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#compiler-settings\n'
        '2   |useLegacyImportMode = True\n'
        '                              ^\n',

        '#compiler-settings\nuseLegacyImportMode = True',
    )


def test_weird_close_call():
    assert_parse_error(
        '\n\n'
        "Mismatched token. Found '}' while searching for ')'\n"
        'Line 1, column 5\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |$foo(}\n'
        '         ^\n',

        '$foo(}',
    )


def test_invalid_syntax_in_super():
    assert_parse_error(
        '\n\n'
        'Invalid Syntax\n'
        'Line 1, column 12\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#super(foo=${bar})\n'
        '                ^\n',

        '#super(foo=${bar})',
    )


def test_invalid_syntax_in_call():
    assert_parse_error(
        '\n\n'
        'Invalid identifier\n'
        'Line 1, column 12\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |$herp(foo=${bar})\n'
        '                ^\n',

        '$herp(foo=${bar})',
    )


def test_placeholders_cannot_start_with_whitespace():
    assert_parse_error(
        '\n\n'
        'Expected identifier\n'
        'Line 1, column 3\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |${ foo }\n'
        '       ^\n',

        '${ foo }',
    )


def test_unexpected_character_parse_error():
    assert_parse_error(
        '\n\n'
        'Invalid Syntax\n'
        'Line 1, column 8\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#super(☃)\n'
        '            ^\n',

        '#super(☃)',
    )


def test_def_with_dollar_sign_invalid():
    assert_parse_error(
        '\n\n'
        'use #def func() instead of #def $func()\n'
        'Line 1, column 6\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#def $foo()\n'
        '          ^\n'
        '2   |#end def\n',

        '#def $foo()\n'
        '#end def\n',
    )


def test_def_without_arglist_invalid():
    assert_parse_error(
        '\n\n'
        '#def must contain an argspec (at least ())\n'
        'Line 1, column 9\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#def foo\n'
        '             ^\n'
        '2   |#end def\n',

        '#def foo\n'
        '#end def\n',
    )


def test_block_with_an_argspec_invalid():
    assert_parse_error(
        '\n\n'
        '#block must not have an argspec, did you mean #def?\n'
        'Line 1, column 11\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#block foo(bar)\n'
        '               ^\n'
        '2   |#end block\n',

        '#block foo(bar)\n'
        '#end block\n',
    )


def test_self_in_arglist_invalid():
    assert_parse_error(
        '\n\n'
        'SyntaxError: Duplicate arguments: self\n\n'
        'Line 2, column 1\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#def foo(self, bar)\n'
        '2   |#end def\n'
        '     ^\n',

        '#def foo(self, bar)\n'
        '#end def\n'
    )


def test_set_with_dollar_signs_raises():
    assert_parse_error(
        '\n\n'
        "SyntaxError: can't assign to function call (<unknown>, line 1)\n\n"
        'Line 1, column 13\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#py $foo = 1\n'
        '                 ^\n',

        '#py $foo = 1\n',
    )


@pytest.mark.parametrize('decorator', ('@classmethod', '@staticmethod'))
def test_classmethod_staticmethod_not_allowed(decorator):
    assert_parse_error(
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
        '4   |#end def\n'.format(decorator),

        '#{}\n'
        '#def foo(bar)\n'
        '    #return bar + 1\n'
        '#end def\n'.format(decorator),
    )


def test_lvalue_for():
    assert_parse_error(
        '\n\n'
        "SyntaxError: can't assign to function call (<unknown>, line 1)\n\n"
        'Line 2, column 1\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#for $foo in bar\n'
        '2   |$foo\n'
        '     ^\n'
        '3   |#end for\n',

        '#for $foo in bar\n'
        '$foo\n'
        '#end for\n',
    )


def test_uncaught_syntax_error():
    assert_parse_error(
        '\n\n'
        "SyntaxError: can't assign to function call (<unknown>, line 1)\n\n"
        'Line 3, column 15\n\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |Hello\n'
        '2   |World\n'
        '3   |#py x = $y = 1\n'
        '                   ^\n',

        'Hello\nWorld\n#py x = $y = 1\n',
    )


def test_errors_on_invalid_setting():
    assert_parse_error(
        '\n\n'
        "UnexpectedSettingName: not_a_real_setting\n\n"
        'Line 3, column 23\n\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#compiler-settings\n'
        '2   |not_a_real_setting = True\n'
        '3   |#end compiler-settings\n'
        '                           ^\n',

        '#compiler-settings\n'
        'not_a_real_setting = True\n'
        '#end compiler-settings\n',
    )


def test_errors_on_blinged_kwarg():
    assert_parse_error(
        '\n\n'
        "SyntaxError: keyword can't be an expression (<unknown>, line 1)\n\n"
        'Line 1, column 15\n\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |$foo($bar=$baz)\n'
        '                   ^\n',

        '$foo($bar=$baz)',
    )


def test_weird_def_parsing():
    assert_parse_error(
        '\n\n'
        "EOF while searching for ')' (to match '(')\n"
        'Line 1, column 9\n\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#def foo(x,#\n'
        '             ^\n'
        '2   |#end def\n',

        '#def foo(x,#\n'
        '#end def\n',
    )


def test_no_cheetah_vars_in_def():
    assert_parse_error(
        '\n\n'
        'Invalid Syntax\n'
        'Line 1, column 13\n\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#def foo(x=($y)):\n'
        '                 ^\n'
        '2   |#end def\n',

        '#def foo(x=($y)):\n'
        '#end def\n',
    )


def test_junk_after_decorator():
    assert_parse_error(
        '\n\n'
        'Expected #def, #block or another @decorator\n'
        'Line 2, column 1\n\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#@dec\n'
        '2   |junk\n'
        '     ^\n'
        '3   |#def foo(): hi\n',

        '#@dec\n'
        'junk\n'
        '#def foo(): hi\n'
    )


@pytest.mark.parametrize('placeholder', ('$(x)', '$[x]'))
def test_old_placeholders(placeholder):
    assert_parse_error(
        '\n\n'
        'Invalid placeholder.  Valid placeholders are $x or ${{x}}.\n'
        'Line 1, column 1\n\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |{}\n'
        '     ^\n'.format(placeholder),

        placeholder,
    )
