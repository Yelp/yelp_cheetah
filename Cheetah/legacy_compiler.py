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
from Cheetah.legacy_parser import SET_GLOBAL
from Cheetah.legacy_parser import SET_MODULE
from Cheetah.legacy_parser import escapedNewlineRE
from Cheetah.SettingsManager import SettingsManager


FilterDetails = collections.namedtuple('FilterDetails', ['ID', 'theFilter'])
CallDetails = collections.namedtuple(
    'CallDetails', ['ID', 'functionName', 'args', 'lineCol'],
)


# Settings format: (key, default, docstring)
_DEFAULT_COMPILER_SETTINGS = [
    ('useNameMapper', True, 'Enable NameMapper for dotted notation and searchList support'),
    ('useAutocalling', False, 'Detect and call callable objects in searchList, requires useNameMapper=True'),
    ('useDottedNotation', False, 'Allow use of dotted notation for dictionary lookups, requires useNameMapper=True'),
    ('useLegacyImportMode', True, 'All #import statements are relocated to the top of the generated Python module'),

    ('mainMethodName', 'respond', ''),
    ('mainMethodNameForSubclasses', 'writeBody', ''),
    ('indentationStep', ' ' * 4, ''),

    ('cheetahVarStartToken', '$', ''),
    ('commentStartToken', '##', ''),
    ('directiveStartToken', '#', ''),
    ('directiveEndToken', '#', ''),
    ('PSPStartToken', '<%', ''),
    ('PSPEndToken', '%>', ''),
    ('gettextTokens', ['_', 'ngettext'], ''),
    ('macroDirectives', {}, 'For providing macros'),

    ('future_unicode_literals', True, 'from __future__ import unicode_literals'),
]

DEFAULT_COMPILER_SETTINGS = dict([(v[0], v[1]) for v in _DEFAULT_COMPILER_SETTINGS])


def genPlainVar(nameChunks):
    """Generate Python code for a Cheetah $var without using NameMapper
    (Unified Dotted Notation with the SearchList).
    """
    nameChunks.reverse()
    chunk = nameChunks.pop()
    pythonCode = chunk[0] + chunk[2]
    while nameChunks:
        chunk = nameChunks.pop()
        pythonCode = (pythonCode + '.' + chunk[0] + chunk[2])
    return pythonCode


class GenUtils(object):
    """An abstract baseclass for the Compiler classes that provides methods that
    perform generic utility functions or generate pieces of output code from
    information passed in by the LegacyParser baseclass.  These methods don't
    do any parsing themselves.
    """

    def genCheetahVar(self, nameChunks, plain=False):
        if nameChunks[0][0] in self.setting('gettextTokens'):
            self.addGetTextVar(nameChunks)
        if self.setting('useNameMapper') and not plain:
            return self.genNameMapperVar(nameChunks)
        else:
            return genPlainVar(nameChunks)

    def addGetTextVar(self, nameChunks):
        """Output something that gettext can recognize.

        This is a harmless side effect necessary to make gettext work when it
        is scanning compiled templates for strings marked for translation.

        @@TR: another marginally more efficient approach would be to put the
        output in a dummy method that is never called.
        """
        # @@TR: this should be in the compiler not here
        self.addChunk("if False:")
        self.indent()
        self.addChunk(genPlainVar(nameChunks[:]))
        self.dedent()

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
          VFSL = NameMapper.valueFromSearchList # optionally used instead of VFFSL
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


