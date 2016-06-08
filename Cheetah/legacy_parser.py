"""
Parser classes for Cheetah's LegacyCompiler

Classes:
  ParseError(Exception)
  _LowLevelParser(Cheetah.SourceReader.SourceReader), basically a lexer
  LegacyParser(_LowLevelParser)
"""
from __future__ import unicode_literals

import collections
import functools
import re
import string
import sys
import tokenize

import six

from Cheetah.SourceReader import SourceReader

python_token_re = re.compile(tokenize.PseudoToken)
identchars = string.ascii_letters + '_'

triple_quoted_pairs = {k: k[-3:] for k in tokenize.triple_quoted}
triple_quoted_res = {
    k: re.compile('(?:{}).*?(?:{})'.format(k, v), re.DOTALL)
    for k, v in triple_quoted_pairs.items()
}

brace_pairs = {'(': ')', '[': ']', '{': '}'}

escape_lookbehind = r'(?:(?<=\A)|(?<!\\))'
identRE = re.compile(r'[a-zA-Z_][a-zA-Z_0-9]*')

IDENT = '[a-zA-Z_][a-zA-Z0-9_]*'

VAR_START = '$'
EXPRESSION_START_RE = re.compile(escape_lookbehind + r'\$[A-Za-z_{]')
OLD_EXPRESSION_START_RE = re.compile(escape_lookbehind + r'\$[([]')

ATTRIBUTE_RE = re.compile(r'\.{}'.format(IDENT))

COMMENT_START_RE = re.compile(escape_lookbehind + re.escape('##'))
DIRECTIVE_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_-]*|@{})'.format(IDENT))
DIRECTIVE_START_RE = re.compile(
    escape_lookbehind + re.escape('#') + r'(?=([A-Za-z_]|@[A-Za-z_]))',
)
DIRECTIVE_END_RE = re.compile(escape_lookbehind + re.escape('#'))


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


CheetahVar = collections.namedtuple('CheetahVar', ('name',))


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
                ParseError(self, '{}: {}\n'.format(type(e).__name__, e)),
                sys.exc_info()[2],
            )
    return inner


class UnknownDirectiveError(ParseError):
    pass


