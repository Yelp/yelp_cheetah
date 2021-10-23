'''
    Compiler classes for Cheetah:
    Compiler
    ClassCompiler
    MethodCompiler

    If you are trying to grok this code start with Compiler.__init__,
    Compiler.compile, and Compiler.__getattr__.
'''
import ast
import builtins
import contextlib
import copy
import re
import textwrap
import warnings

from Cheetah.ast_utils import get_argument_names
from Cheetah.ast_utils import get_imported_names
from Cheetah.ast_utils import get_lvalues
from Cheetah.legacy_parser import brace_ends
from Cheetah.legacy_parser import brace_starts
from Cheetah.legacy_parser import CheetahVar
from Cheetah.legacy_parser import LegacyParser
from Cheetah.SettingsManager import SettingsManager


INDENT = 4 * ' '


BUILTIN_NAMES = frozenset(dir(builtins))


DEFAULT_COMPILER_SETTINGS = {
    # All #import statements are hoisted to the top of the module
    'useLegacyImportMode': True,
}

CLASS_NAME = 'YelpCheetahTemplate'
BASE_CLASS_NAME = 'YelpCheetahBaseClass'


UNESCAPE_NEWLINES = re.compile(r'(?<!\\)((\\\\)*)\\n')


def _cheetah_var_to_text(var, local_vars, global_vars):
    if var.name in local_vars | global_vars | BUILTIN_NAMES:
        return var.name
    else:
        return f'VFNS("{var.name}", NS)'


def _process_comprehensions(expr_parts):
    """Comprehensions are a unique part of python's syntax which
    references variables earlier in the source than they are declared.
    Because of this, we need to do some pre-processing to predict local
    variables introduced by comprehensions.

    For instance, the following is "legal" cheetah syntax:

        #py y = [$x for x in (1, 2, 3) if $x]

    Naively, $x is compiled as a cheetah variable and attempts a lookup.
    However, this variable is guaranteed to come from locals.

    We'll use the python3 rules here for determining local variables.  That is
    the scope of a variable that is an lvalue in a `for ... in` comprehension
    is only the comprehension and not the rest of the function as it is in
    python2.

    The ast defines each of the comprehensions as follows:

        ListComp(expr elt, comprehension* generators)
        comprehension(expr target, expr iter, expr* ifs)

    (set / dict / generator expressions are similar)

    Consider:

        [elt_expr for x in x_iter if x_if1 if x_if2 for y in y_iter if y_if]

    Each `for ... in ...` introduces names which are available in:
        - `elt`
        - the `ifs` for that part
        - Any `for ... in ...` after that

    In the above, the expressions have the following local variables
    introduced by the comprehensions:
        - elt: [x, y]
        - x_iter: []
        - x_if1 / x_if2: [x]
        - y_iter: [x]
        - y_if: [x, y]

    The approximate algorithm:
        Search for a `for` token.
        Search left for a brace, if there is none abandon -- this is a for
            loop and not a comprehension.
        While searching left, if a `for` token is encountered, record its
            position
        Search forward for `in`, `for`, `if` and the right boundary
        Process `for ... in` + (): pass looking for introduced locals
            For example, 'for (x, y) in' will look for locals in
            `for (x, y) in (): pass` and finds `x` and `y` as lvalues
        Process tokens in `elt` and the rest of the expression (if applicable)
            For each CheetahVar encountered, if it is in the locals detected
                replace it with the raw variable
    """
    def _search(parts, index, direction):
        """Helper for searching forward / backward.
        Yields (index, token, brace_depth)
        """
        assert direction in (1, -1), direction

        def in_bounds(index):
            return index >= 0 and index < len(parts)

        if direction == 1:
            starts = brace_starts
            ends = brace_ends
        else:
            starts = brace_ends
            ends = brace_starts

        brace_depth = 0
        index += direction
        while in_bounds(index) and brace_depth >= 0:
            token = parts[index]
            if token in starts:
                brace_depth += 1
            elif token in ends:
                brace_depth -= 1
            yield index, token, brace_depth
            index += direction

    expr_parts = list(expr_parts)
    for i in range(len(expr_parts)):
        if expr_parts[i] != 'for':
            continue

        # A diagram of the below indices:
        # (Considering the first `for`)
        # [(x, y) for x in (1,) if x for y in (2,)]
        # |       |     |       |                 |
        # |       |     |       +- next_index     +- right_boundary
        # |       |     +- in_index
        # |       +- for_index + first_for_index
        # +- left_boundary
        #
        #  (Considering the second `for`)
        # [(x, y) for x in (1,) if x for y in (2,)]
        # |       |                  |     |      |
        # |       |                  |     |      +- right_boundary
        # |       +- first_for_index |     +- in_index
        # +- left_boundary           +- for_index
        # (next_index is None)

        first_for_index = for_index = i

        # Search for the left boundary or abandon (if it is a for loop)
        for i, token, depth in _search(expr_parts, for_index, direction=-1):
            if depth == 0 and token == 'for':
                first_for_index = i
            elif depth == -1:
                left_boundary = i
                break
        else:
            continue

        in_index = None
        next_index = None
        for i, token, depth in _search(expr_parts, for_index, direction=1):
            if in_index is None and depth == 0 and token == 'in':
                in_index = i
            elif next_index is None and depth == 0 and token in {'if', 'for'}:
                next_index = i
            elif depth == -1:
                right_boundary = i
                break
        else:
            raise AssertionError('unreachable')

        # Defensive assertion is required, slicing with [:None] is valid
        assert in_index is not None, in_index
        lvalue_expr = ''.join(expr_parts[for_index:in_index]) + 'in (): pass'
        lvalue_expr = lvalue_expr.replace('\n', ' ')
        lvalues = get_lvalues(lvalue_expr)

        replace_ranges = [range(left_boundary, first_for_index)]
        if next_index is not None:
            replace_ranges.append(range(next_index, right_boundary))

        for replace_range in replace_ranges:
            for i in replace_range:
                token = expr_parts[i]
                if isinstance(token, CheetahVar) and token.name in lvalues:
                    expr_parts[i] = token.name

    return tuple(expr_parts)


