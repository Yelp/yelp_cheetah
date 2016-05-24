'''
    Compiler classes for Cheetah:
    Compiler
    ClassCompiler
    MethodCompiler

    If you are trying to grok this code start with Compiler.__init__,
    Compiler.compile, and Compiler.__getattr__.
'''
from __future__ import unicode_literals

import contextlib
import copy
import re
import textwrap
import warnings

import six

from Cheetah.ast_utils import get_imported_names
from Cheetah.ast_utils import get_lvalues
from Cheetah.legacy_parser import escapedNewlineRE
from Cheetah.legacy_parser import LegacyParser
from Cheetah.SettingsManager import SettingsManager


INDENT = 4 * ' '


BUILTIN_NAMES = frozenset(dir(six.moves.builtins))


DEFAULT_COMPILER_SETTINGS = {
    # Enable NameMapper for namespace support.
    'useNameMapper': True,
    # All #import statements are hoisted to the top of the module
    'useLegacyImportMode': True,
    'gettextTokens': ['_', 'gettext', 'ngettext', 'pgettext', 'npgettext'],
}

CLASS_NAME = 'YelpCheetahTemplate'
BASE_CLASS_NAME = 'YelpCheetahBaseClass'


def genPlainVar(nameChunks):
    """Generate Python code for a Cheetah $var without using NameMapper."""
    return '.'.join(name + rest for name, rest in nameChunks)


def genNameMapperVar(nameChunks):
    name, remainder = nameChunks[0]
    namept1, dot, rest = name.partition('.')
    start = 'VFFSL("{}", locals(), globals(), self, NS){}{}{}'.format(namept1, dot, rest, remainder)
    tail = genPlainVar(nameChunks[1:])
    return start + ('.' if tail else '') + tail


def _arg_chunk_to_text(chunk):
    if chunk[1] is not None:
        return '{}={}'.format(*chunk)
    else:
        return chunk[0]


def arg_string_list_to_text(arg_string_list):
    return ', '.join(_arg_chunk_to_text(chunk) for chunk in arg_string_list)