class MethodCompiler(GenUtils):
    def __init__(
            self,
            methodName,
            classCompiler,
            initialMethodComment,
            decorators=None,
    ):
        self._next_variable_id = 0
        self._settingsManager = classCompiler
        self._classCompiler = classCompiler
        self._moduleCompiler = classCompiler._moduleCompiler
        self._methodName = methodName
        self._initialMethodComment = initialMethodComment
        self._indent = self.setting('indentationStep')
        self._indentLev = 2
        self._pendingStrConstChunks = []
        self._methodSignature = None
        self._methodBodyChunks = []
        self._callRegionsStack = []
        self._filterRegionsStack = []
        self._hasReturnStatement = False
        self._isGenerator = False
        self._argStringList = [("self", None)]
        self._decorators = decorators or []

    def setting(self, key):
        return self._settingsManager.setting(key)

    def cleanupState(self):
        """Called by the containing class compiler instance
        """
        self.commitStrConst()

        has_double_star_arg = any(
            argname.strip().startswith('**')
            for argname, _ in self._argStringList
        )

        if not has_double_star_arg:
            self.addMethArg('**KWS', None)

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
        return self._indent * self._indentLev

    def indent(self):
        self._indentLev += 1

    def dedent(self):
        if not self._indentLev:
            raise AssertionError('Attempt to dedent when the indentLev is 0')
        self._indentLev -= 1

    # methods for final code wrapping

    def methodDef(self):
        self.commitStrConst()
        methodDefChunks = (
            self.methodSignature(),
            '\n',
            self.methodBody())
        methodDef = ''.join(methodDefChunks)
        return methodDef

    def methodBody(self):
        return ''.join(self._methodBodyChunks)

    # methods for adding code

    def addChunk(self, chunk):
        self.commitStrConst()
        chunk = "\n" + self.indentation() + chunk
        self._methodBodyChunks.append(chunk)

    def appendToPrevChunk(self, appendage):
        self._methodBodyChunks[-1] = self._methodBodyChunks[-1] + appendage

    def addWriteChunk(self, chunk):
        self.addChunk('write(' + chunk + ')')

    def addFilteredChunk(self, chunk, rawExpr=None, lineCol=None):
        if rawExpr and rawExpr.find('\n') == -1 and rawExpr.find('\r') == -1:
            self.addChunk("_v = %s # %r" % (chunk, rawExpr))
            assert lineCol
            self.appendToPrevChunk(' on line %s, col %s' % lineCol)
        else:
            self.addChunk("_v = %s" % chunk)

        self.addChunk("if _v is not NO_CONTENT: write(_filter(_v))")

    def addStrConst(self, strConst):
        if self._pendingStrConstChunks:
            self._pendingStrConstChunks.append(strConst)
        else:
            self._pendingStrConstChunks = [strConst]

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

        if self.setting('future_unicode_literals'):
            out = []
        else:
            out = ['u']

        # If our repr starts with u, trim it off
        if reprstr.startswith('u'):  # pragma: no cover (py2 only)
            reprstr = reprstr[1:]

        body = escapedNewlineRE.sub('\\1\n', reprstr[1:-1])

        if reprstr[0] == "'":
            out.extend(["'''", body, "'''"])
        else:
            out.extend(['"""', body, '"""'])
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
        self.addChunk('# ' + comment)

    def addPlaceholder(self, expr, rawPlaceholder, lineCol):
        self.addFilteredChunk(expr, rawPlaceholder, lineCol)
        self.appendToPrevChunk(' # from line %s, col %s' % lineCol + '.')

    def addSet(self, expr, exprComponents, setStyle):
        if setStyle is SET_GLOBAL:
            (LVALUE, OP, RVALUE) = (exprComponents.LVALUE,
                                    exprComponents.OP,
                                    exprComponents.RVALUE)
            # we need to split the LVALUE to deal with globalSetVars
            splitPos1 = LVALUE.find('.')
            splitPos2 = LVALUE.find('[')
            if splitPos1 > 0 and splitPos2 == -1:
                splitPos = splitPos1
            elif splitPos1 > 0 and splitPos1 < max(splitPos2, 0):
                splitPos = splitPos1
            else:
                splitPos = splitPos2

            if splitPos > 0:
                primary = LVALUE[:splitPos]
                secondary = LVALUE[splitPos:]
            else:
                primary = LVALUE
                secondary = ''
            LVALUE = 'self._CHEETAH__globalSetVars["' + primary + '"]' + secondary
            expr = LVALUE + ' ' + OP + ' ' + RVALUE.strip()

        if setStyle is SET_MODULE:
            self._moduleCompiler.addModuleGlobal(expr)
        else:
            self.addChunk(expr)

    def addIndentingDirective(self, expr, lineCol):
        assert expr and expr[-1] != ':'
        expr = expr + ':'
        self.addChunk(expr)
        assert lineCol
        self.appendToPrevChunk(' # generated from line %s, col %s' % lineCol)
        self.indent()

    addWhile = addIndentingDirective
    addFor = addIndentingDirective
    addWith = addIndentingDirective
    addIf = addIndentingDirective
    addTry = addIndentingDirective

    def addReIndentingDirective(self, expr, dedent=True, lineCol=None):
        self.commitStrConst()
        if dedent:
            self.dedent()
        assert expr[-1] != ':'
        expr = expr + ':'

        self.addChunk(expr)
        assert lineCol
        self.appendToPrevChunk(' # generated from line %s, col %s' % lineCol)
        self.indent()

    addExcept = addReIndentingDirective
    addFinally = addReIndentingDirective

    def addElse(self, expr, dedent=True, lineCol=None):
        expr = re.sub(r'else[ \f\t]+if', 'elif', expr)
        self.addReIndentingDirective(expr, dedent=dedent, lineCol=lineCol)

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

    def nextCacheID(self):
        self._next_variable_id += 1
        return '_{0}'.format(self._next_variable_id)

    nextCallRegionID = nextCacheID

    def startCallRegion(self, functionName, args, lineCol):
        call_id = self.nextCallRegionID()
        call_details = CallDetails(call_id, functionName, args, lineCol)

        self._callRegionsStack.append((call_id, call_details))

        self.addChunk('## START CALL REGION: '
                      + call_id
                      + ' of ' + functionName
                      + ' at line %s, col %s' % lineCol + ' in the source.')
        self.addChunk('_orig_trans{0} = trans'.format(call_id))
        self.addChunk('trans = _callCollector{0} = DummyTransaction()'.format(
            call_id,
        ))
        self.addChunk('self.transaction = trans')
        self.addChunk('write = _callCollector{0}.response().write'.format(
            call_id,
        ))

    def endCallRegion(self):
        ID, callDetails = self._callRegionsStack[-1]
        functionName, initialKwArgs, lineCol = (
            callDetails.functionName, callDetails.args, callDetails.lineCol)

        def reset(ID=ID):
            self.addChunk('trans = _orig_trans{0}'.format(ID))
            self.addChunk('self.transaction = trans')
            self.addChunk('write = trans.response().write')
            self.addChunk('del _orig_trans{0}'.format(ID))

        reset()
        self.addChunk('_callArgVal%(ID)s = _callCollector%(ID)s.response().getvalue()' % locals())
        self.addChunk('del _callCollector%(ID)s' % locals())
        if initialKwArgs:
            initialKwArgs = ', ' + initialKwArgs
        self.addFilteredChunk('%(functionName)s(_callArgVal%(ID)s%(initialKwArgs)s)' % locals())
        self.addChunk('del _callArgVal%(ID)s' % locals())
        self.addChunk('## END CALL REGION: '
                      + ID
                      + ' of ' + functionName
                      + ' at line %s, col %s' % lineCol + ' in the source.')
        self.addChunk('')
        self._callRegionsStack.pop()  # attrib of current methodCompiler

    nextFilterRegionID = nextCacheID

    def setFilter(self, filter_name):
        filter_id = self.nextFilterRegionID()
        filter_details = FilterDetails(filter_id, filter_name)
        self._filterRegionsStack.append(
            (filter_id, filter_details)
        )

        self.addChunk('_orig_filter{0} = _filter'.format(filter_id))
        if filter_name.lower() == 'none':
            self.addChunk('_filter = self._CHEETAH__initialFilter')
        else:
            # is string representing the name of a builtin filter
            self.addChunk(
                '_filter = '
                'self._CHEETAH__currentFilter = '
                'self._CHEETAH__filters[{0!r}]'.format(filter_name)
            )

    def closeFilterBlock(self):
        filter_id = self._filterRegionsStack.pop()[0]
        self.addChunk(
            '_filter = self._CHEETAH__currentFilter = _orig_filter{0}'.format(
                filter_id,
            )
        )

    def isClassMethod(self):
        return '@classmethod' in self._decorators

    def isStaticMethod(self):
        return '@staticmethod' in self._decorators

    def _addAutoSetupCode(self):
        self.addChunk(self._initialMethodComment)

        if not self.isClassMethod() and not self.isStaticMethod():
            self.addChunk('trans = self.transaction')
            self.addChunk('if not trans:')
            self.indent()
            self.addChunk('self.transaction = trans = DummyTransaction()')
            self.addChunk('_dummyTrans = True')
            self.dedent()
            self.addChunk('else: _dummyTrans = False')
        else:
            self.addChunk('trans = DummyTransaction()')
            self.addChunk('_dummyTrans = True')
        self.addChunk('write = trans.response().write')
        if self.setting('useNameMapper'):
            if not self.isClassMethod() and not self.isStaticMethod():
                self.addChunk('SL = self._CHEETAH__searchList')
            else:
                self.addChunk('SL = []')
        if self.isClassMethod() or self.isStaticMethod():
            self.addChunk('_filter = lambda x, **kwargs: unicode(x)')
        else:
            self.addChunk('_filter = self._CHEETAH__currentFilter')
        self.addChunk('')
        self.addChunk("#" * 40)
        self.addChunk('## START - generated method body')
        self.addChunk('')

    def _addAutoCleanupCode(self):
        self.addChunk('')
        self.addChunk("#" * 40)
        self.addChunk('## END - generated method body')
        self.addChunk('')

        if not self._isGenerator:
            self.addStop()
        self.addChunk('')

    def addStop(self):
        no_content = 'NO_CONTENT'
        self.addChunk('if _dummyTrans:')
        self.indent()
        self.addChunk('self.transaction = None')
        self.addChunk('return trans.response().getvalue()')
        self.dedent()
        self.addChunk('else:')
        self.indent()
        self.addChunk('return %s' % no_content)
        self.dedent()

    def addMethArg(self, name, defVal=None):
        self._argStringList.append((name, defVal))

    def methodSignature(self):
        argStringChunks = []
        for arg in self._argStringList:
            chunk = arg[0]
            if chunk == 'self' and self.isClassMethod():
                chunk = 'cls'
            if chunk == 'self' and self.isStaticMethod():
                # Skip the "self" method for @staticmethod decorators
                continue
            if arg[1] is not None:
                chunk += '=' + arg[1]
            argStringChunks.append(chunk)
        argString = (', ').join(argStringChunks)

        output = []
        if self._decorators:
            output.append(''.join([self._indent + decorator + '\n'
                                   for decorator in self._decorators]))
        output.append(self._indent + "def "
                      + self.methodName() + "(" +
                      argString + "):\n\n")
        return ''.join(output)


