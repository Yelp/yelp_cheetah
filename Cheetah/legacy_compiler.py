'''
    Compiler classes for Cheetah:
    Compiler
    ClassCompiler
    MethodCompiler

    If you are trying to grok this code start with Compiler.__init__,
    Compiler.compile, and Compiler.__getattr__.
'''
from __future__ import unicode_literals

import collections
import copy
import re
import textwrap
import warnings

from Cheetah import five
from Cheetah.legacy_parser import LegacyParser
from Cheetah.legacy_parser import escapedNewlineRE
from Cheetah.SettingsManager import SettingsManager


CallDetails = collections.namedtuple(
    'CallDetails', ['call_id', 'function_name', 'args', 'lineCol'],
)

INDENT = 4 * ' '


# Settings format: (key, default, docstring)
_DEFAULT_COMPILER_SETTINGS = [
    ('useNameMapper', True, 'Enable NameMapper for dotted notation and searchList support'),
    ('useAutocalling', False, 'Detect and call callable objects in searchList, requires useNameMapper=True'),
    ('useDottedNotation', False, 'Allow use of dotted notation for dictionary lookups, requires useNameMapper=True'),
    ('useLegacyImportMode', True, 'All #import statements are relocated to the top of the generated Python module'),
    ('mainMethodName', 'respond', ''),
    ('mainMethodNameForSubclasses', 'writeBody', ''),
    ('cheetahVarStartToken', '$', ''),
    ('commentStartToken', '##', ''),
    ('directiveStartToken', '#', ''),
    ('directiveEndToken', '#', ''),
    ('PSPStartToken', '<%', ''),
    ('PSPEndToken', '%>', ''),
    ('gettextTokens', ['_', 'gettext', 'ngettext', 'pgettext', 'npgettext'], ''),
    ('macroDirectives', {}, 'For providing macros'),
]

DEFAULT_COMPILER_SETTINGS = dict((v[0], v[1]) for v in _DEFAULT_COMPILER_SETTINGS)


def genPlainVar(nameChunks):
    """Generate Python code for a Cheetah $var without using NameMapper."""
    nameChunks.reverse()
    chunk = nameChunks.pop()
    pythonCode = chunk[0] + chunk[2]
    while nameChunks:
        chunk = nameChunks.pop()
        pythonCode = pythonCode + '.' + chunk[0] + chunk[2]
    return pythonCode


