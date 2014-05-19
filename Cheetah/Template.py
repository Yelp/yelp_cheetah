'''
Provides the core API for Cheetah.

See the docstring in the Template class and the Users' Guide for more information
'''

################################################################################
# DEPENDENCIES
import sys                        # used in the error handling code
import re                         # used to define the internal delims regex
import logging
import os.path
import time
import io
import StringIO
import traceback
import types
from random import randrange

try:
    from threading import Lock
except ImportError:
    class Lock:
        def acquire(self):
            pass

        def release(self):
            pass

if isinstance(sys.version_info[:], tuple):
    def createMethod(func, cls):
        return types.MethodType(func, None, cls)
else:
    def createMethod(func, cls):
        return types.MethodType(func, cls)


from Cheetah.Version import convertVersionStringToTuple, MinCompatibleVersionTuple
from Cheetah.Version import MinCompatibleVersion
# More intra-package imports ...
from Cheetah.Parser import ParseError, SourceReader
from Cheetah.Compiler import Compiler
from Cheetah import Filters                    # the output filters
from Cheetah.convertTmplPathToModuleName import convertTmplPathToModuleName
from Cheetah.NameMapper import NotFound, valueFromSearchList
from Cheetah.Unspecified import Unspecified

# Decide whether to use the file modification time in file's cache key
__checkFileMtime = True


def checkFileMtime(value):
    globals()['__checkFileMtime'] = value


def hashList(l):
    hashedList = []
    for v in l:
        if isinstance(v, dict):
            v = hashDict(v)
        elif isinstance(v, list):
            v = hashList(v)
        hashedList.append(v)
    return hash(tuple(hashedList))


def hashDict(d):
    items = sorted(d.items())
    hashedList = []
    for k, v in items:
        if isinstance(v, dict):
            v = hashDict(v)
        elif isinstance(v, list):
            v = hashList(v)
        hashedList.append((k, v))
    return hash(tuple(hashedList))


################################################################################
# MODULE GLOBALS AND CONSTANTS

# Singleton object, representing no data to be written.
# None or empty-string can be filtered into useful data, unlike NO_CONTENT.
NO_CONTENT = object()


def _genUniqueModuleName(baseModuleName):
    """The calling code is responsible for concurrency locking.
    """
    if baseModuleName not in sys.modules:
        finalName = baseModuleName
    else:
        finalName = ('cheetah_%s_%s_%s' % (baseModuleName,
                                           str(time.time()).replace('.', '_'),
                                           str(randrange(10000, 99999))))
    return finalName


def updateLinecache(filename, src):
    import linecache
    size = len(src)
    mtime = time.time()
    lines = src.splitlines()
    fullname = filename
    linecache.cache[filename] = size, mtime, lines, fullname


class CompileCacheItem(object):
    pass


