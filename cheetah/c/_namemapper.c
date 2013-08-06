/* ***************************************************************************
This is the C language version of NameMapper.py.  See the comments and
DocStrings in NameMapper for details on the purpose and interface of this
module.

===============================================================================
$Id: _namemapper.c,v 1.34 2007/12/10 18:25:20 tavis_rudd Exp $
Authors: Tavis Rudd <tavis@damnsimple.com>
Version: $Revision: 1.34 $
Start Date: 2001/08/07
Last Revision Date: $Date: 2007/12/10 18:25:20 $
*/

/* *************************************************************************** */
#include <Python.h>
#include <frameobject.h>
#include <string.h>
#include <stdlib.h>

#include "cheetah.h"

#ifdef __cplusplus
extern "C" {
#endif


static PyObject *NotFound;   /* locally-raised exception */
static PyObject *TooManyPeriods;   /* locally-raised exception */
static PyObject* pprintMod_pformat; /* used for exception formatting */


/* *************************************************************************** */
/* Instrumentation code */
/* *************************************************************************** */

static PyObject *clogMod_log_line;

#define DID_AUTOKEY     1
#define DID_AUTOCALL    2

#define NS_GLOBALS      (-1)
#define NS_LOCALS       (-2)
#define NS_BUILTINS     (-3)

struct PlaceholderInfo {
    /* A pointer to the Python stack frame that is evaluating the placeholder.
     * This is used to distinguish placeholders with the same name in different
     * templates, since it's easier to compare frame pointers than to compare
     * filenames (strings). */
    PyFrameObject* pythonStackPointer;

    /* The ID of the placeholder, assigned by the Cheetah compiler. */
    uint16_t placeholderID;

    /* The index of the item in the search list where the first lookup
     * succeeded.  (For "$x.y", this is the index of the searchlist item that
     * contained "x".)  May also be one of the special constants NS_GLOBALS,
     * NS_LOCALS, or NS_BUILTINS, to indicate that the item was found in
     * globals(), locals(), or __builtins__ respectively. */
    int8_t nameSpaceIndex;

    /* The number of lookups performed so far.  "$x.y[1].z" contains three
     * lookups (one each for "x", "y", and "z").  The "[1]" part does not
     * invoke the namemapper, so it is not counted as a lookup. */
    uint8_t lookupCount;

    /* A list of 16 two-bit entries, indicating whether each lookup DID_AUTOKEY
     * and/or DID_AUTOCALL.  The least-significant two bits correspond to the
     * first lookup. */
    uint32_t flags;

    /* Pointer to the next item on the placeholder stack. */
    struct PlaceholderInfo *next;
};


/* Keep a stack of placeholders being evaluated as a singly-linked list.  NULL
 * represents the empty list. */
struct PlaceholderInfo *placeholderStackTop = NULL;

/* Push a new item onto the placeholder stack, initialized with the provided
 * placeholderID and nameSpaceIndex, and the current PyFrameObject (the current
 * Python stack frame, from PyEval_GetFrame()). */
void pushPlaceholderStack(int placeholderID, int nameSpaceIndex) {
    struct PlaceholderInfo *newPlaceholderInfo = malloc(sizeof(struct PlaceholderInfo));

    newPlaceholderInfo->pythonStackPointer = PyEval_GetFrame();
    newPlaceholderInfo->placeholderID = placeholderID;
    newPlaceholderInfo->nameSpaceIndex = nameSpaceIndex;
    newPlaceholderInfo->lookupCount = 0;
    newPlaceholderInfo->flags = 0;
    newPlaceholderInfo->next = placeholderStackTop;

    placeholderStackTop = newPlaceholderInfo;
}

/* Pop an item from the placeholder stack. */
void popPlaceholderStack(void) {
    if (placeholderStackTop == NULL) {
        // TODO: warn
        return;
    }

    struct PlaceholderInfo *oldStackTop = placeholderStackTop;
    placeholderStackTop = oldStackTop->next;
    free(oldStackTop);
}

/* Pop all items from the placeholder stack. */
void clearPlaceholderStack(void) {
    while (placeholderStackTop != NULL) {
        popPlaceholderStack();
    }
}

/* Record a lookup step for the current placeholder. */
void recordLookup(int flags) {
    int index = placeholderStackTop->lookupCount;
    ++placeholderStackTop->lookupCount;
    if (index >= 16)
        // TODO: warn
        return;

    placeholderStackTop->flags |= (flags & 3) << (index * 2);
}

/* Check if the current placeholder matches the provided placeholderID and the
 * current PyFrameObject. */
int currentPlaceholderMatches(int placeholderID) {
    return placeholderStackTop->pythonStackPointer == PyEval_GetFrame() &&
        placeholderStackTop->placeholderID == placeholderID;
}

uint32_t hashString(const char* str) {
    uint32_t hash = 0;
    while (*str != '\0') {
        hash = hash * 37 + (uint8_t)(*str);
        ++str;
    }
    return hash;
}

void extractPathComponents(const char *filename, const char **deploySHAStartPtr, const char **templateNameStartPtr) {
    const char *deploySHAStart = NULL;
    const char *templateNameStart = NULL;

    const char *foundDeploy;
    const char *foundYelpMain;
    const char *foundSlash = NULL;

    /* Check for various things that look like yelp-main checkouts.  Set
     * 'foundSlash' to the slash following the checkout directory once we find
     * it. */

    /* First check for path components that look like deployment directories.
     */
    foundDeploy = strstr(filename, "-deploy");
    if (foundDeploy != NULL) {
        /* Try to find a deployment SHA.  It should be 10 characters of hex
         * immediately preceding the "-deploy". */

        /* First make sure there are at least 10 characters between the start
         * of the filename and the "-deploy". */
        if (foundDeploy - 10 >= filename) {
            /* Now check that those 10 characters are all hex. */
            if (strspn(foundDeploy - 10, "0123456789abcdef") >= 10) {
                deploySHAStart = foundDeploy - 10;
            }
        }

        foundSlash = strchr(foundDeploy, '/');
    }

    /* Next, look for components containing "yelp-main".  This is how it works
     * in dev playgrounds. */
    if (foundSlash == NULL) {
        foundYelpMain = strstr(filename, "yelp-main");
        if (foundYelpMain != NULL) {
            foundSlash = strchr(foundYelpMain, '/');
        }
    }

    /* Finally, check if the path starts with "./".  If so, we assume "." is a
     * yelp-main checkout, because that's how it works on buildbot. */
    if (foundSlash == NULL) {
        if (strstr(filename, "./") == filename) {
            foundSlash = strchr(filename, '/');
        }
    }

    /* If we found a yelp-main component, then the template name starts after
     * the / that follows that component.  Otherwise, leave NULL as the
     * template name. */
    if (foundSlash != NULL) {
        templateNameStart = foundSlash + 1;
    }

    *deploySHAStartPtr = deploySHAStart;
    *templateNameStartPtr = templateNameStart;
}

/* Log the information stored in the current placeholders. */
void logPlaceholderInfo(void) {
    PyFrameObject *pyFrame = placeholderStackTop->pythonStackPointer;
    const char *fileName = PyString_AsString(pyFrame->f_code->co_filename);
    /* We don't need to free(fileName), since it's a pointer into memory that
     * is managed by the Python runtime. */

    /* Extract the interesting information from the filename. */

    /* The first character of the deploy SHA from the filename, or NULL if we
     * can't find the SHA. */
    const char *deploySHAStart;
    /* The first character of the first path component inside the yelp-main
     * checkout. */
    const char *templateNameStart;

    extractPathComponents(fileName, &deploySHAStart, &templateNameStart);

    if (deploySHAStart == NULL) {
        deploySHAStart = "0000000000";
    }

    /* Hash the template name, so we don't have to write the whole thing to
     * scribe. */
    uint32_t templateNameHash;
    if (templateNameStart != NULL) {
        templateNameHash = hashString(templateNameStart);
    } else {
        templateNameHash = 0;
    }

    /* We log everything in hexadecimal, with each field separated by a space.
     * So the expected output width is: 11 (deploy SHA) + 9 (fileNameHash) +
     * 5 (placeholderID) + 3 (nameSpaceIndex) + 3 (lookupCount) +
     * 9 (flags) = 40. */
    char buf[48];
    /* The 'size' argument to snprintf includes the terminating \0, which is
     * always written (even if the output is too long for the buffer). */
    snprintf(buf, 48, "%.10s %x %x %x %x %x",
            deploySHAStart,
            templateNameHash,
            placeholderStackTop->placeholderID,
            (uint8_t)placeholderStackTop->nameSpaceIndex,
            placeholderStackTop->lookupCount,
            placeholderStackTop->flags);
    /* We cast nameSpaceIndex from int8_t to uint8_t because it might be
     * negative.  Since printf arguments are implicitly converted to 'int',
     * (int8_t)-1 would be converted to (int)-1, which is "ffffffff" (8
     * digits), while (uint8_t)-1 == (uint8_t)255 would be converted to
     * (int)255, which is "ff" (2 digits).  Observe:
     *      printf("%x\n", (int8_t)-1);     -> prints "ffffffff"
     *      printf("%x\n", (uint8_t)-1);    -> prints "ff"
     */

    PyObject_CallFunction(clogMod_log_line, "ss", "tmp_namemapper_placeholder_uses", buf);
}


/* *************************************************************************** */
/* First the c versions of the functions */
/* *************************************************************************** */

static void setNotFoundException(char *key, PyObject *namespace)
{
    PyObject *exceptionStr = NULL;
    exceptionStr = PyUnicode_FromFormat("cannot find \'%s\'", key);
    PyErr_SetObject(NotFound, exceptionStr);
    Py_XDECREF(exceptionStr);
}

static int wrapInternalNotFoundException(char *fullName, PyObject *namespace)
{
    PyObject *excType, *excValue, *excTraceback, *isAlreadyWrapped = NULL;
    PyObject *newExcValue = NULL;
    if (!ALLOW_WRAPPING_OF_NOTFOUND_EXCEPTIONS) {
        return 0;
    } 

    if (!PyErr_Occurred()) {
        return 0;
    }

    if (PyErr_GivenExceptionMatches(PyErr_Occurred(), NotFound)) {
        PyErr_Fetch(&excType, &excValue, &excTraceback);
        isAlreadyWrapped = PyObject_CallMethod(excValue, "find", "s", "while searching");

        if (isAlreadyWrapped != NULL) {
            if (PyLong_AsLong(isAlreadyWrapped) == -1) {
                newExcValue = PyUnicode_FromFormat("%U while searching for \'%s\'",
                        excValue, fullName);
            }
            Py_DECREF(isAlreadyWrapped);
        }
        else {
           newExcValue = excValue; 
        }
        PyErr_Restore(excType, newExcValue, excTraceback);
        return -1;
    } 
    return 0;
}


static int isInstanceOrClass(PyObject *nextVal) {
#ifndef IS_PYTHON3
    /* old style classes or instances */
    if((PyInstance_Check(nextVal)) || (PyClass_Check(nextVal))) {
        return 1;
    }
#endif 

    if (!PyObject_HasAttrString(nextVal, "__class__")) {
        return 0;
    }

    /* new style classes or instances */
    if (PyType_Check(nextVal) || PyObject_HasAttrString(nextVal, "mro")) {
        return 1;
    }

    if (strncmp(nextVal->ob_type->tp_name, "function", 9) == 0)
        return 0;

    /* method, func, or builtin func */
    if (PyObject_HasAttrString(nextVal, "im_func") 
        || PyObject_HasAttrString(nextVal, "func_code")
        || PyObject_HasAttrString(nextVal, "__self__")) {
        return 0;
    }

    /* instance */
    if ((!PyObject_HasAttrString(nextVal, "mro")) &&
            PyObject_HasAttrString(nextVal, "__init__")) {
        return 1;
    }

    return 0;
}


static int getNameChunks(char *nameChunks[], char *name, char *nameCopy) 
{
    char c;
    char *currChunk;
    int currChunkNum = 0;

    currChunk = nameCopy;
    while ('\0' != (c = *nameCopy)){
    if ('.' == c) {
        if (currChunkNum >= (MAXCHUNKS-2)) { /* avoid overflowing nameChunks[] */
            PyErr_SetString(TooManyPeriods, name); 
            return 0;
        }

        *nameCopy ='\0';
        nameChunks[currChunkNum++] = currChunk;
        nameCopy++;
        currChunk = nameCopy;
    } else 
        nameCopy++;
    }
    if (nameCopy > currChunk) {
        nameChunks[currChunkNum++] = currChunk;
    }
    return currChunkNum;
}


static int PyNamemapper_hasKey(PyObject *obj, char *key)
{
    if (PyMapping_Check(obj) && PyMapping_HasKeyString(obj, key)) {
        return TRUE;
    } else if (PyObject_HasAttrString(obj, key)) {
        return TRUE;
    }
    return FALSE;
}


static PyObject *PyNamemapper_valueForKey(PyObject *obj, char *key)
{
    PyObject *theValue = NULL;

    if (PyMapping_Check(obj) && PyMapping_HasKeyString(obj, key)) {
        theValue = PyMapping_GetItemString(obj, key);
    } else if (PyObject_HasAttrString(obj, key)) {
        theValue = PyObject_GetAttrString(obj, key);
    } else {
        setNotFoundException(key, obj);
    }
    return theValue;
}

static PyObject *PyNamemapper_valueForName(PyObject *obj, char *nameChunks[], int numChunks, int placeholderID, int executeCallables)
{
    int i;
    char *currentKey;
    int currentFlags;
    int placeholderIsCurrent;
    PyObject *currentVal = NULL;
    PyObject *nextVal = NULL;

    /* A placeholder evaluation should always start with a valueFromX call
     * (typically valueFromFrameOrSearchList), not valueForName, and it should
     * end with flushPlaceholderInfo.  If we see a valueForName for a
     * placeholder that's not the current stack top, there's a bug. */
    placeholderIsCurrent = currentPlaceholderMatches(placeholderID);
    if (!placeholderIsCurrent) {
        // TODO: warn
    }

    currentVal = obj;
    for (i=0; i < numChunks;i++) {
        currentKey = nameChunks[i];
        currentFlags = 0;
        if (PyErr_CheckSignals()) {	/* not sure if I really need to do this here, but what the hell */
            if (i>0) {
                Py_DECREF(currentVal);
            }
            return NULL;
        }

        if (PyMapping_Check(currentVal) && PyMapping_HasKeyString(currentVal, currentKey)) {
            nextVal = PyMapping_GetItemString(currentVal, currentKey);
            currentFlags |= DID_AUTOKEY;
        }

        else {
            PyObject *exc;
            nextVal = PyObject_GetAttrString(currentVal, currentKey);
            exc = PyErr_Occurred();

            if (exc != NULL) {
                // if exception == AttributeError, report our own exception
                if (PyErr_ExceptionMatches(PyExc_AttributeError)) {
                    setNotFoundException(currentKey, currentVal);
                }
                // any exceptions results in failure
                if (i > 0) {
                    Py_DECREF(currentVal);
                }
                return NULL;
            }

            if (nextVal == NULL) {
                setNotFoundException(currentKey, currentVal);
                // any exceptions results in failure
                if (i > 0) {
                    Py_DECREF(currentVal);
                }
                return NULL;
            }
        }
        if (i > 0) {
            Py_DECREF(currentVal);
        }

        if (executeCallables && PyCallable_Check(nextVal) && 
                (isInstanceOrClass(nextVal) == 0) ) {
            if (!(currentVal = PyObject_CallObject(nextVal, NULL))) {
                Py_DECREF(nextVal);
                return NULL;
            }
            currentFlags |= DID_AUTOCALL;
            Py_DECREF(nextVal);
        } else {
            currentVal = nextVal;
        }

        if (placeholderIsCurrent)
            recordLookup(currentFlags);
    }

    return currentVal;
}


/* *************************************************************************** */
/* Now the wrapper functions to export into the Python module */
/* *************************************************************************** */


static PyObject *namemapper_valueForKey(PyObject *self, PyObject *args)
{
    PyObject *obj;
    char *key;

    if (!PyArg_ParseTuple(args, "Os", &obj, &key)) {
        return NULL;
    }

    return PyNamemapper_valueForKey(obj, key);
}

static PyObject *namemapper_valueForName(PYARGS)
{
    PyObject *obj;
    char *name;
    int executeCallables = 0;
    int placeholderID;

    char *nameCopy = NULL;
    char *tmpPntr1 = NULL;
    char *tmpPntr2 = NULL;
    char *nameChunks[MAXCHUNKS];
    int numChunks;

    PyObject *theValue;

    static char *kwlist[] = {"obj", "name", "placeholderID", "executeCallables", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Osi|i", kwlist,  &obj, &name, &placeholderID, &executeCallables)) {
        return NULL;
    }

    createNameCopyAndChunks();  

    theValue = PyNamemapper_valueForName(obj, nameChunks, numChunks, placeholderID, executeCallables);
    free(nameCopy);
    if (wrapInternalNotFoundException(name, obj)) {
        theValue = NULL;
    }
    return theValue;
}

static PyObject *namemapper_valueFromSearchList(PYARGS)
{
    PyObject *searchList;
    char *name;
    int placeholderID;
    int executeCallables = 0;

    char *nameCopy = NULL;
    char *tmpPntr1 = NULL;
    char *tmpPntr2 = NULL;
    char *nameChunks[MAXCHUNKS];
    int numChunks;
    int searchListIndex;

    PyObject *nameSpace = NULL;
    PyObject *theValue = NULL;
    PyObject *iterator = NULL;

    static char *kwlist[] = {"searchList", "name", "placeholderID", "executeCallables", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Osi|i", kwlist, &searchList, &name, &placeholderID, &executeCallables)) {
        return NULL;
    }

    createNameCopyAndChunks();

    iterator = PyObject_GetIter(searchList);
    if (iterator == NULL) {
        PyErr_SetString(PyExc_TypeError,"This searchList is not iterable!");
        goto done;
    }

    searchListIndex = 0;
    while ((nameSpace = PyIter_Next(iterator))) {
        checkForNameInNameSpaceAndReturnIfFound(TRUE, searchListIndex);
        ++searchListIndex;
        Py_DECREF(nameSpace);
        if(PyErr_CheckSignals()) {
        theValue = NULL;
        goto done;
        }
    }
    if (PyErr_Occurred()) {
        theValue = NULL;
        goto done;
    }

    setNotFoundException(nameChunks[0], searchList);

done:
    Py_XDECREF(iterator);
    free(nameCopy);
    return theValue;
}

static PyObject *namemapper_valueFromFrameOrSearchList(PyObject *self, PyObject *args, PyObject *keywds)
{
    /* python function args */
    char *name;
    int placeholderID;
    int executeCallables = 0;
    PyObject *searchList = NULL;

    /* locals */
    char *nameCopy = NULL;
    char *tmpPntr1 = NULL;
    char *tmpPntr2 = NULL;
    char *nameChunks[MAXCHUNKS];
    int numChunks;
    int searchListIndex;

    PyObject *nameSpace = NULL;
    PyObject *theValue = NULL;
    PyObject *excString = NULL;
    PyObject *iterator = NULL;

    static char *kwlist[] = {"searchList", "name", "placeholderID",  "executeCallables", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, keywds, "Osi|i", kwlist,  &searchList, &name, 
                    &placeholderID, &executeCallables)) {
        return NULL;
    }

    createNameCopyAndChunks();

    nameSpace = PyEval_GetLocals();
    checkForNameInNameSpaceAndReturnIfFound(FALSE, NS_LOCALS);  

    iterator = PyObject_GetIter(searchList);
    if (iterator == NULL) {
        PyErr_SetString(PyExc_TypeError,"This searchList is not iterable!");
        goto done;
    }
    searchListIndex = 0;
    while ( (nameSpace = PyIter_Next(iterator)) ) {
        checkForNameInNameSpaceAndReturnIfFound(TRUE, searchListIndex);
        ++searchListIndex;
        Py_DECREF(nameSpace);
        if(PyErr_CheckSignals()) {
            theValue = NULL;
            goto done;
        }
    }
    if (PyErr_Occurred()) {
        theValue = NULL;
        goto done;
    }

    nameSpace = PyEval_GetGlobals();
    checkForNameInNameSpaceAndReturnIfFound(FALSE, NS_GLOBALS);

    nameSpace = PyEval_GetBuiltins();
    checkForNameInNameSpaceAndReturnIfFound(FALSE, NS_BUILTINS);

    excString = Py_BuildValue("s", "[locals()]+searchList+[globals(), __builtins__]");
    setNotFoundException(nameChunks[0], excString);
    Py_DECREF(excString);

done:
    Py_XDECREF(iterator);
    free(nameCopy);
    return theValue;
}

