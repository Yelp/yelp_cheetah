# -*- coding: UTF-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

from Cheetah.compile import compile_to_class
from Cheetah.legacy_parser import ArgList
from Cheetah.legacy_parser import UnknownDirectiveError
from Cheetah.legacy_parser import ParseError
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


def test_unknown_macro_name():
    with assert_raises_exactly(
        UnknownDirectiveError,
        '\n\n'
        'Bad macro name: "foo". You may want to escape that # sign?\n'
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
        'Line 1, column 18\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#attr $foo = $bar\n'
        '                      ^\n'
    ):
        compile_to_class('#attr $foo = $bar\n')


def test_invalid_line_continuation():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'Line ending expected\n'
        'Line 1, column 21\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#set foo = "bar" + \\hi, not a new line\n'
        '                         ^\n'
    ):
        compile_to_class('#set foo = "bar" + \\hi, not a new line')


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


def test_filter_with_variable():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        "Filters should be in the filterLib\n"
        'Line 1, column 9\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#filter $MyFilter\n'
        '             ^\n'
    ):
        compile_to_class('#filter $MyFilter')


def test_non_ending_compiler_settings():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        "Unexpected EOF while searching for #end compiler-settings\n"
        'Line 2, column 24\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#compiler-settings\n'
        '2   |useDottedNotation = True\n'
        '                            ^\n'
    ):
        compile_to_class('#compiler-settings\nuseDottedNotation = True')


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


def test_malformed_compiler_settings():
    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'An error occurred while parsing the settings:\n'
        '---------------------------------------------\n'
        '==\n'
        '---------------------------------------------\n'
        'Line 3, column 23\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#compiler-settings\n'
        '2   |==\n'
        '3   |#end compiler-settings\n'
        '                           ^\n'
    ):
        compile_to_class(
            '#compiler-settings\n'
            '==\n'
            '#end compiler-settings\n'
        )


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
        'lvalue of #set cannot contain `$`\n'
        'Line 1, column 6\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#set $foo = 1\n'
        '          ^\n'
    ):
        compile_to_class('#set $foo = 1\n')


def test_macros_with_arguments():
    def herp_macro(src, foo):
        return src + foo  # pragma: no cover

    with assert_raises_exactly(
        ParseError,
        '\n\n'
        'Macro arguments must not contain a `$`\n'
        'Line 1, column 13\n'
        '\n'
        'Line|Cheetah Code\n'
        '----|-------------------------------------------------------------\n'
        '1   |#herp_macro $foo\n'
        '                 ^\n'
        '2   |src\n'
        '3   |#end herp_macro\n'
    ):
        compile_to_class(
            '#herp_macro $foo\n'
            'src\n'
            '#end herp_macro\n',
            settings={'macroDirectives': {'herp_macro': herp_macro}},
        )