class Template(object):
    '''
    This class provides a) methods used by templates at runtime and b)
    methods for compiling Cheetah source code into template classes.

    This documentation assumes you already know Python and the basics of object
    oriented programming.  If you don't know Python, see the sections of the
    Cheetah Users' Guide for non-programmers.  It also assumes you have read
    about Cheetah's syntax in the Users' Guide.

    The following explains how to use Cheetah from within Python programs or via
    the interpreter. If you statically compile your templates on the command
    line using the 'cheetah' script, this is not relevant to you. Statically
    compiled Cheetah template modules/classes (e.g. myTemplate.py:
    MyTemplateClasss) are just like any other Python module or class. Also note,
    most Python web frameworks (Webware, Aquarium, mod_python, Turbogears,
    CherryPy, Quixote, etc.) provide plugins that handle Cheetah compilation for
    you.

    There are several possible usage patterns:
       1) tclass = Template.compile(src)
          t1 = tclass() # or tclass(namespaces=[namespace,...])
          t2 = tclass() # or tclass(namespaces=[namespace2,...])
          outputStr = str(t1) # or outputStr = t1.aMethodYouDefined()

          Template.compile provides a rich and very flexible API via its
          optional arguments so there are many possible variations of this
          pattern.  One example is:
            tclass = Template.compile('hello $name from $caller', baseclass=dict)
            print tclass(name='world', caller='me')
          See the Template.compile() docstring for more details.

       2) tmplInstance = Template(src)
             # or Template(src, namespaces=[namespace,...])
          outputStr = str(tmplInstance) # or outputStr = tmplInstance.aMethodYouDefined(...args...)

    Notes on the usage patterns:

       usage pattern 1)
          This is the most flexible, but it is slightly more verbose unless you
          write a wrapper function to hide the plumbing.  Under the hood, all
          other usage patterns are based on this approach.  Templates compiled
          this way can #extend (subclass) any Python baseclass: old-style or
          new-style (based on object or a builtin type).

       usage pattern 2)
          This was Cheetah's original usage pattern.  It returns an instance,
          but you can still access the generated class via
          tmplInstance.__class__.  If you want to use several different
          namespace 'searchLists' with a single template source definition,
          you're better off with Template.compile (1).

          Limitations (use pattern 1 instead):
           - Templates compiled this way can only #extend subclasses of the
             new-style 'object' baseclass.  Cheetah.Template is a subclass of
             'object'.  You also can not #extend dict, list, or other builtin
             types.
           - If your template baseclass' __init__ constructor expects args there
             is currently no way to pass them in.

    If you need to subclass a dynamically compiled Cheetah class, do something like this:
        from Cheetah.Template import Template
        T1 = Template.compile('$meth1 #def meth1: this is meth1 in T1')
        T2 = Template.compile('#implements meth1\nthis is meth1 redefined in T2', baseclass=T1)
        print T1, T1()
        print T2, T2()


    Note about class and instance attribute names:
      Attributes used by Cheetah have a special prefix to avoid confusion with
      the attributes of the templates themselves or those of template
      baseclasses.

      Class attributes which are used in class methods look like this:
          klass._CHEETAH_useCompilationCache (_CHEETAH_xxx)

      Instance attributes look like this:
          klass._CHEETAH__globalSetVars (_CHEETAH__xxx with 2 underscores)
    '''

    # this is used by ._addCheetahPlumbingCodeToClass()
    _CHEETAH_requiredCheetahMethods = (
        '_initCheetahInstance',
        'searchList',
        'getVar',
        'varExists',
        'getFileContents',
        'generatedClassCode',
        'generatedModuleCode',
    )
    _CHEETAH_requiredCheetahClassMethods = ('subclass',)

    # the following are used by .compile(). Most are documented in its docstring.
    _CHEETAH_cacheModuleFilesForTracebacks = False
    _CHEETAH_cacheDirForModuleFiles = None  # change to a dirname

    _CHEETAH_compileCache = dict()  # cache store for compiled code and classes
    # To do something other than simple in-memory caching you can create an
    # alternative cache store. It just needs to support the basics of Python's
    # mapping/dict protocol. E.g.:
    #   class AdvCachingTemplate(Template):
    #       _CHEETAH_compileCache = MemoryOrFileCache()
    _CHEETAH_compileLock = Lock()  # used to prevent race conditions
    _CHEETAH_defaultMainMethodName = None
    _CHEETAH_compilerSettings = None
    _CHEETAH_compilerClass = Compiler
    _CHEETAH_compilerInstance = None
    _CHEETAH_cacheCompilationResults = True
    _CHEETAH_useCompilationCache = True
    _CHEETAH_keepRefToGeneratedCode = True
    _CHEETAH_defaultBaseclassForTemplates = None
    _CHEETAH_defaultClassNameForTemplates = None
    # defaults to DEFAULT_COMPILER_SETTINGS['mainMethodName']:
    _CHEETAH_defaultMainMethodNameForTemplates = None
    _CHEETAH_defaultModuleNameForTemplates = 'DynamicallyCompiledCheetahTemplate'
    _CHEETAH_defaultModuleGlobalsForTemplates = None

    # The following attributes are used by instance methods:
    _CHEETAH_generatedModuleCode = None

    @classmethod
    def _getCompilerClass(klass, source=None, file=None):
        return klass._CHEETAH_compilerClass

    @classmethod
    def _getCompilerSettings(klass, source=None, file=None):
        return klass._CHEETAH_compilerSettings

    @classmethod
    def compile(klass, source=None, file=None,
                returnAClass=True,

                compilerSettings=Unspecified,
                compilerClass=Unspecified,
                moduleName=None,
                className=Unspecified,
                mainMethodName=Unspecified,
                baseclass=Unspecified,
                moduleGlobals=Unspecified,
                cacheCompilationResults=Unspecified,
                useCache=Unspecified,
                cacheModuleFilesForTracebacks=Unspecified,
                cacheDirForModuleFiles=Unspecified,
                commandlineopts=None,
                keepRefToGeneratedCode=Unspecified,
                ):

        """
        The core API for compiling Cheetah source code into template classes.

        This class method compiles Cheetah source code and returns a python
        class.  You then create template instances using that class.  All
        Cheetah's other compilation API's use this method under the hood.

        Internally, this method a) parses the Cheetah source code and generates
        Python code defining a module with a single class in it, b) dynamically
        creates a module object with a unique name, c) execs the generated code
        in that module's namespace then inserts the module into sys.modules, and
        d) returns a reference to the generated class.  If you want to get the
        generated python source code instead, pass the argument
        returnAClass=False.

        It caches generated code and classes.  See the descriptions of the
        arguments'cacheCompilationResults' and 'useCache' for details. This
        doesn't mean that templates will automatically recompile themselves when
        the source file changes. Rather, if you call Template.compile(src) or
        Template.compile(file=path) repeatedly it will attempt to return a
        cached class definition instead of recompiling.

        If you are an advanced user and need to customize the way Cheetah parses
        source code or outputs Python code, you should check out the
        compilerSettings argument.

        Arguments:
          You must provide either a 'source' or 'file' arg, but not both:
            - source (string or None)
            - file (string path, file-like object, or None)

          The rest of the arguments are strictly optional. All but the first
          have defaults in attributes of the Template class which can be
          overridden in subclasses of this class.  Working with most of these is
          an advanced topic.

            - returnAClass=True
              If false, return the generated module code rather than a class.

            - compilerSettings (a dict)
              Default: Template._CHEETAH_compilerSettings=None

              a dictionary of settings to override those defined in
              DEFAULT_COMPILER_SETTINGS. These can also be overridden in your
              template source code with the #compiler or #compiler-settings
              directives.

            - compilerClass (a class)
              Default: Template._CHEETAH_compilerClass=Cheetah.Compiler.Compiler

              a subclass of Cheetah.Compiler.Compiler. Mucking with this is a
              very advanced topic.

            - moduleName (a string)
              Default:
                  Template._CHEETAH_defaultModuleNameForTemplates
                  ='DynamicallyCompiledCheetahTemplate'

              What to name the generated Python module.  If the provided value is
              None and a file arg was given, the moduleName is created from the
              file path.  In all cases if the moduleName provided is already in
              sys.modules it is passed through a filter that generates a unique
              variant of the name.


            - className (a string)
              Default: Template._CHEETAH_defaultClassNameForTemplates=None

              What to name the generated Python class.  If the provided value is
              None, the moduleName is use as the class name.

            - mainMethodName (a string)
              Default:
                  Template._CHEETAH_defaultMainMethodNameForTemplates
                  =None (and thus DEFAULT_COMPILER_SETTINGS['mainMethodName'])

              What to name the main output generating method in the compiled
              template class.

            - baseclass (a string or a class)
              Default: Template._CHEETAH_defaultBaseclassForTemplates=None

              Specifies the baseclass for the template without manually
              including an #extends directive in the source. The #extends
              directive trumps this arg.

              If the provided value is a string you must make sure that a class
              reference by that name is available to your template, either by
              using an #import directive or by providing it in the arg
              'moduleGlobals'.

              If the provided value is a class, Cheetah will handle all the
              details for you.

            - moduleGlobals (a dict)
              Default: Template._CHEETAH_defaultModuleGlobalsForTemplates=None

              A dict of vars that will be added to the global namespace of the
              module the generated code is executed in, prior to the execution
              of that code.  This should be Python values, not code strings!

            - cacheCompilationResults (True/False)
              Default: Template._CHEETAH_cacheCompilationResults=True

              Tells Cheetah to cache the generated code and classes so that they
              can be reused if Template.compile() is called multiple times with
              the same source and options.

            - useCache (True/False)
              Default: Template._CHEETAH_useCompilationCache=True

              Should the compilation cache be used?  If True and a previous
              compilation created a cached template class with the same source
              code, compiler settings and other options, the cached template
              class will be returned.

            - cacheModuleFilesForTracebacks (True/False)
              Default: Template._CHEETAH_cacheModuleFilesForTracebacks=False

              In earlier versions of Cheetah tracebacks from exceptions that
              were raised inside dynamically compiled Cheetah templates were
              opaque because Python didn't have access to a python source file
              to use in the traceback:

                File "xxxx.py", line 192, in getTextiledContent
                  content = str(template(searchList=searchList))
                File "cheetah_yyyy.py", line 202, in __str__
                File "cheetah_yyyy.py", line 187, in respond
                File "cheetah_yyyy.py", line 139, in writeBody
               ZeroDivisionError: integer division or modulo by zero

              It is now possible to keep those files in a cache dir and allow
              Python to include the actual source lines in tracebacks and makes
              them much easier to understand:

               File "xxxx.py", line 192, in getTextiledContent
                 content = str(template(searchList=searchList))
               File "/tmp/CheetahCacheDir/cheetah_yyyy.py", line 202, in __str__
                 def __str__(self): return self.respond()
               File "/tmp/CheetahCacheDir/cheetah_yyyy.py", line 187, in respond
                 self.writeBody(trans=trans)
               File "/tmp/CheetahCacheDir/cheetah_yyyy.py", line 139, in writeBody
                 __v = 0/0 # $(0/0)
              ZeroDivisionError: integer division or modulo by zero

            - cacheDirForModuleFiles (a string representing a dir path)
              Default: Template._CHEETAH_cacheDirForModuleFiles=None

              See notes on cacheModuleFilesForTracebacks.
        """
        errmsg = "arg '%s' must be %s"

        if not isinstance(source, (types.NoneType, basestring)):
            raise TypeError(errmsg % ('source', 'string or None'))

        if not isinstance(file, (types.NoneType, basestring, io.IOBase)):
            raise TypeError(errmsg %
                            ('file', 'string, file-like object, or None'))

        if baseclass is Unspecified:
            baseclass = klass._CHEETAH_defaultBaseclassForTemplates
        if isinstance(baseclass, Template):
            baseclass = baseclass.__class__

        if not isinstance(baseclass, (types.NoneType, basestring, type)):
            raise TypeError(errmsg % ('baseclass', 'string, class or None'))

        if cacheCompilationResults is Unspecified:
            cacheCompilationResults = klass._CHEETAH_cacheCompilationResults

        if not isinstance(cacheCompilationResults, (int, bool)):
            raise TypeError(errmsg % ('cacheCompilationResults', 'boolean'))

        if useCache is Unspecified:
            useCache = klass._CHEETAH_useCompilationCache

        if not isinstance(useCache, (int, bool)):
            raise TypeError(errmsg % ('useCache', 'boolean'))

        if compilerSettings is Unspecified:
            compilerSettings = klass._getCompilerSettings(source, file) or {}
        if not isinstance(compilerSettings, dict):
            raise TypeError(errmsg % ('compilerSettings', 'dictionary'))

        if compilerClass is Unspecified:
            compilerClass = klass._getCompilerClass(source, file)

        if keepRefToGeneratedCode is Unspecified:
            keepRefToGeneratedCode = klass._CHEETAH_keepRefToGeneratedCode

        if not isinstance(keepRefToGeneratedCode, (int, bool)):
            raise TypeError(errmsg % ('keepReftoGeneratedCode', 'boolean'))

        if not isinstance(moduleName, (types.NoneType, basestring)):
            raise TypeError(errmsg % ('moduleName', 'string or None'))
        __orig_file__ = None
        if not moduleName:
            if file and isinstance(file, basestring):
                moduleName = convertTmplPathToModuleName(file)
                __orig_file__ = file
            else:
                moduleName = klass._CHEETAH_defaultModuleNameForTemplates

        if className is Unspecified:
            className = klass._CHEETAH_defaultClassNameForTemplates

        if not isinstance(className, (types.NoneType, basestring)):
            raise TypeError(errmsg % ('className', 'string or None'))
        className = re.sub(r'^_+', '', className or moduleName)

        if mainMethodName is Unspecified:
            mainMethodName = klass._CHEETAH_defaultMainMethodNameForTemplates

        if not isinstance(mainMethodName, (types.NoneType, basestring)):
            raise TypeError(errmsg % ('mainMethodName', 'string or None'))

        if moduleGlobals is Unspecified:
            moduleGlobals = klass._CHEETAH_defaultModuleGlobalsForTemplates

        if cacheModuleFilesForTracebacks is Unspecified:
            cacheModuleFilesForTracebacks = klass._CHEETAH_cacheModuleFilesForTracebacks

        if not isinstance(cacheModuleFilesForTracebacks, (int, bool)):
            raise TypeError(errmsg %
                            ('cacheModuleFilesForTracebacks', 'boolean'))

        if cacheDirForModuleFiles is Unspecified:
            cacheDirForModuleFiles = klass._CHEETAH_cacheDirForModuleFiles

        if not isinstance(cacheDirForModuleFiles, (types.NoneType, basestring)):
            raise TypeError(errmsg %
                            ('cacheDirForModuleFiles', 'string or None'))

        ##################################################
        # compilation, using cache if requested/possible
        baseclassValue = None
        baseclassName = None
        if baseclass:
            if isinstance(baseclass, basestring):
                baseclassName = baseclass
            elif isinstance(baseclass, type):
                # @@TR: should soft-code this
                baseclassName = 'CHEETAH_dynamicallyAssignedBaseClass_'+baseclass.__name__
                baseclassValue = baseclass

        cacheHash = None
        cacheItem = None
        if source or isinstance(file, basestring):
            compilerSettingsHash = None
            if compilerSettings:
                compilerSettingsHash = hashDict(compilerSettings)

            moduleGlobalsHash = None
            if moduleGlobals:
                moduleGlobalsHash = hashDict(moduleGlobals)

            fileHash = None
            if file:
                fileHash = str(hash(file))
                if globals()['__checkFileMtime']:
                    fileHash += str(os.path.getmtime(file))

            try:
                # @@TR: find some way to create a cacheHash that is consistent
                # between process restarts.  It would allow for caching the
                # compiled module on disk and thereby reduce the startup time
                # for applications that use a lot of dynamically compiled
                # templates.
                cacheHash = ''.join([str(v) for v in
                                     [hash(source),
                                      fileHash,
                                      className,
                                      moduleName,
                                      mainMethodName,
                                      hash(compilerClass),
                                      hash(baseclass),
                                      compilerSettingsHash,
                                      moduleGlobalsHash,
                                      hash(cacheDirForModuleFiles),
                                      ]])
            except Exception:
                # @@TR: should add some logging to this
                pass
        outputEncoding = 'ascii'
        compiler = None
        if useCache and cacheHash and cacheHash in klass._CHEETAH_compileCache:
            cacheItem = klass._CHEETAH_compileCache[cacheHash]
            generatedModuleCode = cacheItem.code
        else:
            compiler = compilerClass(source, file,
                                     moduleName=moduleName,
                                     mainClassName=className,
                                     baseclassName=baseclassName,
                                     mainMethodName=mainMethodName,
                                     settings=(compilerSettings or {}))
            compiler.compile()
            generatedModuleCode = compiler.getModuleCode()
            outputEncoding = compiler.getModuleEncoding()

        if not returnAClass:
            # This is a bit of a hackish solution to make sure we're setting the proper
            # encoding on generated code that is destined to be written to a file
            if not outputEncoding == 'ascii':
                generatedModuleCode = generatedModuleCode.split('\n')
                generatedModuleCode.insert(1, '# -*- coding: %s -*-' % outputEncoding)
                generatedModuleCode = '\n'.join(generatedModuleCode)
            return generatedModuleCode.encode(outputEncoding)
        else:
            if cacheItem:
                cacheItem.lastCheckoutTime = time.time()
                return cacheItem.klass

            try:
                klass._CHEETAH_compileLock.acquire()
                uniqueModuleName = _genUniqueModuleName(moduleName)
                __file__ = uniqueModuleName + '.py'  # relative file path with no dir part

                if cacheModuleFilesForTracebacks:
                    if not os.path.exists(cacheDirForModuleFiles):
                        raise Exception('%s does not exist' % cacheDirForModuleFiles)

                    __file__ = os.path.join(cacheDirForModuleFiles, __file__)
                    # @@TR: might want to assert that it doesn't already exist
                    open(__file__, 'w').write(generatedModuleCode)
                    # @@TR: should probably restrict the perms, etc.

                mod = types.ModuleType(str(uniqueModuleName))
                if moduleGlobals:
                    for k, v in moduleGlobals.items():
                        setattr(mod, k, v)
                mod.__file__ = __file__
                if __orig_file__ and os.path.exists(__orig_file__):
                    # this is used in the WebKit filemonitoring code
                    mod.__orig_file__ = __orig_file__

                if baseclass and baseclassValue:
                    setattr(mod, baseclassName, baseclassValue)

                try:
                    co = compile(generatedModuleCode, __file__, 'exec')
                    exec(co, mod.__dict__)
                except SyntaxError, e:
                    try:
                        parseError = genParserErrorFromPythonException(
                            source, file, generatedModuleCode, exception=e)
                    except:
                        updateLinecache(__file__, generatedModuleCode)
                        e.generatedModuleCode = generatedModuleCode
                        raise e
                    else:
                        raise parseError
                except Exception, e:
                    updateLinecache(__file__, generatedModuleCode)
                    e.generatedModuleCode = generatedModuleCode
                    raise

                sys.modules[uniqueModuleName] = mod
            finally:
                klass._CHEETAH_compileLock.release()

            templateClass = getattr(mod, className)

            if (
                cacheCompilationResults and
                cacheHash and
                cacheHash not in klass._CHEETAH_compileCache
            ):
                cacheItem = CompileCacheItem()
                cacheItem.cacheTime = cacheItem.lastCheckoutTime = time.time()
                cacheItem.code = generatedModuleCode
                cacheItem.klass = templateClass
                templateClass._CHEETAH_isInCompilationCache = True
                klass._CHEETAH_compileCache[cacheHash] = cacheItem
            else:
                templateClass._CHEETAH_isInCompilationCache = False

            if keepRefToGeneratedCode or cacheCompilationResults:
                templateClass._CHEETAH_generatedModuleCode = generatedModuleCode

            # If we have a compiler object, let's set it to the compiler class
            # to help the directive analyzer code
            if compiler:
                templateClass._CHEETAH_compilerInstance = compiler
            return templateClass

    @classmethod
    def subclass(klass, *args, **kws):
        """Takes the same args as the .compile() classmethod and returns a
        template that is a subclass of the template this method is called from.

          T1 = Template.compile(' foo - $meth1 - bar\n#def meth1: this is T1.meth1')
          T2 = T1.subclass('#implements meth1\n this is T2.meth1')
        """
        kws['baseclass'] = klass
        if isinstance(klass, Template):
            templateAPIClass = klass
        else:
            templateAPIClass = Template
        return templateAPIClass.compile(*args, **kws)

    @classmethod
    def _addCheetahPlumbingCodeToClass(klass, concreteTemplateClass):
        """If concreteTemplateClass is not a subclass of Cheetah.Template, add
        the required cheetah methods and attributes to it.

        This is called on each new template class after it has been compiled.
        If concreteTemplateClass is not a subclass of Cheetah.Template but
        already has method with the same name as one of the required cheetah
        methods, this will skip that method.
        """
        for methodname in klass._CHEETAH_requiredCheetahMethods:
            if not hasattr(concreteTemplateClass, methodname):
                method = getattr(Template, methodname)
                newMethod = createMethod(method.im_func, concreteTemplateClass)
                setattr(concreteTemplateClass, methodname, newMethod)

        for classMethName in klass._CHEETAH_requiredCheetahClassMethods:
            if not hasattr(concreteTemplateClass, classMethName):
                meth = getattr(klass, classMethName)
                setattr(concreteTemplateClass, classMethName, classmethod(meth.im_func))

        if (
            not hasattr(concreteTemplateClass, '__str__') or
            concreteTemplateClass.__str__ is object.__str__
        ):
            mainMethNameAttr = '_mainCheetahMethod_for_'+concreteTemplateClass.__name__
            mainMethName = getattr(concreteTemplateClass, mainMethNameAttr, None)
            if mainMethName:
                def __str__(self):
                    rc = getattr(self, mainMethName)()
                    if isinstance(rc, unicode):
                        return rc.encode('utf-8')
                    return rc

                def __unicode__(self):
                    return getattr(self, mainMethName)()
            elif hasattr(concreteTemplateClass, 'respond'):
                def __str__(self):
                    rc = self.respond()
                    if isinstance(rc, unicode):
                        return rc.encode('utf-8')
                    return rc

                def __unicode__(self):
                    return self.respond()
            else:
                def __str__(self):
                    rc = None
                    if hasattr(self, mainMethNameAttr):
                        rc = getattr(self, mainMethNameAttr)()
                    elif hasattr(self, 'respond'):
                        rc = self.respond()
                    else:
                        rc = super(self.__class__, self).__str__()
                    if isinstance(rc, unicode):
                        return rc.encode('utf-8')
                    return rc

                def __unicode__(self):
                    if hasattr(self, mainMethNameAttr):
                        return getattr(self, mainMethNameAttr)()
                    elif hasattr(self, 'respond'):
                        return self.respond()
                    else:
                        return super(self.__class__, self).__unicode__()

            __str__ = createMethod(__str__, concreteTemplateClass)
            __unicode__ = createMethod(__unicode__, concreteTemplateClass)
            setattr(concreteTemplateClass, '__str__', __str__)
            setattr(concreteTemplateClass, '__unicode__', __unicode__)

    def __init__(self, source=None,

                 namespaces=None, searchList=None,
                 # use either or.  They are aliases for the same thing.

                 file=None,
                 filter='RawOrEncodedUnicode',  # which filter from Cheetah.Filters
                 filtersLib=Filters,

                 compilerSettings=Unspecified,  # control the behaviour of the compiler
                 ):
        """a) compiles a new template OR b) instantiates an existing template.

        Read this docstring carefully as there are two distinct usage patterns.
        You should also read this class' main docstring.

        a) to compile a new template:
             t = Template(source=aSourceString)
                 # or
             t = Template(file='some/path')
                 # or
             t = Template(file=someFileObject)
                 # or
             namespaces = [{'foo':'bar'}]
             t = Template(source=aSourceString, namespaces=namespaces)
                 # or
             t = Template(file='some/path', namespaces=namespaces)

             print t

        b) to create an instance of an existing, precompiled template class:
             ## i) first you need a reference to a compiled template class:
             tclass = Template.compile(source=src) # or just Template.compile(src)
                 # or
             tclass = Template.compile(file='some/path')
                 # or
             tclass = Template.compile(file=someFileObject)

             ## ii) then you create an instance
             t = tclass(namespaces=namespaces)
                 # or
             t = tclass(namespaces=namespaces, filter='RawOrEncodedUnicode')
             print t

        Arguments:
          for usage pattern a)
            If you are compiling a new template, you must provide either a
            'source' or 'file' arg, but not both:
              - source (string or None)
              - file (string path, file-like object, or None)

            Optional args (see below for more) :
              - compilerSettings
               Default: Template._CHEETAH_compilerSettings=None

               a dictionary of settings to override those defined in
               DEFAULT_COMPILER_SETTINGS.  See
               Cheetah.Template.DEFAULT_COMPILER_SETTINGS and the Users' Guide
               for details.

            You can pass the source arg in as a positional arg with this usage
            pattern.  Use keywords for all other args.

          for usage pattern b)
            Do not use positional args with this usage pattern, unless your
            template subclasses something other than Cheetah.Template and you
            want to pass positional args to that baseclass.  E.g.:
              dictTemplate = Template.compile('hello $name from $caller', baseclass=dict)
              tmplvars = dict(name='world', caller='me')
              print dictTemplate(tmplvars)
            This usage requires all Cheetah args to be passed in as keyword args.

          optional args for both usage patterns:

            - namespaces (aka 'searchList')
              Default: None

              an optional list of namespaces (dictionaries, objects, modules,
              etc.) which Cheetah will search through to find the variables
              referenced in $placeholders.

              If you provide a single namespace instead of a list, Cheetah will
              automatically convert it into a list.

              NOTE: Cheetah does NOT force you to use the namespaces search list
              and related features.  It's on by default, but you can turn if off
              using the compiler settings useSearchList=False or
              useNameMapper=False.

             - filter
               Default: 'EncodeUnicode'

               Which filter should be used for output filtering. This should
               either be a string which is the name of a filter in the
               'filtersLib' or a subclass of Cheetah.Filters.Filter. . See the
               Users' Guide for more details.

             - filtersLib
               Default: Cheetah.Filters

               A module containing subclasses of Cheetah.Filters.Filter. See the
               Users' Guide for more details.
        """
        errmsg = "arg '%s' must be %s"
        errmsgextra = errmsg + "\n%s"

        if not isinstance(source, (types.NoneType, basestring)):
            raise TypeError(errmsg % ('source', 'string or None'))

        if not isinstance(source, (types.NoneType, basestring, io.IOBase)):
            raise TypeError(errmsg %
                            ('file', 'string, file open for reading, or None'))

        if not isinstance(filter, (basestring, types.TypeType)) and not \
                (isinstance(filter, type) and issubclass(filter, Filters.Filter)):
            raise TypeError(errmsgextra %
                            ('filter', 'string or class',
                             '(if class, must be subclass of Cheetah.Filters.Filter)'))
        if not isinstance(filtersLib, (basestring, types.ModuleType)):
            raise TypeError(errmsgextra %
                            ('filtersLib', 'string or module',
                             '(if module, must contain subclasses of Cheetah.Filters.Filter)'))

        if compilerSettings is not Unspecified:
            if not isinstance(compilerSettings, types.DictType):
                raise TypeError(errmsg %
                                ('compilerSettings', 'dictionary'))

        if source is not None and file is not None:
            raise TypeError("you must supply either a source string or the" +
                            " 'file' keyword argument, but not both")

        ##################################################
        # Do superclass initialization.
        super(Template, self).__init__()

        ##################################################
        # Do required version check
        if not hasattr(self, '_CHEETAH_versionTuple'):
            try:
                mod = sys.modules[self.__class__.__module__]
                compiledVersion = mod.__CHEETAH_version__
                compiledVersionTuple = convertVersionStringToTuple(compiledVersion)
                if compiledVersionTuple < MinCompatibleVersionTuple:
                    raise AssertionError(
                        'This template was compiled with Cheetah version'
                        ' %s. Templates compiled before version %s must be recompiled.' % (
                            compiledVersion, MinCompatibleVersion,
                        )
                    )
            except AssertionError:
                raise
            except:
                pass

        ##################################################
        # Setup instance state attributes used during the life of template
        # post-compile
        if searchList:
            for namespace in searchList:
                if isinstance(namespace, dict):
                    intersection = self.Reserved_SearchList & set(namespace.keys())
                    warn = False
                    if intersection:
                        warn = True
                    if isinstance(compilerSettings, dict) and compilerSettings.get('prioritizeSearchListOverSelf'):
                        warn = False
                    if warn:
                        logging.info(
                            'The following keys are members of the Template class '
                            'and will result in NameMapper collisions!'
                        )
                        logging.info('  > %s ' % ', '.join(list(intersection)))
                        logging.info(
                            "Please change the key's name or use the compiler setting "
                            '"prioritizeSearchListOverSelf=True" to prevent the NameMapper from using'
                        )
                        logging.info('the Template member in place of your searchList variable')

        self._initCheetahInstance(
            searchList=searchList, namespaces=namespaces,
            filter=filter, filtersLib=filtersLib,
            compilerSettings=compilerSettings)

        ##################################################
        # Now, compile if we're meant to
        if (source is not None) or (file is not None):
            self._compile(source, file, compilerSettings=compilerSettings)

    def generatedModuleCode(self):
        """Return the module code the compiler generated, or None if no
        compilation took place.
        """

        return self._CHEETAH_generatedModuleCode

    def generatedClassCode(self):
        """Return the class code the compiler generated, or None if no
        compilation took place.
        """

        return self._CHEETAH_generatedModuleCode[
            self._CHEETAH_generatedModuleCode.find('\nclass '):
            self._CHEETAH_generatedModuleCode.find('\n## END CLASS DEFINITION')
        ]

    def searchList(self):
        """Return a reference to the searchlist
        """
        return self._CHEETAH__searchList

    # utility functions

    def getVar(self, varName, default=Unspecified, autoCall=True, useDottedNotation=True):
        """Get a variable from the searchList.  If the variable can't be found
        in the searchList, it returns the default value if one was given, or
        raises NameMapper.NotFound.
        """

        try:
            return valueFromSearchList(self.searchList(), varName.replace('$', ''), autoCall, useDottedNotation)
        except NotFound:
            if default is not Unspecified:
                return default
            else:
                raise

    def varExists(self, varName, autoCall=False, useDottedNotation=True):
        """Test if a variable name exists in the searchList.
        """
        try:
            valueFromSearchList(self.searchList(), varName.replace('$', ''), autoCall, useDottedNotation)
            return True
        except NotFound:
            return False

    hasVar = varExists

    def getFileContents(self, path):
        """A hook for getting the contents of a file.  The default
        implementation just uses the Python open() function to load local files.
        This method could be reimplemented to allow reading of remote files via
        various protocols, as PHP allows with its 'URL fopen wrapper'
        """

        fp = open(path, 'r')
        output = fp.read()
        fp.close()
        return output

    ##################################################
    # internal methods -- not to be called by end-users

    def _initCheetahInstance(self,
                             searchList=None,
                             namespaces=None,
                             filter='RawOrEncodedUnicode',  # which filter from Cheetah.Filters
                             filtersLib=Filters,
                             compilerSettings=None):
        """Sets up the instance attributes that cheetah templates use at
        run-time.

        This is automatically called by the __init__ method of compiled
        templates.

        Note that the names of instance attributes used by Cheetah are prefixed
        with '_CHEETAH__' (2 underscores), where class attributes are prefixed
        with '_CHEETAH_' (1 underscore).
        """
        if getattr(self, '_CHEETAH__instanceInitialized', False):
            return

        if namespaces is not None:
            assert searchList is None, (
                'Provide "namespaces" or "searchList", not both!')
            searchList = namespaces
        if searchList is not None and not isinstance(searchList, (list, tuple)):
            searchList = [searchList]

        self._CHEETAH__globalSetVars = {}

        # create our own searchList
        self._CHEETAH__searchList = [self._CHEETAH__globalSetVars, self]
        if searchList is not None:
            if isinstance(compilerSettings, dict) and compilerSettings.get('prioritizeSearchListOverSelf'):
                self._CHEETAH__searchList = searchList + self._CHEETAH__searchList
            else:
                self._CHEETAH__searchList.extend(list(searchList))
        self._CHEETAH__cheetahIncludes = {}

        # @@TR: consider allowing simple callables as the filter argument
        self._CHEETAH__filtersLib = filtersLib
        self._CHEETAH__filters = {}
        if isinstance(filter, basestring):
            filterName = filter
            klass = getattr(self._CHEETAH__filtersLib, filterName)
        else:
            klass = filter
            filterName = klass.__name__
        self._CHEETAH__currentFilter = self._CHEETAH__filters[filterName] = klass(self).filter
        self._CHEETAH__initialFilter = self._CHEETAH__currentFilter

        if not hasattr(self, 'transaction'):
            self.transaction = None
        self._CHEETAH__instanceInitialized = True
        self._CHEETAH__isBuffering = False
        self._CHEETAH__isControlledByWebKit = False

    def respond(self):
        raise NotImplementedError

    def _compile(self, source=None, file=None, compilerSettings=Unspecified,
                 moduleName=None, mainMethodName=None):
        """Compile the template. This method is automatically called by
        Template.__init__ it is provided with 'file' or 'source' args.

        USERS SHOULD *NEVER* CALL THIS METHOD THEMSELVES.  Use Template.compile
        instead.
        """
        if compilerSettings is Unspecified:
            compilerSettings = self._getCompilerSettings(source, file) or {}
        mainMethodName = mainMethodName or self._CHEETAH_defaultMainMethodName
        self._fileMtime = None
        self._fileDirName = None
        self._fileBaseName = None
        if file and isinstance(file, basestring):
            self._fileMtime = os.path.getmtime(file)
            self._fileDirName, self._fileBaseName = os.path.split(file)
        self._filePath = file
        templateClass = self.compile(source, file,
                                     moduleName=moduleName,
                                     mainMethodName=mainMethodName,
                                     compilerSettings=compilerSettings,
                                     keepRefToGeneratedCode=True)

        if not self.__class__ == Template:
            # Only propogate attributes if we're in a subclass of
            # Template
            for k, v in self.__class__.__dict__.iteritems():
                if not v or k.startswith('__'):
                    continue
                # Propogate the class attributes to the instance
                # since we're about to obliterate self.__class__
                # (see: cheetah.Tests.Tepmlate.SubclassSearchListTest)
                setattr(self, k, v)

        self.__class__ = templateClass
        # must initialize it so instance attributes are accessible
        templateClass.__init__(self)
        if not hasattr(self, 'transaction'):
            self.transaction = None