static PyObject *namemapper_valueFromFrame(PyObject *self, PyObject *args, PyObject *keywds)
{
    /* python function args */
    char *name;
    int placeholderID;
    int executeCallables = 0;

    /* locals */
    char *tmpPntr1 = NULL;
    char *tmpPntr2 = NULL;

    char *nameCopy = NULL;
    char *nameChunks[MAXCHUNKS];
    int numChunks;

    PyObject *nameSpace = NULL;
    PyObject *theValue = NULL;
    PyObject *excString = NULL;

    static char *kwlist[] = {"name", "placeholderID", "executeCallables", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, keywds, "si|i", kwlist, &name, &placeholderID, &executeCallables)) {
        return NULL;
    }

    createNameCopyAndChunks();

    nameSpace = PyEval_GetLocals();
    checkForNameInNameSpaceAndReturnIfFound(FALSE, NS_LOCALS);

    nameSpace = PyEval_GetGlobals();
    checkForNameInNameSpaceAndReturnIfFound(FALSE, NS_GLOBALS);

    nameSpace = PyEval_GetBuiltins();
    checkForNameInNameSpaceAndReturnIfFound(FALSE, NS_BUILTINS);

    excString = Py_BuildValue("s", "[locals(), globals(), __builtins__]");
    setNotFoundException(nameChunks[0], excString);
    Py_DECREF(excString);
