import pytest

from Cheetah.Parser import ArgList


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

    assert arglist.merge() == [(u'a', u'999'), (u'b', u'444')]


def test_merge3(arglist):
    """Testing the ArgList case results
    from SyntaxAndOutput.BlockDirective.test13
    """
    arglist.add_argument('arg')
    arglist.add_default("'This is my block'")
    assert arglist.merge() == [('arg', "'This is my block'")]