class _LowLevelParser(SourceReader):
    """This class implements the methods to match or extract ('get*') the basic
    elements of Cheetah's grammar.  It does NOT handle any code generation or
    state management.
    """

    def matchTopLevelToken(self):
        """Returns the first match found from the following methods:
            self.matchCommentStartToken
            self.matchExpressionPlaceholderStart
            self.matchDirective

        Returns None if no match.
        """
        for matcher in (
                self.matchCommentStartToken,
                self.match_old_expression_start,
                self.match_expression_start,
                self.matchDirective,
        ):
            match = matcher()
            if match:
                return match
        return None

    def getPyToken(self):
        match = python_token_re.match(self.src(), self.pos())

        if match and match.group() in triple_quoted_pairs:
            match = triple_quoted_res[match.group()].match(self.src(), self.pos())
            if not match:
                raise ParseError(self, msg='Malformed triple-quoted string')
        elif not match:
            raise ParseError(self)

        return self.readTo(match.end())

    def matchCommentStartToken(self):
        return COMMENT_START_RE.match(self.src(), self.pos())

    def getCommentStartToken(self):
        match = self.matchCommentStartToken()
        return self.readTo(match.end())

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
        match_text = DIRECTIVE_RE.match(self.src(), self.pos()).group(0)

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

    def _read_cheetah_variable(self):
        parts = [CheetahVar(self.getIdentifier())]

        # A cheetah variable could continue with an attribute, function call,
        # or getitem.
        while not self.atEnd():
            attr_match = ATTRIBUTE_RE.match(self.src(), self.pos())
            if attr_match:
                parts.append(self.readTo(attr_match.end()))
            elif self.peek() in '([':
                parts.extend(self._read_braced_expression())
            else:
                break
        return tuple(parts)

    def _read_braced_expression(self, allow_cheetah_vars=True, force_variable=False):
        """Returns a tuple of read parts.  The tuple is mixed strings and
        CheetahVars

        :param bool allow_cheetah_vars: Whether cheetah variables are legal in
            this expression.
        :param bool force_variable: For expressions like ${var}, should var
            be parsed as a cheetah variable?
        """
        start_pos = self.pos()
        token = self.getPyToken()
        assert token in '({[', token
        brace_stack = [token]
        parts = [token]

        while brace_stack:
            if self.atEnd():
                self.setPos(start_pos)
                raise ParseError(
                    self,
                    "EOF while searching for '{}' (to match '{}')".format(
                        brace_pairs[brace_stack[-1]],
                        brace_stack[-1],
                    )
                )

            if force_variable and self.peek() in identchars:
                parts.extend(self._read_cheetah_variable())
            elif allow_cheetah_vars and self.peek() == VAR_START:
                self.advance()
                parts.extend(self._read_cheetah_variable())
            elif force_variable and self.peek() in ' \t':
                raise ParseError(self, 'Expected identifier')
            elif self.peek() in ' \t':
                parts.append(self.getc())
            else:
                token = self.getPyToken()
                if token in '({[':
                    brace_stack.append(token)
                elif token in ')}]':
                    if brace_pairs[brace_stack[-1]] != token:
                        self.setPos(start_pos)
                        raise ParseError(
                            self,
                            'Mismatched token. '
                            "Found '{}' while searching for '{}'".format(
                                token, brace_pairs[brace_stack[-1]],
                            )
                        )
                    brace_stack.pop()
                parts.append(token)

            # force_variable is only true for the first identifier
            force_variable = False
        return tuple(parts)

    def get_unbraced_expression(self, allow_cheetah_vars=True, stop_chars=''):
        parts = []
        stop_chars += '\n#'

        while not self.atEnd():
            if self.peek() in '{([':
                parts.extend(self._read_braced_expression(
                    allow_cheetah_vars=allow_cheetah_vars,
                ))
            elif allow_cheetah_vars and self.peek() == VAR_START:
                self.advance()
                parts.extend(self._read_cheetah_variable())
            elif self.peek() in ' \t':
                parts.append(self.getc())
            elif self.peek() in stop_chars:
                break
            else:
                parts.append(self.getPyToken())

        return tuple(parts)

    def get_placeholder_expression(self):
        if self.peek() != '{':
            return self._read_cheetah_variable()
        else:
            expr = self._read_braced_expression(force_variable=True)
            assert expr[0] == '{' and expr[-1] == '}', expr
            return expr[1:-1]

    def match_old_expression_start(self):
        # No longer valid, just here for a parse error
        return OLD_EXPRESSION_START_RE.match(self.src(), self.pos())

    def match_expression_start(self):
        return EXPRESSION_START_RE.match(self.src(), self.pos())

    def get_def_argspec(self):
        """Returns python source for function arguments.

        For example:

            def foo(bar, baz, x={'womp'}):
                   ^ (parser is about to parse this)

        Will return "(bar, baz, x={'womp'})" and the parser state afterwards:

            def foo(bar, baz, x={'womp'}):
                                         ^ (parser is about to parse this)
        """
        assert self.peek() == '('
        expr = self._read_braced_expression(allow_cheetah_vars=False)
        assert expr[0] == '(' and expr[-1] == ')', expr
        return ''.join(expr[1:-1])


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
            elif self.match_old_expression_start():
                raise ParseError(
                    self,
                    'Invalid placeholder.  Valid placeholders are $x or ${x}.'
                )
            elif self.match_expression_start():
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
        text = text.replace('\\$', '$').replace('\\#', '#')
        self._compiler.addStrConst(text)

    def eatComment(self):
        isLineClearToStartToken = self.isLineClearToStartToken()
        if isLineClearToStartToken:
            self._compiler.handleWSBeforeDirective()
        self.getCommentStartToken()
        comm = self.readToEOL(gobble=isLineClearToStartToken)
        self._compiler.addComment(comm)

    def eatPlaceholder(self):
        start = self.pos()
        line_col = self.getRowCol()
        assert self.getc() == VAR_START
        expr = self.get_placeholder_expression()
        end = self.pos()
        original_src = self.src()[start:end]
        self._compiler.addPlaceholder(expr, original_src, line_col)

    def eatDirective(self):
        directive = self.matchDirective()

        # subclasses can override the default behaviours here by providing an
        # eater method in self._directiveNamesAndParsers[directive]
        directiveParser = self._directiveNamesAndParsers.get(directive)
        if directiveParser:
            directiveParser()
        else:
            if directive in INDENTING_DIRECTIVES:
                self.eatSimpleIndentingDirective(directive)
            else:
                assert directive in EXPRESSION_DIRECTIVES
                line_col = self.getRowCol()
                include_name = directive != 'py'
                expr = self.eatSimpleExprDirective(
                    directive, include_name=include_name,
                )
                self._add_directive(directive, expr, line_col)

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
        expr = self.get_unbraced_expression()
        self._eatRestOfDirectiveTag(isLineClearToStartToken, endOfFirstLine)
        return expr

    def _add_directive(self, directive_name, expr, line_col):
        if directive_name != 'compiler-settings':
            add = getattr(self._compiler, 'add' + directive_name.capitalize())
            add(expr, line_col)

    def eatSimpleIndentingDirective(self, directiveName):
        isLineClearToStartToken = self.isLineClearToStartToken()
        endOfFirstLinePos = self.findEOL()
        lineCol = self.getRowCol()
        self.getDirectiveStartToken()
        self.getWhiteSpace()

        expr = self.get_unbraced_expression(stop_chars=':')
        if self.matchColonForSingleLineShortFormDirective():
            self.advance()  # skip over :
            self._compiler.commitStrConst()
            self._add_directive(directiveName, expr, lineCol)

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
            if directiveName in {'else', 'elif', 'except', 'finally'}:
                self._compiler.commitStrConst()
                self._compiler.dedent()
            self._add_directive(directiveName, expr, lineCol)

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
        self.get_unbraced_expression()  # eat in any extra comment-like crap
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
        if self.peek() == VAR_START:
            raise ParseError(self, '#attr directive must not contain `$`')
        attribName = self.getIdentifier()
        self.getWhiteSpace()
        assert self.peek() == '='
        self.getc()
        self.getWhiteSpace()
        expr = ''.join(self.get_unbraced_expression(allow_cheetah_vars=False))
        self._compiler.addAttribute(attribName + ' = ' + expr)
        self._eatRestOfDirectiveTag(isLineClearToStartToken, endOfFirstLinePos)

    def eatDecorator(self):
        isLineClearToStartToken = self.isLineClearToStartToken()
        endOfFirstLinePos = self.findEOL()
        self.getDirectiveStartToken()
        expr = self.get_unbraced_expression(allow_cheetah_vars=False)
        decorator_expr = ''.join(expr)
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
        if self.peek() == VAR_START:
            raise ParseError(self, 'use #def func() instead of #def $func()')
        methodName = self.getIdentifier()
        self.getWhiteSpace()

        if directiveName == 'block' and self.peek() == '(':
            raise ParseError(
                self, '#block must not have an argspec, did you mean #def?',
            )
        elif directiveName == 'def' and self.peek() != '(':
            raise ParseError(self, '#def must contain an argspec (at least ())')

        if directiveName == 'def':
            argspec = self.get_def_argspec()
        else:
            argspec = ''

        if self.matchColonForSingleLineShortFormDirective():
            self.getc()
            self._eatSingleLineDef(
                methodName=methodName,
                argspec=argspec,
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
                argspec=argspec,
                startPos=startPos,
                isLineClearToStartToken=isLineClearToStartToken,
            )

    def _eatMultiLineDef(self, methodName, argspec, startPos, isLineClearToStartToken=False):
        self.get_unbraced_expression()  # slurp up any garbage left at the end
        signature = self[startPos:self.pos()]
        endOfFirstLinePos = self.findEOL()
        self._eatRestOfDirectiveTag(isLineClearToStartToken, endOfFirstLinePos)
        signature = ' '.join([line.strip() for line in signature.splitlines()])
        parserComment = (
            '## CHEETAH: generated from {} at line {}, col {}.'.format(
                signature, *self.getRowCol(startPos)
            )
        )
        self._compiler.startMethodDef(methodName, argspec, parserComment)

    def _eatSingleLineDef(self, methodName, argspec, startPos, endPos):
        fullSignature = self[startPos:endPos]
        parserComment = (
            '## Generated from {} at line {}, col {}.'.format(
                fullSignature, *self.getRowCol(startPos)
            )
        )
        self._compiler.startMethodDef(methodName, argspec, parserComment)

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

        self.get_unbraced_expression()  # throw away and unwanted crap that got added in
        self._eatRestOfDirectiveTag(isLineClearToStartToken, endOfFirstLine)

    def eatSuper(self):
        isLineClearToStartToken = self.isLineClearToStartToken()
        endOfFirstLine = self.findEOL()
        self.getDirectiveStartToken()
        self.advance(len('super'))
        self.getWhiteSpace()
        if not self.atEnd() and self.peek() == '(':
            argspec = self.get_def_argspec()
        else:
            argspec = ''

        self.get_unbraced_expression()  # throw away and unwanted crap that got added in
        self._eatRestOfDirectiveTag(isLineClearToStartToken, endOfFirstLine)
        self._compiler.addSuper(argspec)

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