class MethodCompiler(object):
    def __init__(
            self,
            methodName,
            class_compiler,
            initialMethodComment,
            decorators=None,
    ):
        self._methodName = methodName
        self._initialMethodComment = initialMethodComment
        self._indentLev = 2
        self._pendingStrConstChunks = []
        self._methodBodyChunks = []
        self._hasReturnStatement = False
        self._isGenerator = False
        self._arguments = [('self', None)]
        self._local_vars = {'self'}
        self._decorators = decorators or []

    def cleanupState(self):
        """Called by the containing class compiler instance"""
        self.commitStrConst()

        self._indentLev = 2
        mainBodyChunks = self._methodBodyChunks
        self._methodBodyChunks = []
        self._addAutoSetupCode()
        self._methodBodyChunks.extend(mainBodyChunks)
        self._addAutoCleanupCode()

    def methodName(self):
        return self._methodName

    def setMethodName(self, name):
        self._methodName = name

    # methods for managing indentation

    def indentation(self):
        return INDENT * self._indentLev

    def indent(self):
        self._indentLev += 1

    def dedent(self):
        if not self._indentLev:
            raise AssertionError('Attempt to dedent when the indentLev is 0')
        self._indentLev -= 1

    # methods for final code wrapping

    def methodDef(self):
        self.commitStrConst()
        return self.methodSignature() + ''.join(self._methodBodyChunks)

    # methods for adding code

    def addChunk(self, chunk=''):
        self.commitStrConst()
        if chunk:
            chunk = '\n' + self.indentation() + chunk
        else:
            chunk = '\n'
        self._methodBodyChunks.append(chunk)

    def appendToPrevChunk(self, appendage):
        self._methodBodyChunks[-1] += appendage

    def addWriteChunk(self, chunk):
        self.addChunk('self.transaction.write({})'.format(chunk))

    def addFilteredChunk(self, chunk, rawExpr=None, lineCol=None):
        if rawExpr and rawExpr.find('\n') == -1 and rawExpr.find('\r') == -1:
            self.addChunk('_v = {} # {!r}'.format(chunk, rawExpr))
            self.appendToPrevChunk(' on line %s, col %s' % lineCol)
        else:
            self.addChunk('_v = %s' % chunk)

        self.addChunk('if _v is not NO_CONTENT: self.transaction.write(self._CHEETAH__currentFilter(_v))')

    def addStrConst(self, strConst):
        self._pendingStrConstChunks.append(strConst)

    def getStrConst(self):
        return ''.join(self._pendingStrConstChunks)

    def clearStrConst(self):
        del self._pendingStrConstChunks[:]

    def commitStrConst(self):
        """Add the code for outputting the pending strConst without chopping off
        any whitespace from it.
        """
        if not self._pendingStrConstChunks:
            return

        strConst = self.getStrConst()
        self.clearStrConst()
        if not strConst:
            return

        reprstr = repr(strConst).lstrip('u')
        body = escapedNewlineRE.sub('\\1\n', reprstr[1:-1])

        if reprstr[0] == "'":
            out = ("'''", body, "'''")
        else:
            out = ('"""', body, '"""')
        self.addWriteChunk(''.join(out))

    def handleWSBeforeDirective(self):
        """Truncate the pending strConst to the beginning of the current line.
        """
        if self._pendingStrConstChunks:
            src = self._pendingStrConstChunks[-1]
            BOL = max(src.rfind('\n') + 1, src.rfind('\r') + 1, 0)
            if BOL < len(src):
                self._pendingStrConstChunks[-1] = src[:BOL]

    def addComment(self, comment):
        comment = comment.rstrip('\n')
        self.addChunk('#' + comment)

    def _append_line_col_comment(self, line_col):
        self.appendToPrevChunk(' # generated from line {}, col {}.'.format(
            *line_col
        ))

    def _update_locals(self, expr):
        self._local_vars.update(get_lvalues(expr))

    def addPlaceholder(self, expr, rawPlaceholder, line_col):
        self.addFilteredChunk(expr, rawPlaceholder, line_col)
        self._append_line_col_comment(line_col)

    def _add_with_line_col(self, expr, line_col):
        self._update_locals(expr)
        self.addChunk(expr)
        self._append_line_col_comment(line_col)

    addSet = addSilent = addPy = addPass = addDel = _add_with_line_col
    addAssert = addRaise = addBreak = addContinue = _add_with_line_col

    def addReturn(self, expr, line_col):
        assert not self._isGenerator
        self._hasReturnStatement = True
        self._add_with_line_col(expr, line_col)

    def addYield(self, expr, line_col):
        assert not self._hasReturnStatement
        self._isGenerator = True
        self._add_with_line_col(expr, line_col)

    def _add_indenting_directive(self, expr, line_col):
        assert expr[-1] != ':'
        expr = expr + ':'
        self.addChunk(expr)
        self._append_line_col_comment(line_col)
        self.indent()

    addWhile = addIf = addTry = _add_indenting_directive

    def _add_lvalue_indenting_directive(self, expr, line_col):
        self._update_locals(expr + ':\n    pass')
        self._add_indenting_directive(expr, line_col)

    addFor = addWith = _add_lvalue_indenting_directive

    def addReIndentingDirective(self, expr, line_col, dedent=True):
        self.commitStrConst()
        if dedent:
            self.dedent()
        assert expr[-1] != ':'
        expr = expr + ':'

        self.addChunk(expr)
        self._append_line_col_comment(line_col)
        self.indent()

    addFinally = addReIndentingDirective

    def addExcept(self, expr, line_col, dedent=True):
        self._update_locals('try:\n    pass\n' + expr + ':\n    pass')
        self.addReIndentingDirective(expr, line_col, dedent=dedent)

    def addElse(self, expr, line_col, dedent=True):
        expr = re.sub('else +if', 'elif', expr)
        self.addReIndentingDirective(expr, line_col, dedent=dedent)

    addElif = addElse

    def _addAutoSetupCode(self):
        self.addChunk(self._initialMethodComment)

        self.addChunk('if not self.transaction:')
        self.indent()
        self.addChunk('self.transaction = io.StringIO()')
        self.addChunk('_dummyTrans = True')
        self.dedent()
        self.addChunk('else:')
        self.indent()
        self.addChunk('_dummyTrans = False')
        self.dedent()
        self.addChunk('NS = self._CHEETAH__namespace')
        self.addChunk()
        self.addChunk('## START - generated method body')
        self.addChunk()

    def _addAutoCleanupCode(self):
        self.addChunk()
        self.addChunk('## END - generated method body')

        if not self._isGenerator:
            self.addChunk()
            self.addChunk('if _dummyTrans:')
            self.indent()
            self.addChunk('result = self.transaction.getvalue()')
            self.addChunk('self.transaction = None')
            self.addChunk('return result')
            self.dedent()
            self.addChunk('else:')
            self.indent()
            self.addChunk('return NO_CONTENT')
            self.dedent()

    def addMethArg(self, name, val):
        self._arguments.append((name, val))
        self._local_vars.add(name.lstrip('*'))

    def methodSignature(self):
        arg_text = arg_string_list_to_text(self._arguments)
        return ''.join((
            ''.join(
                INDENT + decorator + '\n' for decorator in self._decorators
            ),
            INDENT + 'def ' + self.methodName() + '(' + arg_text + '):'
        ))