done:
    free(nameCopy);
    return theValue;
}

static PyObject *namemapper_flushPlaceholderInfo(PyObject *self, PyObject *args, PyObject *keywds)
{
    /* python function args */
    PyObject* obj;
    int placeholderID;

    static char *kwlist[] = {"obj", "placeholderID", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, keywds, "Oi", kwlist, &obj, &placeholderID)) {
        return NULL;
    }

    if (currentPlaceholderMatches(placeholderID)) {
        logPlaceholderInfo();
        popPlaceholderStack();
    } else {
        // TODO: warn
    }

    /* Python doesn't automatically increment the reference count of the
     * function's return value, so we have to do it manually. */
    Py_XINCREF(obj);
    return obj;
}

/* *************************************************************************** */
/* Method registration table: name-string -> function-pointer */

static struct PyMethodDef namemapper_methods[] = {
  {"valueForKey", namemapper_valueForKey,  1},
  {"valueForName", (PyCFunction)namemapper_valueForName,  METH_VARARGS|METH_KEYWORDS},
  {"valueFromSearchList", (PyCFunction)namemapper_valueFromSearchList,  METH_VARARGS|METH_KEYWORDS},
  {"valueFromFrame", (PyCFunction)namemapper_valueFromFrame,  METH_VARARGS|METH_KEYWORDS},
  {"valueFromFrameOrSearchList", (PyCFunction)namemapper_valueFromFrameOrSearchList,  METH_VARARGS|METH_KEYWORDS},
  {"flushPlaceholderInfo", (PyCFunction)namemapper_flushPlaceholderInfo,  METH_VARARGS|METH_KEYWORDS},
  {NULL,         NULL}
};


