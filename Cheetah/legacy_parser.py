"""
Parser classes for Cheetah's LegacyCompiler

Classes:
  ParseError(Exception)
  _LowLevelParser(Cheetah.SourceReader.SourceReader), basically a lexer
  LegacyParser(_LowLevelParser)
"""
from __future__ import unicode_literals

import functools
import re
import string
import sys
from tokenize import PseudoToken

import six

from Cheetah.SourceReader import SourceReader

python_token_re = re.compile(PseudoToken)
identchars = string.ascii_letters + '_'
namechars = identchars + string.digits

single3 = "'''"
double3 = '"""'

tripleQuotedStringStarts = (
    "'''", '"""',
    "r'''", 'r"""', "R'''", 'R"""',
    "u'''", 'u"""', "U'''", 'U"""',
    "ur'''", 'ur"""', "Ur'''", 'Ur"""',
    "uR'''", 'uR"""', "UR'''", 'UR"""',
)

tripleQuotedStringPairs = {
    "'''": single3, '"""': double3,
    "r'''": single3, 'r"""': double3,
    "u'''": single3, 'u"""': double3,
    "ur'''": single3, 'ur"""': double3,
    "R'''": single3, 'R"""': double3,
    "U'''": single3, 'U"""': double3,
    "uR'''": single3, 'uR"""': double3,
    "Ur'''": single3, 'Ur"""': double3,
    "UR'''": single3, 'UR"""': double3,
}

closurePairs = {')': '(', ']': '[', '}': '{'}
closurePairsRev = {'(': ')', '[': ']', '{': '}'}


tripleQuotedStringREs = {}


def makeTripleQuoteRe(start, end):
    start = re.escape(start)
    end = re.escape(end)
    return re.compile(r'(?:' + start + r').*?' + r'(?:' + end + r')', re.DOTALL)

for start_part, end_part in tripleQuotedStringPairs.items():
    tripleQuotedStringREs[start_part] = makeTripleQuoteRe(start_part, end_part)

escCharLookBehind = r'(?:(?<=\A)|(?<!\\))'
identRE = re.compile(r'[a-zA-Z_][a-zA-Z_0-9]*')
directiveRE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_-]*|@[a-zA-Z_][a-zA-Z0-9_]*)')
EOLre = re.compile(r'(?:\r\n|\r|\n)')

escapedNewlineRE = re.compile(r'(?<!\\)((\\\\)*)\\(n|012)')

VAR_START = '$'
VAR_START_ESC = re.escape(VAR_START)
VAR_START_RE = re.compile(
    escCharLookBehind +
    r'(?P<startToken>' + VAR_START_ESC + ')' +
    r'(?P<enclosure>|(?:(?:\{|\(|\[)[ \t]*))' +  # allow WS after
    r'(?=[A-Za-z_])',
)
VAR_START_TOKEN_RE = re.compile(
    escCharLookBehind +
    VAR_START_ESC +
    r'(?=[A-Za-z_\*!\{\(\[])'
)
VAR_IN_EXPRESSION_START_TOKEN_RE = re.compile(
    VAR_START_ESC + r'(?=[A-Za-z_])'
)
EXPR_PLACEHOLDER_START_RE = re.compile(
    escCharLookBehind +
    r'(?P<startToken>' + VAR_START_ESC + ')' +
    r'(?:\{|\(|\[)[ \t]*'
    r'(?=[^\)\}\]])'
)
COMMENT_START_RE = re.compile(escCharLookBehind + re.escape('##'))
DIRECTIVE_START_RE = re.compile(
    escCharLookBehind + re.escape('#') + r'(?=[A-Za-z_@])',
)
DIRECTIVE_END_RE = re.compile(escCharLookBehind + re.escape('#'))


def _unescapeCheetahVars(s):
    r"""Unescape any escaped Cheetah \$vars in the string."""
    return s.replace('\\$', '$')


def _unescapeDirectives(s):
    """Unescape any escaped Cheetah directives in the string."""
    return s.replace('\\#', '#')


directiveNamesAndParsers = {
    # Python directives
    'import': None,
    'from': None,
    'super': 'eatSuper',
    'def': 'eatDef',
    '@': 'eatDecorator',
    'del': None,
    'if': None,
    'while': None,
    'for': None,
    'else': None,
    'elif': None,
    'pass': None,
    'break': None,
    'continue': None,
    'return': None,
    'yield': None,
    'with': None,
    'assert': None,
    'raise': None,
    'try': None,
    'except': None,
    'finally': None,

    # Cheetah extensions
    'compiler-settings': None,
    'extends': 'eatExtends',
    'implements': 'eatImplements',
    'slurp': 'eatSlurp',
    'py': None,
    'attr': 'eatAttr',
    'block': 'eatBlock',
    'end': 'eatEndDirective',
}