class ClassCompiler(object):
    methodCompilerClass = MethodCompiler

    def __init__(self, main_method_name):
        self._mainMethodName = main_method_name
        self._decoratorsForNextMethod = []
        self._activeMethodsList = []        # stack while parsing/generating
        self._attrs = []
        self._finishedMethodsList = []      # store by order

        self._main_method = self._spawnMethodCompiler(
            main_method_name,
            '## CHEETAH: main method generated for this template'
        )

    def __getattr__(self, name):
        """Provide access to the methods and attributes of the MethodCompiler
        at the top of the activeMethods stack: one-way namespace sharing
        """
        return getattr(self._activeMethodsList[-1], name)

    def cleanupState(self):
        while self._activeMethodsList:
            methCompiler = self._popActiveMethodCompiler()
            self._swallowMethodCompiler(methCompiler)

    def setMainMethodName(self, methodName):
        self._main_method.setMethodName(methodName)

    def _spawnMethodCompiler(self, methodName, initialMethodComment):
        methodCompiler = self.methodCompilerClass(
            methodName,
            class_compiler=self,
            initialMethodComment=initialMethodComment,
            decorators=self._decoratorsForNextMethod,
        )
        self._decoratorsForNextMethod = []
        self._activeMethodsList.append(methodCompiler)
        return methodCompiler

    def _getActiveMethodCompiler(self):
        return self._activeMethodsList[-1]

    def _popActiveMethodCompiler(self):
        return self._activeMethodsList.pop()

    def _swallowMethodCompiler(self, methodCompiler):
        methodCompiler.cleanupState()
        self._finishedMethodsList.append(methodCompiler)
        return methodCompiler

    def startMethodDef(self, methodName, argsList, parserComment):
        methodCompiler = self._spawnMethodCompiler(
            methodName, parserComment,
        )
        for argName, defVal in argsList:
            methodCompiler.addMethArg(argName, defVal)

    def addDecorator(self, decorator_expr):
        """Set the decorator to be used with the next method in the source.

        See _spawnMethodCompiler() and MethodCompiler for the details of how
        this is used.
        """
        self._decoratorsForNextMethod.append(decorator_expr)

    def addAttribute(self, attr_expr):
        self._attrs.append(attr_expr)

    def addSuper(self, argsList):
        methodName = self._getActiveMethodCompiler().methodName()
        arg_text = arg_string_list_to_text(argsList)
        self.addFilteredChunk(
            'super({}, self).{}({})'.format(
                CLASS_NAME, methodName, arg_text,
            )
        )

    def closeDef(self):
        self.commitStrConst()
        methCompiler = self._popActiveMethodCompiler()
        self._swallowMethodCompiler(methCompiler)

    def closeBlock(self):
        self.commitStrConst()
        methCompiler = self._popActiveMethodCompiler()
        methodName = methCompiler.methodName()
        self._swallowMethodCompiler(methCompiler)

        # insert the code to call the block
        self.addChunk('self.{}()'.format(methodName))

    def class_def(self):
        return '\n'.join((
            'class {}({}):\n'.format(CLASS_NAME, BASE_CLASS_NAME),
            self.attributes(),
            self.methodDefs(),
        ))

    def methodDefs(self):
        return '\n\n'.join(
            method.methodDef() for method in self._finishedMethodsList
        )

    def attributes(self):
        if self._attrs:
            return '\n'.join(INDENT + attr for attr in self._attrs) + '\n'
        else:
            return ''