##################################################
# CLASS COMPILERS


class ClassCompiler(GenUtils):
    methodCompilerClass = MethodCompiler

    def __init__(self, className, mainMethodName='respond',
                 moduleCompiler=None,
                 fileName=None,
                 settingsManager=None):

        self._settingsManager = settingsManager
        self._fileName = fileName
        self._className = className
        self._moduleCompiler = moduleCompiler
        self._mainMethodName = mainMethodName
        self._decoratorsForNextMethod = []
        self._activeMethodsList = []        # stack while parsing/generating
        self._finishedMethodsList = []      # store by order
        self._methodsIndex = {}      # store by name
        self._baseClass = 'Template'
        # printed after methods in the gen class def:
        self._generatedAttribs = []
        self._blockMetaData = {}
        methodCompiler = self._spawnMethodCompiler(
            mainMethodName,
            '## CHEETAH: main method generated for this template'
        )

        self._setActiveMethodCompiler(methodCompiler)

    def setting(self, key):
        return self._settingsManager.setting(key)

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
        return self._className

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
        klass = self.methodCompilerClass
        decorators = self._decoratorsForNextMethod or []
        self._decoratorsForNextMethod = []
        methodCompiler = klass(
            methodName,
            classCompiler=self,
            initialMethodComment=initialMethodComment,
            decorators=decorators,
        )
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

    def addDecorator(self, decoratorExpr):
        """Set the decorator to be used with the next method in the source.

        See _spawnMethodCompiler() and MethodCompiler for the details of how
        this is used.
        """
        self._decoratorsForNextMethod.append(decoratorExpr)

    def addAttribute(self, attribExpr):
        self._generatedAttribs.append(attribExpr)

    def addSuper(self, argsList):
        className = self._className
        methodName = self._getActiveMethodCompiler().methodName()

        argStringChunks = []
        for arg in argsList:
            chunk = arg[0]
            if arg[1] is not None:
                chunk += '=' + arg[1]
            argStringChunks.append(chunk)
        argString = ','.join(argStringChunks)

        self.addFilteredChunk(
            'super({0}, self).{1}({2})'.format(className, methodName, argString)
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

    # code wrapping methods

    def classDef(self):
        ind = self.setting('indentationStep')
        classDefChunks = [self.classSignature()]

        classDefChunks.extend([
            ind + '#' * 50,
            ind + '## CHEETAH GENERATED METHODS',
            '\n',
            self.methodDefs(),
        ])

        classDefChunks.extend([
            ind + '#' * 50,
            ind + '## CHEETAH GENERATED ATTRIBUTES',
            '\n',
            self.attributes(),
        ])

        classDef = '\n'.join(classDefChunks)
        return classDef

    def classSignature(self):
        return 'class {0}({1}):'.format(self.className(), self._baseClass)

    def methodDefs(self):
        methodDefs = [methGen.methodDef() for methGen in self._finishedMethods()]
        return '\n\n'.join(methodDefs)

    def attributes(self):
        attribs = [
            self.setting('indentationStep') + five.text(attrib)
            for attrib in self._generatedAttribs
        ]
        return '\n\n'.join(attribs)


##################################################
# MODULE COMPILERS


class LegacyCompiler(SettingsManager, GenUtils):
    parserClass = LegacyParser
    classCompilerClass = ClassCompiler

    def __init__(self, source, moduleName, settings=None):
        super(LegacyCompiler, self).__init__()
        if settings:
            self.updateSettings(settings)

        self._moduleName = moduleName
        self._mainClassName = moduleName

        assert isinstance(source, five.text), 'the yelp-cheetah compiler requires text, not bytes.'

        if source == '':
            warnings.warn("You supplied an empty string for the source!", )

        self._parser = self.parserClass(source, compiler=self)
        self._activeClassesList = []
        self._finishedClassesList = []  # listed by ordered
        self._finishedClassIndex = {}  # listed by name
        self._importStatements = [
            'from Cheetah.DummyTransaction import DummyTransaction',
            'from Cheetah.NameMapper import NotFound',
            'from Cheetah.NameMapper import valueForName as VFN',
            'from Cheetah.NameMapper import valueFromSearchList as VFSL',
            'from Cheetah.NameMapper import valueFromFrameOrSearchList as VFFSL',
            'from Cheetah.Template import NO_CONTENT',
            'from Cheetah.Template import Template',
        ]

        self._moduleConstants = []

        self._importedVarNames = [
            'DummyTransaction',
            'NotFound',
            'Template',
        ]

    def __getattr__(self, name):
        """Provide one-way access to the methods and attributes of the
        ClassCompiler, and thereby the MethodCompilers as well.
        """
        return getattr(self._activeClassesList[-1], name)

    def _initializeSettings(self):
        self.updateSettings(copy.deepcopy(DEFAULT_COMPILER_SETTINGS))

    def _spawnClassCompiler(self, className):
        return self.classCompilerClass(
            className,
            moduleCompiler=self,
            mainMethodName=self.setting('mainMethodName'),
            settingsManager=self,
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

    def setBaseClass(self, baseClassName):
        self.setMainMethodName(self.setting('mainMethodNameForSubclasses'))

        if baseClassName in self.importedVarNames():
            raise AssertionError(
                'yelp_cheetah only supports extends by module name'
            )

        # If the #extends directive contains a classname or modulename that isn't
        # in self.importedVarNames() already, we assume that we need to add
        # an implied 'from ModName import ClassName' where ModName == ClassName.
        # - We also assume that the final . separates the classname from the
        #   module name.  This might break if people do something really fancy
        #   with their dots and namespaces.
        chunks = baseClassName.split('.')
        if len(chunks) == 1:
            self._getActiveClassCompiler().setBaseClass(baseClassName)
            modName = baseClassName
            # we assume the class name to be the module name
            # and that it's not a builtin:
            importStatement = 'from {0} import {1}'.format(
                modName, baseClassName
            )
            self.addImportStatement(importStatement)
            self.addImportedVarNames((baseClassName,))
        else:
            modName, finalClassName = '.'.join(chunks[:-1]), chunks[-1]
            # if finalClassName != chunks[:-1][-1]:
            if finalClassName != chunks[-2]:
                # we assume the class name to be the module name
                modName = '.'.join(chunks)
            self._getActiveClassCompiler().setBaseClass(finalClassName)
            importStatement = "from %s import %s" % (modName, finalClassName)
            self.addImportStatement(importStatement)
            self.addImportedVarNames([finalClassName])

    def setCompilerSettings(self, settingsStr):
        self.updateSettingsFromConfigStr(settingsStr)
        self._parser.configureParser()

    def addModuleGlobal(self, line):
        """Adds a line of global module code.  It is inserted after the import
        statements and Cheetah default module constants.
        """
        self._moduleConstants.append(line)

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
        self._getActiveClassCompiler().addAttribute(attribName + ' =' + expr)

    def addComment(self, comm):
        if re.match(r'#+$', comm):      # skip bar comments
            return

        for line in comm.splitlines():
            self.addMethComment(line)

    # methods for module code wrapping

    def getModuleCode(self):
        classCompiler = self._spawnClassCompiler(self._mainClassName)
        self._addActiveClassCompiler(classCompiler)
        self._parser.parse()
        self._swallowClassCompiler(self._popActiveClassCompiler())

        futures = ''
        if self.setting('future_unicode_literals'):
            futures += 'from __future__ import unicode_literals\n'

        moduleDef = textwrap.dedent(
            """
            %(futures)s
            %(imports)s

            # This is compiled yelp_cheetah sourcecode
            __YELP_CHEETAH__ = True

            %(constants)s

            %(classes)s

            %(footer)s
            """
        ).strip() % {
            'futures': futures,
            'imports': self.importStatements(),
            'constants': self.moduleConstants(),
            'classes': self.classDefs(),
            'footer': self.moduleFooter(),
            'mainClassName': self._mainClassName,
        }

        return moduleDef

    def importStatements(self):
        return '\n'.join(self._importStatements)

    def moduleConstants(self):
        return '\n'.join(self._moduleConstants)

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