T = Template   # Short and sweet for debugging at the >>> prompt.
Template.Reserved_SearchList = set(dir(Template))


def genParserErrorFromPythonException(source, file, generatedPyCode, exception):
    filename = isinstance(file, (str, unicode)) and file or None

    sio = StringIO.StringIO()
    traceback.print_exc(1, sio)
    formatedExc = sio.getvalue()

    if hasattr(exception, 'lineno'):
        pyLineno = exception.lineno
    else:
        pyLineno = int(re.search('[ \t]*File.*line (\d+)', formatedExc).group(1))

    lines = generatedPyCode.splitlines()

    prevLines = []                  # (i, content)
    for i in range(1, 4):
        if pyLineno-i <= 0:
            break
        prevLines.append((pyLineno+1-i, lines[pyLineno-i]))

    nextLines = []                  # (i, content)
    for i in range(1, 4):
        if not pyLineno+i < len(lines):
            break
        nextLines.append((pyLineno+i, lines[pyLineno+i]))
    nextLines.reverse()
    report = 'Line|Python Code\n'
    report += '----|-------------------------------------------------------------\n'
    while prevLines:
        lineInfo = prevLines.pop()
        report += "%(row)-4d|%(line)s\n" % {'row': lineInfo[0], 'line': lineInfo[1]}

    if hasattr(exception, 'offset'):
        report += ' '*(3+(exception.offset or 0)) + '^\n'

    while nextLines:
        lineInfo = nextLines.pop()
        report += "%(row)-4d|%(line)s\n" % {'row': lineInfo[0], 'line': lineInfo[1]}

    message = [
        "Error in the Python code which Cheetah generated for this template:",
        '='*80,
        '',
        str(exception),
        '',
        report,
        '='*80,
        ]
    cheetahPosMatch = re.search('line (\d+), col (\d+)', formatedExc)
    if cheetahPosMatch:
        lineno = int(cheetahPosMatch.group(1))
        col = int(cheetahPosMatch.group(2))
        # if hasattr(exception, 'offset'):
        #    col = exception.offset
        message.append('\nHere is the corresponding Cheetah code:\n')
    else:
        lineno = None
        col = None
        cheetahPosMatch = re.search('line (\d+), col (\d+)',
                                    '\n'.join(lines[max(pyLineno-2, 0):]))
        if cheetahPosMatch:
            lineno = int(cheetahPosMatch.group(1))
            col = int(cheetahPosMatch.group(2))
            message.append('\nHere is the corresponding Cheetah code.')
            message.append('** I had to guess the line & column numbers,'
                           ' so they are probably incorrect:\n')

    message = '\n'.join(message)
    reader = SourceReader(source, filename=filename)
    return ParseError(reader, message, lineno=lineno, col=col)

# vim: shiftwidth=4 tabstop=4 expandtab
