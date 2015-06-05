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
#include <string.h>
#include <stdlib.h>

#include "namemapper.h"

#ifdef __cplusplus
extern "C" {
#endif

#if PY_MAJOR_VERSION >= 3
#define IF_PY3(three, two) (three)
#else
#define IF_PY3(three, two) (two)
#endif

static PyObject *NotFound;   /* locally-raised exception */
static PyObject *TooManyPeriods;   /* locally-raised exception */
static PyObject* pprintMod_pformat; /* used for exception formatting */


/* *************************************************************************** */
/* First the c versions of the functions */
/* *************************************************************************** */

static void setNotFoundException(char *key)
{
    PyObject* fmt = PyUnicode_FromString("cannot find '{0}'");
    PyObject* fmted = PyObject_CallMethod(fmt, "format", IF_PY3("y", "s"), key);
    PyErr_SetObject(NotFound, fmted);
    Py_XDECREF(fmted);
    Py_XDECREF(fmt);
}

static int wrapInternalNotFoundException(char *fullName)
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
                PyObject* fmt = PyUnicode_FromString(
                    "{0} while searching for '{1}'"
                );
                newExcValue = PyObject_CallMethod(
                    fmt, "format", IF_PY3("Oy", "Os"), excValue, fullName
                );
                Py_XDECREF(fmt);
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

static int getNameChunks(char *nameChunks[], char *name, char *nameCopy)
{
    char c;
    char *currChunk;
    int currChunkNum = 0;

    currChunk = nameCopy;
    while ('\0' != (c = *nameCopy)) {
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


static PyObject *PyNamemapper_valueForName(PyObject *obj, char *nameChunks[], int numChunks, int isFirst)
{
    int i;
    char *currentKey;
    PyObject *currentVal = NULL;
    PyObject *nextVal = NULL;

    currentVal = obj;
    for (i = 0; i < numChunks; i++) {
        currentKey = nameChunks[i];
        if (PyErr_CheckSignals()) {	/* not sure if I really need to do this here, but what the hell */
            if (i > 0) {
                Py_DECREF(currentVal);
            }
            return NULL;
        }

        /* TODO: remove this eventually.
         * We only "auto key" on the first lookup because it could be locals()
         * or globals() or a searchList dictionary */
        if (isFirst && PyMapping_Check(currentVal) && PyMapping_HasKeyString(currentVal, currentKey)) {
            nextVal = PyMapping_GetItemString(currentVal, currentKey);
        } else {
            PyObject *exc;
            nextVal = PyObject_GetAttrString(currentVal, currentKey);
            exc = PyErr_Occurred();

            if (exc != NULL) {
                // if exception == AttributeError, report our own exception
                if (PyErr_ExceptionMatches(PyExc_AttributeError)) {
                    setNotFoundException(currentKey);
                }
                // any exceptions results in failure
                if (i > 0) {
                    Py_DECREF(currentVal);
                }
                return NULL;
            }

            if (nextVal == NULL) {
                setNotFoundException(currentKey);
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

        currentVal = nextVal;
    }

    return currentVal;
}


/* *************************************************************************** */
/* Now the wrapper functions to export into the Python module */
/* *************************************************************************** */

static PyObject *namemapper_valueFromSearchList(PYARGS)
{
    PyObject *searchList;
    char *name;

    char *nameCopy = NULL;
    char *tmpPntr1 = NULL;
    char *tmpPntr2 = NULL;
    char *nameChunks[MAXCHUNKS];
    int numChunks;

    PyObject *nameSpace = NULL;
    PyObject *theValue = NULL;
    PyObject *theValue_tmp = NULL;
    PyObject *iterator = NULL;

    static char *kwlist[] = {"searchList", "name", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Os|ii", kwlist, &searchList, &name)) {
        return NULL;
    }

    createNameCopyAndChunks();

    iterator = PyObject_GetIter(searchList);
    if (iterator == NULL) {
        PyErr_SetString(PyExc_TypeError, "This searchList is not iterable!");
        goto done;
    }

    while ((nameSpace = PyIter_Next(iterator))) {
        checkForNameInNameSpaceAndReturnIfFound(TRUE);
        Py_DECREF(nameSpace);
        if (PyErr_CheckSignals()) {
        theValue = NULL;
        goto done;
        }
    }
    if (PyErr_Occurred()) {
        theValue = NULL;
        goto done;
    }

    setNotFoundException(nameChunks[0]);

done:
    Py_XDECREF(iterator);
    free(nameCopy);

    return theValue;
}

static PyObject *namemapper_valueFromFrameOrSearchList(PyObject *self, PyObject *args, PyObject *keywds)
{
    /* python function args */
    char *name;
    PyObject *searchList = NULL;

    /* locals */
    char *nameCopy = NULL;
    char *tmpPntr1 = NULL;
    char *tmpPntr2 = NULL;
    char *nameChunks[MAXCHUNKS];
    int numChunks;

    PyObject *nameSpace = NULL;
    PyObject *theValue = NULL;
    PyObject *theValue_tmp = NULL;
    PyObject *iterator = NULL;

    static char *kwlist[] = {"searchList", "name", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, keywds, "Os|ii", kwlist,  &searchList, &name)) {
        return NULL;
    }

    createNameCopyAndChunks();

    nameSpace = PyEval_GetLocals();
    checkForNameInNameSpaceAndReturnIfFound(FALSE);

    nameSpace = PyEval_GetGlobals();
    checkForNameInNameSpaceAndReturnIfFound(FALSE);

    nameSpace = PyEval_GetBuiltins();
    checkForNameInNameSpaceAndReturnIfFound(FALSE);

    iterator = PyObject_GetIter(searchList);
    if (iterator == NULL) {
        PyErr_SetString(PyExc_TypeError, "This searchList is not iterable!");
        goto done;
    }
    while ((nameSpace = PyIter_Next(iterator))) {
        checkForNameInNameSpaceAndReturnIfFound(TRUE);
        Py_DECREF(nameSpace);
        if (PyErr_CheckSignals()) {
            theValue = NULL;
            goto done;
        }
    }
    if (PyErr_Occurred()) {
        theValue = NULL;
        goto done;
    }

    setNotFoundException(nameChunks[0]);

done:
    Py_XDECREF(iterator);
    free(nameCopy);

    return theValue;
}


/* *************************************************************************** */
/* Method registration table: name-string -> function-pointer */

static struct PyMethodDef namemapper_methods[] = {
  {"valueFromSearchList", (PyCFunction)namemapper_valueFromSearchList,  METH_VARARGS|METH_KEYWORDS},
  {"valueFromFrameOrSearchList", (PyCFunction)namemapper_valueFromFrameOrSearchList,  METH_VARARGS|METH_KEYWORDS},
  {NULL, NULL}
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
    NotFound = PyErr_NewException("NameMapper.NotFound", PyExc_LookupError, NULL);
    TooManyPeriods = PyErr_NewException("NameMapper.TooManyPeriodsInName", NULL, NULL);
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