class LegacyCompiler(SettingsManager):
    parserClass = LegacyParser
    classCompilerClass = ClassCompiler

    def __init__(self, source, settings=None):
        super(LegacyCompiler, self).__init__()
        if settings:
            self.updateSettings(settings)

        assert isinstance(source, six.text_type), 'the yelp-cheetah compiler requires text, not bytes.'

        if source == '':
            warnings.warn('You supplied an empty string for the source!')

        self._parser = self.parserClass(source, compiler=self)
        self._class_compiler = None
        self._base_import = 'from Cheetah.Template import {} as {}'.format(
            CLASS_NAME, BASE_CLASS_NAME,
        )
        self._importStatements = [
            'import io',
            'from Cheetah.NameMapper import value_from_frame_or_search_list as VFFSL',
            'from Cheetah.Template import NO_CONTENT',
        ]
        self._global_vars = {'io', 'NO_CONTENT', 'VFFSL'}

        self._gettext_scannables = []

    def __getattr__(self, name):
        """Provide one-way access to the methods and attributes of the
        ClassCompiler, and thereby the MethodCompilers as well.
        """
        return getattr(self._class_compiler, name)

    def _initializeSettings(self):
        self._settings = copy.deepcopy(DEFAULT_COMPILER_SETTINGS)

    def _spawnClassCompiler(self):
        return self.classCompilerClass(main_method_name='respond')

    @contextlib.contextmanager
    def _set_class_compiler(self, class_compiler):
        orig = self._class_compiler
        self._class_compiler = class_compiler
        try:
            yield
        finally:
            self._class_compiler = orig

    def addImportedVarNames(self, varNames, raw_statement=None):
        if not varNames:
            return
        if not self.setting('useLegacyImportMode'):
            if raw_statement and getattr(self, '_methodBodyChunks'):
                self.addChunk(raw_statement)
        else:
            self._global_vars.update(varNames)

    # methods for adding stuff to the module and class definitions

    def genCheetahVar(self, nameChunks, lineCol):
        first_accessed_var = nameChunks[0][0].partition('.')[0]
        plain = (
            not self.setting('useNameMapper') or
            first_accessed_var in self._local_vars or
            first_accessed_var in self._global_vars or
            first_accessed_var in BUILTIN_NAMES
        )

        # Look for gettext tokens within nameChunks (if any)
        if any(nameChunk[0] in self.setting('gettextTokens') for nameChunk in nameChunks):
            self.addGetTextVar(nameChunks, lineCol)

        if plain:
            return genPlainVar(nameChunks)
        else:
            return genNameMapperVar(nameChunks)

    def addGetTextVar(self, nameChunks, lineCol):
        """Output something that gettext can recognize.

        This is a harmless side effect necessary to make gettext work when it
        is scanning compiled templates for strings marked for translation.
        """
        scannable = genPlainVar(nameChunks[:])
        scannable += ' # generated from line {}, col {}.'.format(*lineCol)
        self._gettext_scannables.append(scannable)

    def set_extends(self, extends_name):
        self.setMainMethodName('writeBody')

        if extends_name in self._global_vars:
            raise AssertionError(
                'yelp_cheetah only supports extends by module name'
            )

        self._base_import = 'from {} import {} as {}'.format(
            extends_name, CLASS_NAME, BASE_CLASS_NAME,
        )

    def add_compiler_settings(self):
        settings_str = self.getStrConst()
        self.clearStrConst()
        self.updateSettingsFromConfigStr(settings_str)

    def _add_import_statement(self, imp_statement, line_col):
        imported_names = get_imported_names(imp_statement)

        if not self._methodBodyChunks or self.setting('useLegacyImportMode'):
            # In the case where we are importing inline in the middle of a
            # source block we don't want to inadvertantly import the module at
            # the top of the file either
            self._importStatements.append(imp_statement)
        self.addImportedVarNames(imported_names, raw_statement=imp_statement)

    addFrom = addImport = _add_import_statement

    # methods for module code wrapping

    def getModuleCode(self):
        class_compiler = self._spawnClassCompiler()
        with self._set_class_compiler(class_compiler):
            self._parser.parse()
            class_compiler.cleanupState()

        moduleDef = textwrap.dedent(
            """
            from __future__ import absolute_import
            from __future__ import unicode_literals
            {imports}
            {base_import}


            # This is compiled yelp_cheetah sourcecode
            __YELP_CHEETAH__ = True


            {class_def}

            {scannables}
            if __name__ == '__main__':
                from os import environ
                from sys import stdout
                stdout.write({class_name}(namespace=environ).respond())
            """
        ).strip().format(
            imports='\n'.join(self._importStatements),
            base_import=self._base_import,
            class_def=class_compiler.class_def(),
            scannables=self.gettext_scannables(),
            class_name=CLASS_NAME,
        ) + '\n'

        return moduleDef

    def gettext_scannables(self):
        scannables = tuple(INDENT + nameChunks for nameChunks in self._gettext_scannables)
        if scannables:
            return '\n'.join(
                ('\ndef __CHEETAH_gettext_scannables():',) + scannables
            ) + '\n\n'
        else:
            return ''