def _expr_to_text(expr_parts, **kwargs):
    expr_parts = _process_comprehensions(expr_parts)
    return ''.join(
        _cheetah_var_to_text(part, **kwargs)
        if isinstance(part, CheetahVar) else
        part
        for part in expr_parts
    )


def _prepare_argspec(argspec):
    argspec = 'self, ' + argspec if argspec else 'self'
    return argspec, get_argument_names(argspec)


class MethodCompiler:
    def __init__(
            self,
            methodName,
            class_compiler,
            argspec,
            initialMethodComment,
            decorators=None,
    ):
        self._methodName = methodName
        self._class_compiler = class_compiler
        self._initialMethodComment = initialMethodComment
        self._indentLev = 2
        self._pendingStrConstChunks = []
        self._methodBodyChunks = []
        self._hasReturnStatement = False
        self._isGenerator = False
        self._argspec, self._local_vars = _prepare_argspec(argspec)
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
        self.addChunk(f'self.transaction.write({chunk})')

    def addFilteredChunk(self, chunk, rawExpr=None, lineCol=None):
        if rawExpr and rawExpr.find('\n') == -1 and rawExpr.find('\r') == -1:
            self.addChunk(f'_v = {chunk} # {rawExpr!r}')
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
        body = UNESCAPE_NEWLINES.sub('\\1\n', reprstr[1:-1])

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
        self.appendToPrevChunk(
            ' # generated from line {}, col {}.'.format(*line_col),
        )

    def _update_locals(self, expr):
        self._local_vars.update(get_lvalues(expr))

    def _expr_to_text(self, expr):
        return _expr_to_text(
            expr,
            local_vars=self._local_vars,
            global_vars=self._class_compiler._compiler._global_vars,
        )

    def addPlaceholder(self, expr, rawPlaceholder, line_col):
        expr = self._expr_to_text(expr).lstrip()
        assert ast.parse(expr)
        self.addFilteredChunk(expr, rawPlaceholder, line_col)
        self._append_line_col_comment(line_col)

    def _add_with_line_col(self, expr, line_col):
        expr = self._expr_to_text(expr).lstrip()
        self._update_locals(expr)
        self.addChunk(expr)
        self._append_line_col_comment(line_col)

    addAssert = addBreak = addContinue = addDel = addPass = _add_with_line_col
    addPy = addRaise = _add_with_line_col

    def addReturn(self, expr, line_col):
        assert not self._isGenerator
        self._hasReturnStatement = True
        self._add_with_line_col(expr, line_col)

    def addYield(self, expr, line_col):
        assert not self._hasReturnStatement
        self._isGenerator = True
        self._add_with_line_col(expr, line_col)

    def _add_indenting_directive(self, expr, line_col):
        expr = self._expr_to_text(expr)
        assert expr[-1] != ':'
        expr = expr + ':'
        self.addChunk(expr)
        self._append_line_col_comment(line_col)
        self.indent()

    addWhile = addIf = addTry = _add_indenting_directive

    def _add_lvalue_indenting_directive(self, expr, line_col):
        expr = self._expr_to_text(expr)
        self._update_locals(expr + ':\n    pass')
        self._add_indenting_directive(expr, line_col)

    addFor = addWith = _add_lvalue_indenting_directive

    def addReIndentingDirective(self, expr, line_col):
        assert expr[-1] != ':'
        expr = expr + ':'

        self.addChunk(expr)
        self._append_line_col_comment(line_col)
        self.indent()

    def addFinally(self, expr, line_col):
        expr = self._expr_to_text(expr)
        self.addReIndentingDirective(expr, line_col)

    def addExcept(self, expr, line_col):
        expr = self._expr_to_text(expr)
        self._update_locals('try:\n    pass\n' + expr + ':\n    pass')
        self.addReIndentingDirective(expr, line_col)

    def addElse(self, expr, line_col):
        expr = self._expr_to_text(expr)
        expr = re.sub('else +if', 'elif', expr)
        self.addReIndentingDirective(expr, line_col)

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

    def methodSignature(self):
        return ''.join((
            ''.join(
                INDENT + decorator + '\n' for decorator in self._decorators
            ),
            INDENT + 'def ' + self.methodName() + '(' + self._argspec + '):',
        ))