/* *************************************************************************** */
/* Initialization function (import-time) */

#ifdef IS_PYTHON3
static struct PyModuleDef namemappermodule = {
    PyModuleDef_HEAD_INIT,
    "_namemapper",
    NULL, /* docstring */
    -1, 
    namemapper_methods,
    NULL,
    NULL,
    NULL,
    NULL};

PyMODINIT_FUNC PyInit__namemapper(void)
{
    PyObject *m = PyModule_Create(&namemappermodule);
#else
DL_EXPORT(void) init_namemapper(void)
{
    PyObject *m = Py_InitModule3("_namemapper", namemapper_methods, NULL);
#endif 

    PyObject *d, *pprintMod;

    /* add symbolic constants to the module */
    d = PyModule_GetDict(m);
    NotFound = PyErr_NewException("NameMapper.NotFound",PyExc_LookupError,NULL);
    TooManyPeriods = PyErr_NewException("NameMapper.TooManyPeriodsInName",NULL,NULL);
    PyDict_SetItemString(d, "NotFound", NotFound);
    PyDict_SetItemString(d, "TooManyPeriodsInName", TooManyPeriods);

    pprintMod = PyImport_ImportModule("pprint");
    if (!pprintMod) {
#ifdef IS_PYTHON3
        return NULL;
#else
        return;
#endif
    }
    pprintMod_pformat = PyObject_GetAttrString(pprintMod, "pformat");
    Py_DECREF(pprintMod);

    PyObject* clogMod = PyImport_ImportModule("clog");
    if (!clogMod) {
#ifdef IS_PYTHON3
        return NULL;
#else
        return;
#endif
    }
    clogMod_log_line = PyObject_GetAttrString(clogMod, "log_line");
    Py_DECREF(clogMod);

    /* check for errors */
    if (PyErr_Occurred()) {
        Py_FatalError("Can't initialize module _namemapper");
    }
#ifdef IS_PYTHON3
    return m;
#endif
}

#ifdef __cplusplus
}
#endif