def _arg_chunk_to_text(chunk):
    if chunk[1] is not None:
        return '{0}={1}'.format(*chunk)
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
        self._next_variable_id = 0
        self._methodName = methodName
        self._initialMethodComment = initialMethodComment
        self._indentLev = 2
        self._pendingStrConstChunks = []
        self._methodBodyChunks = []
        self._callRegionsStack = []
        self._filterRegionsStack = []
        self._hasReturnStatement = False
        self._isGenerator = False
        self._argStringList = [('self', None)]
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
        return ''.join((
            self.methodSignature(),
            '\n',
            self.methodBody(),
        ))

    def methodBody(self):
        return ''.join(self._methodBodyChunks)

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
        self.addChunk('write({0})'.format(chunk))

    def addFilteredChunk(self, chunk, rawExpr=None, lineCol=None):
        if rawExpr and rawExpr.find('\n') == -1 and rawExpr.find('\r') == -1:
            self.addChunk('_v = {0} # {1!r}'.format(chunk, rawExpr))
            self.appendToPrevChunk(' on line %s, col %s' % lineCol)
        else:
            self.addChunk('_v = %s' % chunk)

        self.addChunk('if _v is not NO_CONTENT: write(_filter(_v))')

    def addStrConst(self, strConst):
        self._pendingStrConstChunks.append(strConst)

    def commitStrConst(self):
        """Add the code for outputting the pending strConst without chopping off
        any whitespace from it.
        """
        if not self._pendingStrConstChunks:
            return

        strConst = ''.join(self._pendingStrConstChunks)
        self._pendingStrConstChunks = []
        if not strConst:
            return

        reprstr = repr(strConst)

        # If our repr starts with u, trim it off
        if reprstr.startswith('u'):  # pragma: no cover (py2 only)
            reprstr = reprstr[1:]

        body = escapedNewlineRE.sub('\\1\n', reprstr[1:-1])

        if reprstr[0] == "'":
            out = ("'''", body, "'''")
        else:
            out = ('"""', body, '"""')
        self.addWriteChunk(''.join(out))

    def handleWSBeforeDirective(self):
        """Truncate the pending strCont to the beginning of the current line.
        """
        if self._pendingStrConstChunks:
            src = self._pendingStrConstChunks[-1]
            BOL = max(src.rfind('\n') + 1, src.rfind('\r') + 1, 0)
            if BOL < len(src):
                self._pendingStrConstChunks[-1] = src[:BOL]

    def addMethComment(self, comment):
        self.addChunk('#' + comment)

    def _append_line_col_comment(self, line_col):
        self.appendToPrevChunk(' # generated from line {0}, col {1}.'.format(
            *line_col
        ))

    def addPlaceholder(self, expr, rawPlaceholder, line_col):
        self.addFilteredChunk(expr, rawPlaceholder, line_col)
        self._append_line_col_comment(line_col)

    def addSet(self, components, line_col):
        self.addChunk(' '.join([component.strip() for component in components]))
        self._append_line_col_comment(line_col)

    def addIndentingDirective(self, expr, line_col):
        assert expr[-1] != ':'
        expr = expr + ':'
        self.addChunk(expr)
        self._append_line_col_comment(line_col)
        self.indent()

    addWhile = addIndentingDirective
    addFor = addIndentingDirective
    addWith = addIndentingDirective
    addIf = addIndentingDirective
    addTry = addIndentingDirective

    def addReIndentingDirective(self, expr, line_col, dedent=True):
        self.commitStrConst()
        if dedent:
            self.dedent()
        assert expr[-1] != ':'
        expr = expr + ':'

        self.addChunk(expr)
        self._append_line_col_comment(line_col)
        self.indent()

    addExcept = addReIndentingDirective
    addFinally = addReIndentingDirective

    def addElse(self, expr, line_col, dedent=True):
        expr = re.sub(r'else[ \f\t]+if', 'elif', expr)
        self.addReIndentingDirective(expr, line_col, dedent=dedent)

    addElif = addElse

    def addReturn(self, expr):
        assert not self._isGenerator
        self.addChunk(expr)
        self._hasReturnStatement = True

    def addYield(self, expr):
        assert not self._hasReturnStatement
        self._isGenerator = True
        self.addChunk(expr)

    addSilent = addChunk
    addPass = addChunk
    addDel = addChunk
    addAssert = addChunk
    addRaise = addChunk
    addBreak = addChunk
    addContinue = addChunk

    def addPSP(self, PSP):
        self.commitStrConst()

        for line in PSP.splitlines():
            self.addChunk(line)

    def next_id(self):
        self._next_variable_id += 1
        return '_{0}'.format(self._next_variable_id)

    def startCallRegion(self, function_name, args, lineCol):
        call_id = self.next_id()
        call_details = CallDetails(call_id, function_name, args, lineCol)
        self._callRegionsStack.append(call_details)

        self.addChunk(
            '## START CALL REGION: {call_id} of {function_name} '
            'at line {line}, col {col}.'.format(
                call_id=call_id,
                function_name=function_name,
                line=lineCol[0],
                col=lineCol[1],
            )
        )
        self.addChunk('_orig_trans{0} = trans'.format(call_id))
        self.addChunk(
            'self.transaction = trans = _call{0} = DummyTransaction()'.format(
                call_id
            )
        )
        self.addChunk('write = trans.write')

    def endCallRegion(self):
        call_details = self._callRegionsStack.pop()
        call_id, function_name, args, (line, col) = (
            call_details.call_id,
            call_details.function_name,
            call_details.args,
            call_details.lineCol,
        )

        self.addChunk(
            'self.transaction = trans = _orig_trans{0}'.format(call_id),
        )
        self.addChunk('write = trans.write')
        self.addChunk('del _orig_trans{0}'.format(call_id))

        self.addChunk('_call_arg{0} = _call{0}.getvalue()'.format(call_id))
        self.addChunk('del _call{0}'.format(call_id))

        args = (', ' + args).strip()
        self.addFilteredChunk(
            '{function_name}(_call_arg{call_id}{args})'.format(
                function_name=function_name,
                call_id=call_id,
                args=args,
            )
        )
        self.addChunk('del _call_arg{0}'.format(call_id))
        self.addChunk(
            '## END CALL REGION: {call_id} of {function_name} '
            'at line {line}, col {col}.'.format(
                call_id=call_id,
                function_name=function_name,
                line=line,
                col=col,
            )
        )
        self.addChunk()

    def setFilter(self, filter_name):
        filter_id = self.next_id()
        self._filterRegionsStack.append(filter_id)

        self.addChunk('_orig_filter{0} = _filter'.format(filter_id))
        if filter_name.lower() == 'none':
            self.addChunk('_filter = self._CHEETAH__initialFilter')
        else:
            self.addChunk(
                '_filter = '
                'self._CHEETAH__currentFilter = '
                'self._CHEETAH__filters[{0!r}]'.format(filter_name)
            )

    def closeFilterBlock(self):
        filter_id = self._filterRegionsStack.pop()
        self.addChunk(
            '_filter = self._CHEETAH__currentFilter = _orig_filter{0}'.format(
                filter_id,
            )
        )

    def _addAutoSetupCode(self):
        self.addChunk(self._initialMethodComment)

        self.addChunk('trans = self.transaction')
        self.addChunk('if not trans:')
        self.indent()
        self.addChunk('self.transaction = trans = DummyTransaction()')
        self.addChunk('_dummyTrans = True')
        self.dedent()
        self.addChunk('else:')
        self.indent()
        self.addChunk('_dummyTrans = False')
        self.dedent()
        self.addChunk('write = trans.write')
        self.addChunk('SL = self._CHEETAH__searchList')
        self.addChunk('_filter = self._CHEETAH__currentFilter')
        self.addChunk()
        self.addChunk('## START - generated method body')
        self.addChunk()

    def _addAutoCleanupCode(self):
        self.addChunk()
        self.addChunk('## END - generated method body')
        self.addChunk()

        if not self._isGenerator:
            self.addChunk('if _dummyTrans:')
            self.indent()
            self.addChunk('self.transaction = None')
            self.addChunk('return trans.getvalue()')
            self.dedent()
            self.addChunk('else:')
            self.indent()
            self.addChunk('return NO_CONTENT')
            self.dedent()
        self.addChunk()

    def addMethArg(self, name, defVal):
        self._argStringList.append((name, defVal))

    def methodSignature(self):
        arg_text = arg_string_list_to_text(self._argStringList)
        return ''.join((
            ''.join(
                INDENT + decorator + '\n' for decorator in self._decorators
            ),
            INDENT + 'def ' + self.methodName() + '(' + arg_text + '):\n\n'
        ))