class ClassCompiler:
    methodCompilerClass = MethodCompiler

    def __init__(self, main_method_name, compiler):
        self._compiler = compiler
        self._mainMethodName = main_method_name
        self._decoratorsForNextMethod = []
        self._activeMethodsList = []        # stack while parsing/generating
        self._attrs = []
        self._finishedMethodsList = []      # store by order

        self._main_method = self._spawnMethodCompiler(
            main_method_name,
            '',
            '## CHEETAH: main method generated for this template',
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

    def _spawnMethodCompiler(self, methodName, argspec, initialMethodComment):
        methodCompiler = self.methodCompilerClass(
            methodName,
            class_compiler=self,
            argspec=argspec,
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

    startMethodDef = _spawnMethodCompiler

    def addDecorator(self, decorator_expr):
        """Set the decorator to be used with the next method in the source.

        See _spawnMethodCompiler() and MethodCompiler for the details of how
        this is used.
        """
        self._decoratorsForNextMethod.append(decorator_expr)

    def addAttribute(self, attr_expr):
        self._attrs.append(attr_expr)

    def addSuper(self, argspec):
        methodName = self._getActiveMethodCompiler().methodName()
        self.addFilteredChunk(
            f'super({CLASS_NAME}, self).{methodName}({argspec})',
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
        self.addChunk(f'self.{methodName}()')

    def class_def(self):
        return '\n'.join((
            f'class {CLASS_NAME}({BASE_CLASS_NAME}):\n',
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
        super().__init__()
        if settings:
            self.updateSettings(settings)

        assert isinstance(source, str), 'the yelp-cheetah compiler requires text, not bytes.'

        if source == '':
            warnings.warn('You supplied an empty string for the source!')

        self._original_source = source
        self._parser = self.parserClass(source, compiler=self)
        self._class_compiler = None
        self._base_import = 'from Cheetah.Template import {} as {}'.format(
            CLASS_NAME, BASE_CLASS_NAME,
        )
        self._importStatements = [
            'import io',
            'from Cheetah.NameMapper import value_from_namespace as VFNS',
            'from Cheetah.Template import NO_CONTENT',
        ]
        self._global_vars = {'io', 'NO_CONTENT', 'VFNS'}

    def __getattr__(self, name):
        """Provide one-way access to the methods and attributes of the
        ClassCompiler, and thereby the MethodCompilers as well.
        """
        return getattr(self._class_compiler, name)

    def _initializeSettings(self):
        self._settings = copy.deepcopy(DEFAULT_COMPILER_SETTINGS)

    def _spawnClassCompiler(self):
        return self.classCompilerClass(
            main_method_name='respond', compiler=self,
        )

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
            if raw_statement and self._methodBodyChunks:
                self.addChunk(raw_statement)
        else:
            self._global_vars.update(varNames)

    # methods for adding stuff to the module and class definitions

    def set_extends(self, extends_name):
        self.setMainMethodName('writeBody')

        if extends_name in self._global_vars:
            raise AssertionError(
                'yelp_cheetah only supports extends by module name',
            )

        self._base_import = 'from {} import {} as {}'.format(
            extends_name, CLASS_NAME, BASE_CLASS_NAME,
        )

        # TODO(#183): stop using the metaclass and just generate functions
        # Partial templates expose their functions as globals, find all the
        # defined functions and add them to known global vars.
        if extends_name == 'Cheetah.partial_template':
            self._global_vars.update(
                get_defined_method_names(self._original_source),
            )

    def add_compiler_settings(self):
        settings_str = self.getStrConst()
        self.clearStrConst()
        self.updateSettingsFromConfigStr(settings_str)

    def _add_import_statement(self, expr, line_col):
        imp_statement = ''.join(expr)
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
            if __name__ == '__main__':
                from os import environ
                from sys import stdout
                stdout.write({class_name}(namespace=environ).respond())
            """,
        ).strip().format(
            imports='\n'.join(self._importStatements),
            base_import=self._base_import,
            class_def=class_compiler.class_def(),
            class_name=CLASS_NAME,
        ) + '\n'

        return moduleDef


def get_defined_method_names(original_source):
    class CollectsMethodNamesCompiler:
        def __init__(self):
            self.method_names = set()

        # Trivially allow anything outside of startMethodDef
        def __getattr__(self, name):
            return lambda *args, **kwargs: None

        # Collect our function names
        def startMethodDef(self, method_name, *args):
            self.method_names.add(method_name)

    compiler = CollectsMethodNamesCompiler()
    LegacyParser(original_source, compiler=compiler).parse()
    return compiler.method_names
