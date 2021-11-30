[![Build Status](https://github.com/Yelp/yelp_cheetah/workflows/main/badge.svg)](https://github.com/Yelp/yelp_cheetah/actions)

yelp_cheetah
============

Cheetah is an open source template engine and code generation tool.

yelp_cheetah is cheetah with everything we don't / shouldn't use removed.

Differences
================================================================================

## 0.19.1
- Fix build on pypy.

## 0.19.0
- Add error message for missing partial template `#extends` under test.
- Fix warnings in python3+.
- Drop support for python 2.
- Build abi3 wheels.

## 0.18.0
- Some optimizations of list comprehensions
- Lookup speed improvements
- Remove `enable_auto_self` setting (always `False`)
- Remove `useNameMapper` setting (always `True`)
- Add an `auto_self` kwarg to `getVar` and `varExists` defaulting to `True`
  (will default to `False` and be removed in a future version).

## 0.17.0
- `enable_auto_self` setting now defaults to `False`
- Lookup involving partial templates calling partial templates is now
  optimized.

## 0.16.1
- Add a parsing hook for cheetah variables

## 0.16.0
- `$foo()bar` no longer compiles to `foo.bar`
- gettext parsing was removed -- it never worked properly.  To get gettext
  scannable compiled output, create a compiler, augment `._global_vars` with
  the gettext functions.
- `$()` and `$[]` are now syntax errors -- use `${}` instead
- `${ foo }` is now a syntax error -- placeholders cannot start with whitespace
- Escaped newlines in expressions are preserved
- Bug with comments in a multi-line expression fixed
- Fix several parsing issues around expressions
- Fix several parsing issues around `#def`

## 0.15.2
- Add an `enable_auto_self` setting (defaulted to `True`) which (when enabled)
  means `$foo` can mean either `self.foo` or `NS['foo']` (the behaviour prior
  to this version).  In future versions, this will default to `False` and will
  eventually be eliminated.

## 0.15.1
- Introduce unused functions for lookup.  These will be used for backwards /
  forwards compatibility in the next release.

## 0.15.0
- Remove `#call` directive (port to `#with` instead)

## 0.14.0
- Use `io.StringIO` as a replacement for `DummyTransaction`
- Drop python2.6 support

## 0.13.2
- Require six>=1.4.0 (for six.PY2)

## 0.13.1
- Add setuptools extension to build templates.  To use add
  `setup_requires=['yelp-cheetah']` and `yelp_cheetah={'directories': [...]}`
  to automatically build templates in a package on installation.

## 0.13.0
- Remove `#set` and `#silent` (replaced by `#py`)

## 0.12.1
- Fix regression introduced in 0.11.0: `$self.getVar('contains_underscore')`

## 0.12.0
- Fix regression introduced in 0.11.0: `[$x for x in ...]`

## 0.11.0
- Remove instrumentation added in 0.10.0
- Remove `useAutocalling` setting (always False)
- Remove `useDottedNotation` setting (always False)
- Remove `mainMethodName` setting (always respond)
- Remove `mainMethodNameForSubclasses` setting (always writeBody)
- Remove `valueForName` (now unused)
- Implement ContextManagerPartialTemplateTestCase
- Template now only takes a single argument `namespace` instead of searchList
- Support pypy for real
- Template.getVar / Template.varExists no longer support dots

## 0.10.0
- Added instrumentation to migrate away from autocall / autokey

## 0.9.0
- Tests pass under pypy (still slow)
- "Blinged" kwargs no longer supported: `$foo($bar='baz') => $foo(bar='baz')`

## 0.8.0
- `#filter` directive is gone.  Use `self.set_filter(filter_fn)`
- `Template`'s signature is now `Template(search_list, filter_fn)`
- All templates now have `from __future__ import absolute_import`

## 0.7.0
- removed macro support: use `#with` instead.
- much-improved support for context managers.
- Raise on unknown settings
- Remove settings: `cheetahVarStartToken`, `commentStartToken`, `directiveStartToken`, `directiveEndToken`
- Fix indexing a return value #23
- Add `#py` directive.  This will replace `#silent` and `#set` in a future version
- Remove `<% ... %>`
- Optimize lookup of builtins, globals, and locals when detected.

## 0.6.0
- Cheetah classes now invariantly have `YelpCheetahTemplate` as the classname
- Variable lookup is now `locals()`, `globals()`, `builtins`, `self`, `searchList`
- `#extends` no longer supports `#extends foo.foo` and should instead be `#extends foo`

## 0.5.0
- `**KWS` is no longer added to every template method definition

## 0.4.1
- Scan gettext variables in attributes `$translator.gettext(...)`
- Scan more types of gettext variables (`gettext`, `pgettext`, `npgettext`).
- Remove some runtime overhead of gettext variables

## 0.4.0
- Remove dollarsigns on `for` lvalues
- Remove `#set global` directive
- Remove `future_unicode_literals` setting
- Disallow dollarsigns in `getVar` / `varExists`

## 0.3.5
- Do not create `__init__.py` in `__pycache__` directories

## 0.3.4
- Invariantly create `__init__.py` in subdirectories

## 0.3.3
- dep argparse

## 0.3.2
- `cheetah-compile` takes directories

## 0.3.1
- Fix partial template testing infrastructure

## 0.3.0
- Disallow dollarsigns on `#def` / `#block` name
- Disallow dollarsigns in function signatures
- Require argspec for `#def`
- Requres no argspec for `#block`
- Require no dollarsign in `#set` lvalue
- Disallow dollarsigns in macro arguments
- Disallow dollarsigns in `#attr` lvalue
- Forbid `@classmethod` / `@staticmethod`
- Remove `#set module` directive
- Add testing infrastructure for partial template testing

## 0.2.1
- Add `compile_directories`

## 0.2.0
- Add `#with` directive
- **100% test coverage**

## 0.1.4
- Make filters simple functions instead of classes
- Add and make default `markupsafe` filter

## 0.1.3
- Add `Cheetah.partial_template`, a system for importable template functions.

## 0.1.2
- Rename `Cheetah.Compiler` and `Cheetah.Parser` to `Cheetah.legacy_compiler` and `Cheetah.legacy_parser`
- Remove `#encoding` directive, cheetah source is now invariantly `UTF-8`

## 0.1.1
- Raise on unknown macros
- Remove `#echo` directive
- Remove `#* ... *#` multiline comment syntax
- Remove version checking code
- Remove `#arg` directive
- Remove `#closure` directive
- Make compilation output deterministic
- Remove `<%=...%>`
- Remove ability to specify argspecs in `#implements`
- Remove multiple inheritance from `#extends`
- Remove `#compiler` directive
- Remove global imports: (`sys`, `os`, `os.path`, `builtin`, `getmtime`, `exists`, `types`)
- Default `useDottedNotation` to false
- Remove `allowNestedDefScopes` setting
- Remove `useSearchList` setting
- Remove `useKWsForPassingTrans` setting
- Remove `alwaysFilterNone` setting
- Remove cheetah ternary `#if ... then ... else ...` directive
- Remove `namespace` argument from `Template.__init__`
- **Support Python 3**
- Expose a global `__YELP_CHEETAH__ = True` in compiled source
- Remove `autoImportForExtends` setting (always True)
- Disable `#extends` of an imported name
- Add setting `future_unicode_literals` for toggling `unicode_literals` in compiled source

## 0.1.0
- Removed Cheetah Analyzer
- Removed textmate highlight support
- Remove logging of placeholders
- Remove Django support
- Make useAutoCalling default to False
- Remove `#cache` directive
- Remove Mondo
- Remove RecursiveNull
- Remove SiteHierarchy
- Remove turbocheetah
- Remove Servlet
- Remove silent placeholders (`$!placeholder`)
- Remove `#errorCatcher` directive
- Remove WebWare support
- Remove FileUtils
- Remove hasName
- Remove Indenter
- Remove `#indent` directive
- Remove cheetah eval `c'$var'` syntax
- Remove import hook, live compiling, compilation cache
- Remove CheetahWrapper
- Remove `#I18n` macro
- Improve cmdline interface
- Remove several magical imports (`time`, `currentTime`, etc.)
- Remove `#unicode` directive
- Remove `#breakpoint` directive
- Remove `#unless` directive
- Remove `#repeat` directive
- Remove `#capture` directive
- Improve compiling interface.  There are now three functions: (`compile_source`, `compile_file`, `compile_to_class`)
- Remove `#defmacro` directive
- Remove `#include` directive
- Remove `getFileContents`
- Remove preprocessors
- Remove `addSrcTimeToOutput` setting
- Remove `disabledDirectives` setting
- Remove `pre` / `post` `ParseDirective` hooks
- Remove placeholder hooks
- Remove expression hooks
- Remove `I18NFunctionName`
- Remove `EmptySingleLineMethods` setting
- Remove `allowWhitespaceAfterDirectiveStartToken`
- Remove `templateMetaclass` setting
- Require `unicode` for compiling source
- Remove `#transform` directive
- Remove `Websafe`, `Markdown`, `CodeHighlight`, `Maxlen`, `Strip` filters
- Remove aliases for `BaseFilter`
- Remove `namespaces` argument for `Template` constructor
- Remove `#stop` directive
- Remove `useFilters` setting (always True)
- Remove `allowPlaceholderFilterArgs` setting
- Remove `encoding` setting
- Remove `EOLSlurp` feature
- Remove `#raw` directive
- Remove C implementation of filters
- Remove `outputMethodsBeforeAttributes` setting
- Remove `defDocStrMsg` setting
- Remove `handlerForExtendsDirective` setting
- Remove `__str__` from all objects
- Remove support for pypy (Delete python implementation of NameMapper)
- Remove `useStackFrames` setting
- Remove `#importsettings` directive
- Remove `#compiler-settings python` directive
- Remove `safeConvert`
- Remove `*` imports
- Raise on searchlist collisions
- Fix bug with macros causing out-of-bounds when near end of source

## 0.0.1
- Correct dependencies

## 0.0.0
- Before hacking