CLOSABLE_DIRECTIVES = frozenset({
    'block', 'compiler-settings', 'def', 'for', 'if', 'try', 'while', 'with',
})
INDENTING_DIRECTIVES = frozenset({
    'compiler-settings', 'else', 'elif', 'except', 'finally', 'for', 'if',
    'try', 'while', 'with',
})
EXPRESSION_DIRECTIVES = frozenset({
    'assert', 'break', 'continue', 'del', 'from', 'import', 'pass', 'py',
    'raise', 'return', 'yield',
})


class ParseError(ValueError):
    def __init__(self, stream, msg='Invalid Syntax'):
        self.stream = stream
        if stream.pos() >= len(stream):
            stream.setPos(len(stream) - 1)
        self.msg = msg

    def __str__(self):
        stream = self.stream
        report = ''
        row, col, line = self.stream.getRowColLine()

        # get the surrounding lines
        lines = stream._srcLines
        prevLines = []                  # (rowNum, content)
        for i in range(1, 4):
            if row - 1 - i < 0:
                break
            prevLines.append((row - i, lines[row - 1 - i]))

        nextLines = []                  # (rowNum, content)
        for i in range(1, 4):
            if row - 1 + i >= len(lines):
                break
            nextLines.append((row + i, lines[row - 1 + i]))
        nextLines.reverse()

        # print the main message
        report += "\n\n%s\n" % self.msg
        report += "Line %i, column %i\n\n" % (row, col)
        report += 'Line|Cheetah Code\n'
        report += '----|-------------------------------------------------------------\n'
        while prevLines:
            lineInfo = prevLines.pop()
            report += "%(row)-4d|%(line)s\n" % {'row': lineInfo[0], 'line': lineInfo[1]}
        report += "%(row)-4d|%(line)s\n" % {'row': row, 'line': line}
        report += ' ' * 5 + ' ' * (col - 1) + "^\n"

        while nextLines:
            lineInfo = nextLines.pop()
            report += "%(row)-4d|%(line)s\n" % {'row': lineInfo[0], 'line': lineInfo[1]}

        return report


