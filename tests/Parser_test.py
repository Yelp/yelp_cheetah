from __future__ import absolute_import
from __future__ import unicode_literals

import pytest

from Cheetah.compile import compile_to_class
from Cheetah.Parser import ArgList
from Cheetah.Parser import UnknownDirectiveError
from Cheetah.Parser import ParseError
from testing.util import assert_raises_exactly


@pytest.yield_fixture
def arglist():
    yield ArgList()


def test_ArgList_merge1(arglist):
    """Testing the ArgList case results from
    Template.Preprocessors.test_complexUsage
    """
    arglist.add_argument('arg')
    assert arglist.merge() == [('arg', None)]


def test_ArgList_merge2(arglist):
    """Testing the ArgList case results from
    SyntaxAndOutput.BlockDirective.test4
    """
    arglist.add_argument('a')
    arglist.add_default('999')
    arglist.next()
    arglist.add_argument('b')
    arglist.add_default('444')

    assert arglist.merge() == [('a', '999'), ('b', '444')]


def test_merge3(arglist):
    """Testing the ArgList case results
    from SyntaxAndOutput.BlockDirective.test13
    """
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
