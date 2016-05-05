#include <Python.h>

#if PY_MAJOR_VERSION >= 3
#define IF_PY3(three, two) (three)
#else
#define IF_PY3(three, two) (two)
#endif

static PyObject* NotFound;
static PyObject* _builtins_module;


static PyObject* _vfsl(char* key, PyObject* selfobj, PyObject* ns) {
    PyObject* ret;
    PyObject* fmt;
    PyObject* fmted;

    if ((ret = PyObject_GetAttrString(selfobj, key))) {
        return ret;
    }

    PyErr_Clear();

    if ((ret = PyMapping_GetItemString(ns, key))) {
        return ret;
    }

    PyErr_Clear();

    fmt = PyUnicode_FromString("Cannot find '{}'");
    fmted = PyObject_CallMethod(fmt, "format", IF_PY3("y", "s"), key);
    PyErr_SetObject(NotFound, fmted);
    Py_XDECREF(fmted);
    Py_XDECREF(fmt);
    return NULL;
}

static PyObject* value_from_search_list(PyObject* _, PyObject* args) {
    char* key;
    PyObject* selfobj;
    PyObject* ns;

    if (!PyArg_ParseTuple(args, "sOO", &key, &selfobj, &ns)) {
        return NULL;
    }

    return _vfsl(key, selfobj, ns);
}

static PyObject* value_from_frame_or_search_list(PyObject* _, PyObject* args) {
    char* key;
    PyObject* locals;
    PyObject* globals;
    PyObject* selfobj;
    PyObject* ns;
    PyObject* ret;

    if (!PyArg_ParseTuple(args, "sOOOO", &key, &locals, &globals, &selfobj, &ns)) {
        return NULL;
    }

    if ((ret = PyMapping_GetItemString(locals, key))) {
        return ret;
    }

    PyErr_Clear();

    if ((ret = PyMapping_GetItemString(globals, key))) {
        return ret;
    }

    PyErr_Clear();

    if ((ret = PyObject_GetAttrString(_builtins_module, key))) {
        return ret;
    }

    PyErr_Clear();

    return _vfsl(key, selfobj, ns);
}

static PyObject* _setup_module(PyObject* module) {
    if (module) {
        NotFound = PyErr_NewException("_cheetah.NotFound", PyExc_LookupError, NULL);
        PyModule_AddObject(module, "NotFound", NotFound);

        _builtins_module = PyImport_ImportModule(IF_PY3("builtins", "__builtin__"));
        if (!_builtins_module) {
            Py_DECREF(module);
            module = NULL;
        }
    }
    return module;
}

static struct PyMethodDef methods[] = {
    {
        "value_from_search_list",
        (PyCFunction)value_from_search_list,
        METH_VARARGS
    },
    {
        "value_from_frame_or_search_list",
        (PyCFunction)value_from_frame_or_search_list,
        METH_VARARGS
    },
    {NULL, NULL}
};

#if PY_MAJOR_VERSION >= 3
static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "_cheetah",
    NULL,
    -1,
    methods
};

PyMODINIT_FUNC PyInit__cheetah(void) {
    return _setup_module(PyModule_Create(&module));
}
#else
PyMODINIT_FUNC init_cheetah(void) {
    _setup_module(Py_InitModule3("_cheetah", methods, NULL));
}
#endif