class ClassCompiler(object):
    methodCompilerClass = MethodCompiler

    def __init__(self, clsname, main_method_name):
        self._clsname = clsname
        self._mainMethodName = main_method_name
        self._decoratorsForNextMethod = []
        self._activeMethodsList = []        # stack while parsing/generating
        self._finishedMethodsList = []      # store by order
        self._methodsIndex = {}      # store by name
        self._baseClass = 'Template'
        # printed after methods in the gen class def:
        self._generatedAttribs = []
        methodCompiler = self._spawnMethodCompiler(
            main_method_name,
            '## CHEETAH: main method generated for this template'
        )

        self._setActiveMethodCompiler(methodCompiler)

    def __getattr__(self, name):
        """Provide access to the methods and attributes of the MethodCompiler
        at the top of the activeMethods stack: one-way namespace sharing
        """
        return getattr(self._activeMethodsList[-1], name)

    def cleanupState(self):
        while self._activeMethodsList:
            methCompiler = self._popActiveMethodCompiler()
            self._swallowMethodCompiler(methCompiler)

    def className(self):
        return self._clsname

    def setBaseClass(self, baseClassName):
        self._baseClass = baseClassName

    def setMainMethodName(self, methodName):
        if methodName == self._mainMethodName:
            return
        # change the name in the methodCompiler and add new reference
        mainMethod = self._methodsIndex[self._mainMethodName]
        mainMethod.setMethodName(methodName)
        self._methodsIndex[methodName] = mainMethod

        # get rid of the old reference and update self._mainMethodName
        del self._methodsIndex[self._mainMethodName]
        self._mainMethodName = methodName

    def _spawnMethodCompiler(self, methodName, initialMethodComment):
        methodCompiler = self.methodCompilerClass(
            methodName,
            class_compiler=self,
            initialMethodComment=initialMethodComment,
            decorators=self._decoratorsForNextMethod,
        )
        self._decoratorsForNextMethod = []
        self._methodsIndex[methodName] = methodCompiler
        return methodCompiler

    def _setActiveMethodCompiler(self, methodCompiler):
        self._activeMethodsList.append(methodCompiler)

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
        self._setActiveMethodCompiler(methodCompiler)
        for argName, defVal in argsList:
            methodCompiler.addMethArg(argName, defVal)

    def _finishedMethods(self):
        return self._finishedMethodsList

    def addDecorator(self, decorator_expr):
        """Set the decorator to be used with the next method in the source.

        See _spawnMethodCompiler() and MethodCompiler for the details of how
        this is used.
        """
        self._decoratorsForNextMethod.append(decorator_expr)

    def addAttribute(self, attrib_expr):
        self._generatedAttribs.append(attrib_expr)

    def addSuper(self, argsList):
        methodName = self._getActiveMethodCompiler().methodName()
        arg_text = arg_string_list_to_text(argsList)
        self.addFilteredChunk(
            'super({0}, self).{1}({2})'.format(
                self._clsname, methodName, arg_text,
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
        self.addChunk('self.{0}()'.format(methodName))

    def classDef(self):
        return '\n'.join((
            'class {0}({1}):'.format(self.className(), self._baseClass),
            INDENT + '## CHEETAH GENERATED METHODS', '\n', self.methodDefs(),
            INDENT + '## CHEETAH GENERATED ATTRIBUTES', '\n', self.attributes(),
        ))

    def methodDefs(self):
        return '\n\n'.join(
            method.methodDef() for method in self._finishedMethods()
        )

    def attributes(self):
        return '\n\n'.join(INDENT + attrib for attrib in self._generatedAttribs)


class LegacyCompiler(SettingsManager):
    parserClass = LegacyParser
    classCompilerClass = ClassCompiler

    def __init__(self, source, moduleName, settings=None):
        super(LegacyCompiler, self).__init__()
        if settings:
            self.updateSettings(settings)

        self._mainClassName = moduleName

        assert isinstance(source, five.text), 'the yelp-cheetah compiler requires text, not bytes.'

        if source == '':
            warnings.warn('You supplied an empty string for the source!')

        self._parser = self.parserClass(source, compiler=self)
        self._activeClassesList = []
        self._finishedClassesList = []  # listed by ordered
        self._finishedClassIndex = {}  # listed by name
        self._importStatements = [
            'from Cheetah.DummyTransaction import DummyTransaction',
            'from Cheetah.NameMapper import valueForName as VFN',
            'from Cheetah.NameMapper import valueFromSearchList as VFSL',
            'from Cheetah.NameMapper import valueFromFrameOrSearchList as VFFSL',
            'from Cheetah.Template import NO_CONTENT',
            'from Cheetah.Template import Template',
        ]

        self._importedVarNames = [
            'DummyTransaction',
            'NO_CONTENT',
            'Template',
            'VFN',
            'VFSL',
            'VFFSL',
        ]

        self._gettextScannables = []

    def __getattr__(self, name):
        """Provide one-way access to the methods and attributes of the
        ClassCompiler, and thereby the MethodCompilers as well.
        """
        return getattr(self._activeClassesList[-1], name)

    def _initializeSettings(self):
        self.updateSettings(copy.deepcopy(DEFAULT_COMPILER_SETTINGS))

    def _spawnClassCompiler(self, clsname):
        return self.classCompilerClass(
            clsname=clsname,
            main_method_name=self.setting('mainMethodName'),
        )

    def _addActiveClassCompiler(self, classCompiler):
        self._activeClassesList.append(classCompiler)

    def _getActiveClassCompiler(self):
        return self._activeClassesList[-1]

    def _popActiveClassCompiler(self):
        return self._activeClassesList.pop()

    def _swallowClassCompiler(self, classCompiler):
        classCompiler.cleanupState()
        self._finishedClassesList.append(classCompiler)
        self._finishedClassIndex[classCompiler.className()] = classCompiler
        return classCompiler

    def importedVarNames(self):
        return self._importedVarNames

    def addImportedVarNames(self, varNames, raw_statement=None):
        settings = self.settings()
        if not varNames:
            return
        if not settings.get('useLegacyImportMode'):
            if raw_statement and getattr(self, '_methodBodyChunks'):
                self.addChunk(raw_statement)
        else:
            self._importedVarNames.extend(varNames)

    # methods for adding stuff to the module and class definitions

    def genCheetahVar(self, nameChunks, lineCol, plain=False):
        # Look for gettext tokens within nameChunks (if any)
        if any(nameChunk[0] in self.setting('gettextTokens') for nameChunk in nameChunks):
            self.addGetTextVar(nameChunks, lineCol)
        if self.setting('useNameMapper') and not plain:
            return self.genNameMapperVar(nameChunks)
        else:
            return genPlainVar(nameChunks)

    def addGetTextVar(self, nameChunks, lineCol):
        """Output something that gettext can recognize.

        This is a harmless side effect necessary to make gettext work when it
        is scanning compiled templates for strings marked for translation.
        """
        scannable = genPlainVar(nameChunks[:])
        scannable += ' # generated from line {0}, col {1}.'.format(*lineCol)
        self._gettextScannables.append(scannable)

    def genNameMapperVar(self, nameChunks):
        """Generate valid Python code for a Cheetah $var, using NameMapper
        (Unified Dotted Notation with the SearchList).

        nameChunks = list of var subcomponents represented as tuples
          [(name, useAC, remainderOfExpr)...]
        where:
          name = the dotted name base
          useAC = where NameMapper should use autocalling on namemapperPart
          remainderOfExpr = any arglist, index, or slice

        If remainderOfExpr contains a call arglist (e.g. '(1234)') then useAC
        is False, otherwise it defaults to True. It is overridden by the global
        setting 'useAutocalling' if this setting is False.

        EXAMPLE
        ------------------------------------------------------------------------
        if the raw Cheetah Var is
          $a.b.c[1].d().x.y.z

        nameChunks is the list
          [ ('a.b.c',True,'[1]'), # A
            ('d',False,'()'),     # B
            ('x.y.z',True,''),    # C
          ]

        When this method is fed the list above it returns
          VFN(VFN(VFFSL(SL, 'a.b.c',True)[1], 'd',False)(), 'x.y.z',True)
        which can be represented as
          VFN(B`, name=C[0], executeCallables=(useAC and C[1]))C[2]
        where:
          VFN = NameMapper.valueForName
          VFFSL = NameMapper.valueFromFrameOrSearchList
          SL = self.searchList()
          useAC = self.setting('useAutocalling') # True in this example

          A = ('a.b.c',True,'[1]')
          B = ('d',False,'()')
          C = ('x.y.z',True,'')

          C` = VFN( VFN( VFFSL(SL, 'a.b.c',True)[1],
                         'd',False)(),
                    'x.y.z',True)
             = VFN(B`, name='x.y.z', executeCallables=True)

          B` = VFN(A`, name=B[0], executeCallables=(useAC and B[1]))B[2]
          A` = VFFSL(SL, name=A[0], executeCallables=(useAC and A[1]))A[2]
        """
        defaultUseAC = self.setting('useAutocalling')
        useDottedNotation = self.setting('useDottedNotation')

        nameChunks.reverse()
        name, useAC, remainder = nameChunks.pop()

        pythonCode = 'VFFSL(SL, "%s", %s, %s)%s' % (
            name,
            defaultUseAC and useAC,
            useDottedNotation,
            remainder,
        )

        while nameChunks:
            name, useAC, remainder = nameChunks.pop()
            pythonCode = 'VFN(%s, "%s", %s, %s)%s' % (
                pythonCode,
                name,
                defaultUseAC and useAC,
                useDottedNotation,
                remainder,
            )

        return pythonCode

    def setBaseClass(self, extends_name):
        self.setMainMethodName(self.setting('mainMethodNameForSubclasses'))

        if extends_name in self.importedVarNames():
            raise AssertionError(
                'yelp_cheetah only supports extends by module name'
            )

        # The #extends directive results in the base class being imported
        # There are (basically) three cases:
        # 1. #extends foo
        #    import added: from foo import foo
        #    baseclass: foo
        # 2. #extends foo.bar
        #    import added: from foo.bar import bar
        #    baseclass: bar
        # 3. #extends foo.bar.bar
        #    import added: from foo.bar import bar
        #    baseclass: bar
        chunks = extends_name.split('.')
        # Case 1
        # If we only have one part, assume it's like from {chunk} import {chunk}
        if len(chunks) == 1:
            chunks *= 2

        class_name = chunks[-1]
        if class_name != chunks[-2]:
            # Case 2
            # we assume the class name to be the module name
            module = '.'.join(chunks)
        else:
            # Case 3
            module = '.'.join(chunks[:-1])
        self._getActiveClassCompiler().setBaseClass(class_name)
        importStatement = 'from {0} import {1}'.format(module, class_name)
        self.addImportStatement(importStatement)
        self.addImportedVarNames((class_name,))

    def setCompilerSettings(self, settingsStr):
        self.updateSettingsFromConfigStr(settingsStr)
        self._parser.configureParser()

    def addImportStatement(self, impStatement):
        settings = self.settings()
        if not self._methodBodyChunks or settings.get('useLegacyImportMode'):
            # In the case where we are importing inline in the middle of a source block
            # we don't want to inadvertantly import the module at the top of the file either
            self._importStatements.append(impStatement)

        # @@TR 2005-01-01: there's almost certainly a cleaner way to do this!
        importVarNames = impStatement[impStatement.find('import') + len('import'):].split(',')
        importVarNames = [var.split()[-1] for var in importVarNames]  # handles aliases
        importVarNames = [var for var in importVarNames if not var == '*']
        self.addImportedVarNames(importVarNames, raw_statement=impStatement)  # used by #extend for auto-imports

    def addAttribute(self, attribName, expr):
        self._getActiveClassCompiler().addAttribute(attribName + ' = ' + expr)

    def addComment(self, comm):
        for line in comm.splitlines():
            self.addMethComment(line)

    # methods for module code wrapping

    def getModuleCode(self):
        classCompiler = self._spawnClassCompiler(self._mainClassName)
        self._addActiveClassCompiler(classCompiler)
        self._parser.parse()
        self._swallowClassCompiler(self._popActiveClassCompiler())

        moduleDef = textwrap.dedent(
            """
            from __future__ import unicode_literals
            %(imports)s

            # This is compiled yelp_cheetah sourcecode
            __YELP_CHEETAH__ = True

            %(classes)s

            %(scannables)s

            %(footer)s
            """
        ).strip() % {
            'imports': self.importStatements(),
            'classes': self.classDefs(),
            'scannables': self.gettextScannables(),
            'footer': self.moduleFooter(),
            'mainClassName': self._mainClassName,
        }

        return moduleDef

    def importStatements(self):
        return '\n'.join(self._importStatements)

    def classDefs(self):
        classDefs = [klass.classDef() for klass in self._finishedClassesList]
        return '\n\n'.join(classDefs)

    def moduleFooter(self):
        return """
# CHEETAH was developed by Tavis Rudd and Mike Orr
# with code, advice and input from many other volunteers.
# For more information visit http://www.CheetahTemplate.org/

if __name__ == '__main__':
    from os import environ
    from sys import stdout
    stdout.write({main_class_name}(searchList=[environ]).respond())
""".format(main_class_name=self._mainClassName)

    def gettextScannables(self):
        scannables = tuple(INDENT + nameChunks for nameChunks in self._gettextScannables)
        if scannables:
            return '\n'.join((
                '\n', '## CHEETAH GENERATED SCANNABLE GETTEXT', '\n'
                'def __CHEETAH_scannables():',
                ) + scannables
            )
        else:
            return ''