def fail_with_our_parse_error(func):
    @functools.wraps(func)
    def inner(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except ParseError:
            raise
        except Exception as e:
            six.reraise(
                ParseError,
                ParseError(
                    self,
                    '{}: {}\n'.format(type(e).__name__, e)
                ),
                sys.exc_info()[2]
            )
    return inner


class UnknownDirectiveError(ParseError):
    pass


class ArgList(object):
    """Used by _LowLevelParser.getArgList()"""

    def __init__(self):
        self.arguments = []
        self.defaults = []
        self.count = 0

    def add_argument(self, name):
        self.arguments.append(name)
        self.defaults.append(None)

    def next(self):
        self.count += 1

    def add_default(self, token):
        count = self.count
        if self.defaults[count] is None:
            self.defaults[count] = ''
        self.defaults[count] += token

    def merge(self):
        defaults = (isinstance(d, six.text_type) and d.strip() or None for d in self.defaults)
        return list(six.moves.zip_longest((a.strip() for a in self.arguments), defaults))


class _LowLevelParser(SourceReader):
    """This class implements the methods to match or extract ('get*') the basic
    elements of Cheetah's grammar.  It does NOT handle any code generation or
    state management.
    """

    def matchTopLevelToken(self):
        """Returns the first match found from the following methods:
            self.matchCommentStartToken
            self.matchVariablePlaceholderStart
            self.matchExpressionPlaceholderStart
            self.matchDirective

        Returns None if no match.
        """
        match = None
        if self.peek() in '#$':
            for matcher in (
                    self.matchCommentStartToken,
                    self.matchVariablePlaceholderStart,
                    self.matchExpressionPlaceholderStart,
                    self.matchDirective,
            ):
                match = matcher()
                if match:
                    break
        return match

    def matchPyToken(self):
        match = python_token_re.match(self.src(), self.pos())

        if match and match.group() in tripleQuotedStringStarts:
            TQSmatch = tripleQuotedStringREs[match.group()].match(self.src(), self.pos())
            if TQSmatch:
                return TQSmatch
        return match

    def getPyToken(self):
        match = self.matchPyToken()
        if match is None:
            raise ParseError(self)
        elif match.group() in tripleQuotedStringStarts:
            raise ParseError(self, msg='Malformed triple-quoted string')
        return self.readTo(match.end())

    def matchCommentStartToken(self):
        return COMMENT_START_RE.match(self.src(), self.pos())

    def getCommentStartToken(self):
        match = self.matchCommentStartToken()
        return self.readTo(match.end())

    def getDottedName(self):
        srcLen = len(self)
        nameChunks = []

        assert self.peek() in identchars

        while self.pos() < srcLen:
            c = self.peek()
            if c in namechars:
                nameChunk = self.getIdentifier()
                nameChunks.append(nameChunk)
            elif c == '.':
                if self.pos() + 1 < srcLen and self.peek(1) in identchars:
                    nameChunks.append(self.getc())
                else:
                    break
            else:
                break

        return ''.join(nameChunks)

    def matchIdentifier(self):
        return identRE.match(self.src(), self.pos())

    def getIdentifier(self):
        match = self.matchIdentifier()
        if not match:
            raise ParseError(self, 'Invalid identifier')
        return self.readTo(match.end())

    def matchDirective(self):
        """Returns False or the name of the directive matched."""
        startPos = self.pos()
        if not self.matchDirectiveStartToken():
            return False
        self.getDirectiveStartToken()
        directiveName = self.matchDirectiveName()
        self.setPos(startPos)
        return directiveName

    def matchDirectiveName(self):
        directive_match = directiveRE.match(self.src(), self.pos())
        # There is a case where something looks like a decorator but actually
        # isn't a decorator.  The parsing for this is particularly wonky
        if directive_match is None:
            return None

        match_text = directive_match.group(0)

        # #@ is the "directive" for decorators
        if match_text.startswith('@'):
            return '@'
        elif match_text in self._directiveNamesAndParsers:
            return match_text
        else:
            raise UnknownDirectiveError(
                self,
                'Bad directive name: "{}". '
                'You may want to escape that # sign?'.format(match_text),
            )

    def matchDirectiveStartToken(self):
        return DIRECTIVE_START_RE.match(self.src(), self.pos())

    def getDirectiveStartToken(self):
        match = self.matchDirectiveStartToken()
        return self.readTo(match.end())

    def matchDirectiveEndToken(self):
        return DIRECTIVE_END_RE.match(self.src(), self.pos())

    def getDirectiveEndToken(self):
        match = self.matchDirectiveEndToken()
        return self.readTo(match.end())

    def matchColonForSingleLineShortFormDirective(self):
        if not self.atEnd() and self.peek() == ':':
            restOfLine = self[self.pos() + 1:self.findEOL()]
            restOfLine = restOfLine.strip()
            if not restOfLine:
                return False
            elif COMMENT_START_RE.match(restOfLine):
                return False
            else:  # non-whitespace, non-commment chars found
                return True
        return False

    def matchCheetahVarStart(self):
        """includes the enclosure"""
        return VAR_START_RE.match(self.src(), self.pos())

    def matchCheetahVarStartToken(self):
        """includes the enclosure"""
        return VAR_START_TOKEN_RE.match(self.src(), self.pos())

    def matchCheetahVarInExpressionStartToken(self):
        """no enclosures"""
        return VAR_IN_EXPRESSION_START_TOKEN_RE.match(self.src(), self.pos())

    def matchVariablePlaceholderStart(self):
        """includes the enclosure"""
        return VAR_START_RE.match(self.src(), self.pos())

    def matchExpressionPlaceholderStart(self):
        """includes the enclosure"""
        return EXPR_PLACEHOLDER_START_RE.match(self.src(), self.pos())

    def getCheetahVarStartToken(self):
        """just the start token, not the enclosure"""
        match = self.matchCheetahVarStartToken()
        return self.readTo(match.end())

    def getCheetahVar(self):
        """This is called when parsing inside expressions."""
        self.getCheetahVarStartToken()
        lineCol = self.getRowCol()
        return self._compiler.genCheetahVar(self.getCheetahVarNameChunks(), lineCol)

    def getCheetahVarNameChunks(self):
        """nameChunks = list of Cheetah $var subcomponents represented as tuples
          [(namemapperPart, restOfName), ...]
        where:
          namemapperPart = the dottedName base
          restOfName = any arglist, index, or slice

        EXAMPLE
        ------------------------------------------------------------------------

        if the raw CheetahVar is
          $a.b.c[1].d().x.y.z

        nameChunks is the list
            [
                ('a.b.c', '[1]'),
                ('d', '()'),
                ('x.y.z', ''),
            ]

        """
        # TODO: this can just partition the first bit and the last bit
        chunks = []
        while self.pos() < len(self):
            rest = ''
            if not self.peek() in identchars + '.':
                break
            elif self.peek() == '.':
                if self.pos() + 1 < len(self) and self.peek(1) in identchars:
                    self.advance()  # discard the period as it isn't needed with NameMapper
                else:
                    break

            dottedName = self.getDottedName()
            if not self.atEnd() and self.peek() in '([':
                while not self.atEnd() and self.peek() in '([':
                    if self.peek() == '(':
                        rest += self.getCallArgString()
                    else:
                        rest += self.getExpression(enclosed=True)

                period = max(dottedName.rfind('.'), 0)
                if period:
                    chunks.append((dottedName[:period], ''))
                    dottedName = dottedName[period + 1:]
            chunks.append((dottedName, rest))

        return chunks

    def getCallArgString(self):
        """Get a method/function call argument string.

        This method understands *arg, and **kw
        """
        assert self.peek() == '('
        startPos = self.pos()
        self.getc()
        enclosures = [('(', startPos)]

        argStringBits = ['(']
        addBit = argStringBits.append

        while True:
            if self.atEnd():
                open = enclosures[-1][0]
                close = closurePairsRev[open]
                self.setPos(enclosures[-1][1])
                raise ParseError(
                    self, msg="EOF was reached before a matching '" + close +
                    "' was found for the '" + open + "'")

            c = self.peek()
            if c in ')}]':  # get the ending enclosure and break
                assert enclosures
                c = self.getc()
                open = closurePairs[c]
                if enclosures[-1][0] == open:
                    enclosures.pop()
                    addBit(')')
                    break
                else:
                    raise ParseError(
                        self,
                        "Expected a '{}' before an end '{}'".format(
                            closurePairsRev[enclosures[-1][0]], c,
                        )
                    )
            elif c in ' \t\r\n':
                addBit(self.getc())
            elif self.matchCheetahVarInExpressionStartToken():
                startPos = self.pos()
                codeFor1stToken = self.getCheetahVar()
                whitespace = self.getWhiteSpace()
                if not self.atEnd() and self.peek() == '=':
                    nextToken = self.getPyToken()
                    if nextToken == '=':
                        # when nextToken is `=` we know this is a kwarg and
                        # not an inline expression, so we can crash
                        self.setPos(startPos)
                        raise ParseError(self, 'kwargs should not start with $')

                    addBit(codeFor1stToken + whitespace + nextToken)
                else:
                    addBit(codeFor1stToken + whitespace)
            elif self.matchCheetahVarStart():
                # it has syntax that is only valid at the top level
                self._raiseErrorAboutInvalidCheetahVarSyntaxInExpr()
            elif self.peek() in ('{', '(', '['):
                addBit(self.getExpression(enclosed=True))
            else:
                addBit(self.getPyToken())

        return ''.join(argStringBits)

    def getDefArgList(self):
        """Get an argument list. Can be used for method/function definition
        argument lists or for # directive argument lists. Returns a list of
        tuples in the form (argName, defVal=None) with one tuple for each arg
        name.

        These defVals are always strings, so (argName, defVal=None) is safe even
        with a case like (arg1, arg2=None, arg3=1234*2), which would be returned as
        [
            ('arg1', None),
            ('arg2', 'None'),
            ('arg3', '1234*2'),
        ]

        This method understands *arg, and **kw
        """
        assert self.peek() == '('
        self.advance()
        argList = ArgList()
        onDefVal = False

        while True:
            if self.atEnd():
                raise ParseError(
                    self, msg="EOF was reached before a matching ')'" +
                    " was found for the '('")

            c = self.peek()
            if c == ")" or self.matchDirectiveEndToken():
                break
            elif c in " \t\r\n":
                if onDefVal:
                    argList.add_default(c)
                self.advance()
            elif c == '=':
                onDefVal = True
                self.advance()
            elif c == ",":
                argList.next()
                onDefVal = False
                self.advance()
            elif self.startswith(VAR_START):
                raise ParseError(self, '$ is not allowed here.')
            elif self.matchIdentifier() and not onDefVal:
                argList.add_argument(self.getIdentifier())
            elif onDefVal and c in ('{', '(', '['):
                argList.add_default(self.getExpression(enclosed=True))
            elif onDefVal:
                argList.add_default(self.getPyToken())
            elif c == '*' and not onDefVal:
                varName = self.getc()
                if self.peek() == '*':
                    varName += self.getc()
                if not self.matchIdentifier():
                    raise ParseError(self, 'Expected an identifier.')
                varName += self.getIdentifier()
                argList.add_argument(varName)
            else:
                raise ParseError(self, 'Unexpected character.')

        return argList.merge()

    def getExpressionParts(
            self,
            enclosed=False,
            enclosures=None,  # list of tuples (char, pos), where char is ({ or [
            pyTokensToBreakAt=None,  # only works if not enclosed
    ):
        """Get a Cheetah expression that includes $CheetahVars and break at
        directive end tokens, the end of an enclosure, or at a specified
        pyToken.
        """
        if enclosures is None:
            enclosures = []

        srcLen = len(self)
        exprBits = []
        while True:
            if self.atEnd():
                if enclosures:
                    open = enclosures[-1][0]
                    close = closurePairsRev[open]
                    self.setPos(enclosures[-1][1])
                    raise ParseError(
                        self, msg="EOF was reached before a matching '" + close +
                        "' was found for the '" + open + "'")
                else:
                    break

            c = self.peek()
            if c in "{([":
                exprBits.append(c)
                enclosures.append((c, self.pos()))
                self.advance()
            elif enclosed and not enclosures:
                break
            elif c in "])}":
                assert enclosures
                open = closurePairs[c]
                if enclosures[-1][0] == open:
                    enclosures.pop()
                    exprBits.append(c)
                else:
                    open = enclosures[-1][0]
                    close = closurePairsRev[open]
                    row, col = self.getRowCol()
                    self.setPos(enclosures[-1][1])
                    raise ParseError(
                        self, msg="A '" + c + "' was found at line " + str(row) +
                        ", col " + str(col) +
                        " before a matching '" + close +
                        "' was found for the '" + open + "'")
                self.advance()

            elif c in " \t":
                exprBits.append(self.getWhiteSpace())
            elif self.matchDirectiveEndToken() and not enclosures:
                break
            elif c == "\\" and self.pos() + 1 < srcLen:
                eolMatch = EOLre.match(self.src(), self.pos() + 1)
                if not eolMatch:
                    self.advance()
                    raise ParseError(self, msg='Line ending expected')
                self.setPos(eolMatch.end())
            elif c in '\r\n':
                if enclosures:
                    self.advance()
                else:
                    break
            elif self.matchCheetahVarInExpressionStartToken():
                expr = self.getCheetahVar()
                exprBits.append(expr)
            elif self.matchCheetahVarStart():
                # it has syntax that is only valid at the top level
                self._raiseErrorAboutInvalidCheetahVarSyntaxInExpr()
            else:
                beforeTokenPos = self.pos()
                token = self.getPyToken()
                if (
                        not enclosures and
                        pyTokensToBreakAt and
                        token in pyTokensToBreakAt
                ):
                    self.setPos(beforeTokenPos)
                    break

                exprBits.append(token)
                if identRE.match(token):
                    if token == 'for':
                        exprBits.append(self.getWhiteSpace())
                        expr = self.get_python_expression(
                            'lvalue of for must not contain a `$`',
                            pyTokensToBreakAt=['in'],
                        )
                        exprBits.append(expr)
                    else:
                        exprBits.append(self.getWhiteSpace())
                        if not self.atEnd() and self.peek() == '(':
                            exprBits.append(self.getCallArgString())
        return exprBits

    def getExpression(
            self,
            enclosed=False,
            enclosures=None,  # list of tuples (char, pos), where # char is ({ or [
            pyTokensToBreakAt=None,
    ):
        """Returns the output of self.getExpressionParts() as a concatenated
        string rather than as a list.
        """
        return ''.join(self.getExpressionParts(
            enclosed=enclosed,
            enclosures=enclosures,
            pyTokensToBreakAt=pyTokensToBreakAt,
        ))

    def get_python_expression(self, failure_msg, **kwargs):
        """Get an expression that should not contain cheetah variables.
        Raises a ParseError with `failure_msg` on failure.
        """
        expr_pos = self.pos()
        expr = self.getExpression(**kwargs)
        if 'VFFSL(' in expr:
            self.setPos(expr_pos)
            raise ParseError(self, failure_msg)
        return expr

    def _raiseErrorAboutInvalidCheetahVarSyntaxInExpr(self):
        match = self.matchCheetahVarStart()
        groupdict = match.groupdict()
        assert 'enclosure' in groupdict, groupdict
        raise ParseError(
            self,
            'Long-form placeholders - ${}, $(), $[], etc. are not valid inside expressions. '
            'Use them in top-level $placeholders only.'
        )

    def getPlaceholder(self):
        startPos = self.pos()
        lineCol = self.getRowCol()
        self.getCheetahVarStartToken()

        if self.peek() in '({[':
            pos = self.pos()
            enclosureOpenChar = self.getc()
            enclosures = [(enclosureOpenChar, pos)]
            self.getWhiteSpace()
        else:
            enclosures = []

        if self.matchIdentifier():
            nameChunks = self.getCheetahVarNameChunks()
            expr = self._compiler.genCheetahVar(nameChunks[:], lineCol)
            restOfExpr = None
            if enclosures:
                whitespace = self.getWhiteSpace()
                expr += whitespace
                if self.peek() == closurePairsRev[enclosureOpenChar]:
                    self.getc()
                else:
                    restOfExpr = self.getExpression(enclosed=True, enclosures=enclosures)
                    assert restOfExpr[-1] == closurePairsRev[enclosureOpenChar]
                    restOfExpr = restOfExpr[:-1]
                    expr += restOfExpr
            rawPlaceholder = self[startPos:self.pos()]
        else:
            expr = self.getExpression(enclosed=True, enclosures=enclosures)
            assert expr[-1] == closurePairsRev[enclosureOpenChar]
            expr = expr[:-1]
            rawPlaceholder = self[startPos:self.pos()]

        return expr, rawPlaceholder, lineCol


class LegacyParser(_LowLevelParser):
    """This class is a StateMachine for parsing Cheetah source and
    sending state dependent code generation commands to
    Cheetah.legacy_compiler.LegacyCompiler
    """

    def __init__(self, src, compiler):
        super(LegacyParser, self).__init__(src)
        self._compiler = compiler
        self._openDirectivesStack = []

        self._directiveNamesAndParsers = {
            name: getattr(self, val) if val is not None else None
            for name, val in directiveNamesAndParsers.items()
        }

    @fail_with_our_parse_error
    def parse(self, breakPoint=None, assertEmptyStack=True):
        if breakPoint:
            origBP = self.breakPoint()
            self.setBreakPoint(breakPoint)
            assertEmptyStack = False

        while not self.atEnd():
            if self.matchCommentStartToken():
                self.eatComment()
            elif self.matchVariablePlaceholderStart():
                self.eatPlaceholder()
            elif self.matchExpressionPlaceholderStart():
                self.eatPlaceholder()
            elif self.matchDirective():
                self.eatDirective()
            else:
                self.eatPlainText()
        if assertEmptyStack:
            self.assertEmptyOpenDirectivesStack()
        if breakPoint:
            self.setBreakPoint(origBP)

    # non-directive eat methods

    def eatPlainText(self):
        start = self.pos()
        while not self.atEnd() and not self.matchTopLevelToken():
            self.advance()
        text = self.readTo(self.pos(), start=start)
        text = _unescapeDirectives(_unescapeCheetahVars(text))
        self._compiler.addStrConst(text)

    def eatComment(self):
        isLineClearToStartToken = self.isLineClearToStartToken()
        if isLineClearToStartToken:
            self._compiler.handleWSBeforeDirective()
        self.getCommentStartToken()
        comm = self.readToEOL(gobble=isLineClearToStartToken)
        self._compiler.addComment(comm)

    def eatPlaceholder(self):
        self._compiler.addPlaceholder(*self.getPlaceholder())

    def eatDirective(self):
        directive = self.matchDirective()

        # subclasses can override the default behaviours here by providing an
        # eater method in self._directiveNamesAndParsers[directive]
        directiveParser = self._directiveNamesAndParsers.get(directive)
        if directiveParser:
            directiveParser()
        else:
            if directive == 'compiler-settings':
                def handler(*_):
                    pass
            else:
                handler = getattr(self._compiler, 'add' + directive.capitalize())

            if directive in INDENTING_DIRECTIVES:
                self.eatSimpleIndentingDirective(directive, callback=handler)
            else:
                assert directive in EXPRESSION_DIRECTIVES
                line_col = self.getRowCol()
                include_name = directive != 'py'
                expr = self.eatSimpleExprDirective(
                    directive, include_name=include_name,
                )
                handler(expr, line_col=line_col)

    def _eatRestOfDirectiveTag(self, isLineClearToStartToken, endOfFirstLinePos):
        foundComment = False
        # There's a potential ambiguity when parsing comments on directived
        # lines.
        # The difficult thing to differentiate is between the following
        # cases:
        # 1. #if foo:##end if#
        # Here, the part that begins with ## is matched as a comment but is
        # actually a directive
        # 2. #if foo: ##comment
        # Here it is actually a comment, but (potentially) ParseErrors as a
        # missing directive.
        if self.matchCommentStartToken():
            pos = self.pos()
            self.advance()

            try:
                matched_directive = self.matchDirective()
            except UnknownDirectiveError:
                matched_directive = False

            if not matched_directive:
                self.setPos(pos)
                foundComment = True
                self.eatComment()  # this won't gobble the EOL
            else:
                self.setPos(pos)

        if not foundComment and self.matchDirectiveEndToken():
            self.getDirectiveEndToken()
        elif isLineClearToStartToken and (not self.atEnd()) and self.peek() in '\r\n':
            # still gobble the EOL if a comment was found.
            self.readToEOL(gobble=True)

        if isLineClearToStartToken and (self.atEnd() or self.pos() > endOfFirstLinePos):
            self._compiler.handleWSBeforeDirective()

    def eatSimpleExprDirective(self, directive, include_name=True):
        isLineClearToStartToken = self.isLineClearToStartToken()
        endOfFirstLine = self.findEOL()
        self.getDirectiveStartToken()
        if not include_name:
            self.advance(len(directive))
        expr = self.getExpression().strip()
        self._eatRestOfDirectiveTag(isLineClearToStartToken, endOfFirstLine)
        return expr

    def eatSimpleIndentingDirective(self, directiveName, callback):
        isLineClearToStartToken = self.isLineClearToStartToken()
        endOfFirstLinePos = self.findEOL()
        lineCol = self.getRowCol()
        self.getDirectiveStartToken()
        self.getWhiteSpace()

        expr = self.getExpression(pyTokensToBreakAt=[':'])
        if self.matchColonForSingleLineShortFormDirective():
            self.advance()  # skip over :
            if directiveName in 'else elif except finally'.split():
                callback(expr, lineCol, dedent=False)
            else:
                callback(expr, lineCol)

            self.getWhiteSpace(maximum=1)
            self.parse(breakPoint=self.findEOL(gobble=True))
            self._compiler.commitStrConst()
            self._compiler.dedent()
        else:
            if self.peek() == ':':
                self.advance()
            self.getWhiteSpace()
            self._eatRestOfDirectiveTag(isLineClearToStartToken, endOfFirstLinePos)
            if directiveName in CLOSABLE_DIRECTIVES:
                self.pushToOpenDirectivesStack(directiveName)
            callback(expr, lineCol)

    def eatEndDirective(self):
        isLineClearToStartToken = self.isLineClearToStartToken()
        self.getDirectiveStartToken()
        self.advance(len('end'))
        self.getWhiteSpace()
        pos = self.pos()
        directiveName = False
        for key in CLOSABLE_DIRECTIVES:
            if self.find(key, pos) == pos:
                directiveName = key
                break
        if not directiveName:
            raise ParseError(self, msg='Invalid end directive')

        endOfFirstLinePos = self.findEOL()
        self.getExpression()  # eat in any extra comment-like crap
        self._eatRestOfDirectiveTag(isLineClearToStartToken, endOfFirstLinePos)
        assert directiveName in CLOSABLE_DIRECTIVES
        self.popFromOpenDirectivesStack(directiveName)

        if directiveName == 'def':
            self._compiler.closeDef()
        elif directiveName == 'compiler-settings':
            self._compiler.add_compiler_settings()
        elif directiveName == 'block':
            self._compiler.closeBlock()
        else:
            assert directiveName in {'while', 'for', 'if', 'try', 'with'}
            self._compiler.commitStrConst()
            self._compiler.dedent()

    # specific directive eat methods
    def eatAttr(self):
        isLineClearToStartToken = self.isLineClearToStartToken()
        endOfFirstLinePos = self.findEOL()
        self.getDirectiveStartToken()
        self.advance(len('attr'))
        self.getWhiteSpace()
        if self.matchCheetahVarStart():
            raise ParseError(self, '#attr directive must not contain `$`')
        attribName = self.getIdentifier()
        self.getWhiteSpace()
        assert self.peek() == '='
        self.getc()
        self.getWhiteSpace()
        expr = self.get_python_expression(
            'Invalid #attr directive. '
            'It should contain simple Python literals.'
        )
        self._compiler.addAttribute(attribName + ' = ' + expr)
        self._eatRestOfDirectiveTag(isLineClearToStartToken, endOfFirstLinePos)

    def eatDecorator(self):
        isLineClearToStartToken = self.isLineClearToStartToken()
        endOfFirstLinePos = self.findEOL()
        self.getDirectiveStartToken()
        decorator_expr = self.getExpression()
        if decorator_expr in ('@classmethod', '@staticmethod'):
            self.setPos(self.pos() - len(decorator_expr))
            raise ParseError(
                self, '@classmethod / @staticmethod are not supported',
            )
        self._compiler.addDecorator(decorator_expr)
        self._eatRestOfDirectiveTag(isLineClearToStartToken, endOfFirstLinePos)
        self.getWhiteSpace()

        directiveName = self.matchDirective()
        if not directiveName or directiveName not in ('def', 'block', '@'):
            raise ParseError(
                self, 'Expected #def, #block or another @decorator',
            )

    def eatDef(self):
        self._eatDefOrBlock('def')

    def eatBlock(self):
        self._eatDefOrBlock('block')

    def _eatDefOrBlock(self, directiveName):
        assert directiveName in ('def', 'block')
        isLineClearToStartToken = self.isLineClearToStartToken()
        endOfFirstLinePos = self.findEOL()
        startPos = self.pos()
        self.getDirectiveStartToken()
        self.advance(len(directiveName))
        self.getWhiteSpace()
        if self.matchCheetahVarStart():
            raise ParseError(self, 'use #def func() instead of #def $func()')
        methodName = self.getIdentifier()
        self.getWhiteSpace()

        if directiveName == 'block' and self.peek() == '(':
            raise ParseError(
                self, '#block must not have an argspec, did you mean #def?',
            )

        if directiveName == 'def' and self.peek() != '(':
            raise ParseError(self, '#def must contain an argspec (at least ())')

        if directiveName == 'def':
            arglist_position = self.pos()
            argsList = self.getDefArgList()
            self.advance()  # Past closing ')'
            if argsList and argsList[0][0] == 'self':
                # So the exception points at the right place
                self.setPos(arglist_position + 1)
                raise ParseError(
                    self,
                    'Do not specify `self` in an arglist, it is assumed',
                )
        else:
            argsList = []

        if self.matchColonForSingleLineShortFormDirective():
            self.getc()
            self._eatSingleLineDef(
                methodName=methodName,
                argsList=argsList,
                startPos=startPos,
                endPos=endOfFirstLinePos,
            )
            if directiveName == 'def':
                # @@TR: must come before _eatRestOfDirectiveTag ... for some reason
                self._compiler.closeDef()
            else:
                self._compiler.closeBlock()

            self._eatRestOfDirectiveTag(isLineClearToStartToken, endOfFirstLinePos)
        else:
            if self.peek() == ':':
                self.getc()
            self.pushToOpenDirectivesStack(directiveName)
            self._eatMultiLineDef(
                methodName=methodName,
                argsList=argsList,
                startPos=startPos,
                isLineClearToStartToken=isLineClearToStartToken,
            )

    def _eatMultiLineDef(self, methodName, argsList, startPos, isLineClearToStartToken=False):
        self.getExpression()  # slurp up any garbage left at the end
        signature = self[startPos:self.pos()]
        endOfFirstLinePos = self.findEOL()
        self._eatRestOfDirectiveTag(isLineClearToStartToken, endOfFirstLinePos)
        signature = ' '.join([line.strip() for line in signature.splitlines()])
        parserComment = ('## CHEETAH: generated from ' + signature +
                         ' at line %s, col %s' % self.getRowCol(startPos) +
                         '.')

        self._compiler.startMethodDef(methodName, argsList, parserComment)

    def _eatSingleLineDef(self, methodName, argsList, startPos, endPos):
        fullSignature = self[startPos:endPos]
        parserComment = ('## Generated from ' + fullSignature +
                         ' at line %s, col %s' % self.getRowCol(startPos) +
                         '.')
        self._compiler.startMethodDef(methodName, argsList, parserComment)

        self.getWhiteSpace(maximum=1)
        self.parse(breakPoint=endPos)

    def eatExtends(self):
        isLineClearToStartToken = self.isLineClearToStartToken()
        endOfFirstLine = self.findEOL()
        self.getDirectiveStartToken()
        self.advance(len('extends'))
        self.getWhiteSpace()
        extends_value = self.readToEOL(gobble=False)

        if ',' in extends_value:
            raise ParseError(
                self, 'yelp_cheetah does not support multiple inheritance'
            )

        self._compiler.set_extends(extends_value)
        self._eatRestOfDirectiveTag(isLineClearToStartToken, endOfFirstLine)

    def eatImplements(self):
        isLineClearToStartToken = self.isLineClearToStartToken()
        endOfFirstLine = self.findEOL()
        self.getDirectiveStartToken()
        self.advance(len('implements'))
        self.getWhiteSpace()
        methodName = self.getIdentifier()
        if not self.atEnd() and self.peek() == '(':
            raise ParseError(
                self, 'yelp_cheetah does not support argspecs for #implements',
            )
        self._compiler.setMainMethodName(methodName)

        self.getExpression()  # throw away and unwanted crap that got added in
        self._eatRestOfDirectiveTag(isLineClearToStartToken, endOfFirstLine)

    def eatSuper(self):
        isLineClearToStartToken = self.isLineClearToStartToken()
        endOfFirstLine = self.findEOL()
        self.getDirectiveStartToken()
        self.advance(len('super'))
        self.getWhiteSpace()
        if not self.atEnd() and self.peek() == '(':
            argsList = self.getDefArgList()
            self.advance()              # past the closing ')'
            if argsList and argsList[0][0] == 'self':
                del argsList[0]
        else:
            argsList = []

        self.getExpression()  # throw away and unwanted crap that got added in
        self._eatRestOfDirectiveTag(isLineClearToStartToken, endOfFirstLine)
        self._compiler.addSuper(argsList)

    def eatSlurp(self):
        if self.isLineClearToStartToken():
            self._compiler.handleWSBeforeDirective()
        self._compiler.commitStrConst()
        self.readToEOL(gobble=True)

    def pushToOpenDirectivesStack(self, directiveName):
        assert directiveName in CLOSABLE_DIRECTIVES
        self._openDirectivesStack.append(directiveName)

    def popFromOpenDirectivesStack(self, directive_name):
        if not self._openDirectivesStack:
            raise ParseError(self, msg="#end found, but nothing to end")

        last = self._openDirectivesStack.pop()
        if last != directive_name:
            raise ParseError(
                self,
                '#end {} found, expected #end {}'.format(directive_name, last)
            )

    def assertEmptyOpenDirectivesStack(self):
        if self._openDirectivesStack:
            errorMsg = (
                "Some #directives are missing their corresponding #end ___ tag: %s" % (
                    ', '.join(self._openDirectivesStack)))
            raise ParseError(self, msg=errorMsg)
