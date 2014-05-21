# -*- coding: utf-8 -*-

import collections
import sys

import Cheetah.compile
import Cheetah.Template
from Cheetah import five


class Parser(Cheetah.Parser.Parser):
    """This parser barfs loudly when it encounters undefined macros."""
    def _initDirectives(self):
        super(Parser, self)._initDirectives()
        # We need unrecognized directives to be seen as macros
        self._directiveNamesAndParsers[AnyString()] = self.eatMacroCall
        self._directiveNamesAndParsers = AutoDict(lambda: self.eatMacroCall, self._directiveNamesAndParsers)
        self._closeableDirectives = set(self._closeableDirectives)

    def eatMacroCall(self):
        startPos = self.pos()
        try:
            super(Parser, self).eatMacroCall()
        except KeyError:
            self.setPos(startPos)
            self.getDirectiveStartToken()
            macroName = self.getIdentifier()
            self.setPos(startPos)
            raise Cheetah.Parser.ParseError(
                self,
                msg=(
                    'Bad macro name: "{0}". '
                    'You may want to escape that # sign?'.format(macroName)
                ),
            )


class Compiler(Cheetah.Compiler.Compiler):
    parserClass = Parser


class AnyString(unicode):
    """Represents "any string"."""
    def startswith(self, other):
        return True

    def __eq__(self, other):
        return True


class AutoDict(collections.defaultdict):
    "Like defaultdict, but auto-populates for .get() as well."
    no_default = []

    def get(self, key, default=no_default):
        if default is self.no_default:
            return self[key]
        else:
            return super(AutoDict, self).get(key, default)

    def __contains__(self, key):
        return True


CHEETAH_OPTS = dict(
    allowNestedDefScopes=False,
    # This strange fellow makes template functions write to the current buffer,
    # rather than returning a flattened string (and losing the Markup blessing)
    autoAssignDummyTransactionToSelf=True,
    # These are the cretins responsible for magically resolving $foo.bar as
    # foo['bar'] and $self.foo as self.foo().
    useAutocalling=False,
    useDottedNotation=False,
)


def compile_template(filename):
    if not isinstance(filename, five.text):
        filename = filename.decode('utf-8')

    Cheetah.compile.compile_file(
        filename,
        settings=CHEETAH_OPTS,
        compiler_cls=Compiler,
    )


def compile_all(filenames):
    for filename in filenames:
        compile_template(filename)


def main():
    compile_all(sys.argv[1:])


if __name__ == '__main__':
    exit(main())
