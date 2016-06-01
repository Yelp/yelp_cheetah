#include <Python.h>

#if PY_MAJOR_VERSION >= 3
#define IF_PY3(three, two) (three)
#else
#define IF_PY3(three, two) (two)
#endif

static PyObject* NotFound;
static PyObject* _builtins_module;


static inline PyObject* _ns_lookup(char* key, PyObject* ns) {
    PyObject* ret = NULL;

    if ((ret = PyMapping_GetItemString(ns, key))) {
        return ret;
    }

    PyErr_Clear();

    {
        PyObject* fmt = PyUnicode_FromString("Cannot find '{}'");
        PyObject* fmted = PyObject_CallMethod(
            fmt, "format", IF_PY3("y", "s"), key
        );
        PyErr_SetObject(NotFound, fmted);
        Py_XDECREF(fmted);
        Py_XDECREF(fmt);
    }
    return NULL;
}


static inline PyObject* _self_lookup(char* key, PyObject* selfobj) {
    PyObject* ret = NULL;

    if ((ret = PyObject_GetAttrString(selfobj, key))) {
        return ret;
    }

    PyErr_Clear();

    return ret;
}


static inline PyObject* _frame_lookup(char* key, PyObject* locals, PyObject* globals) {
    PyObject* ret = NULL;

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

    return ret;
}


static PyObject* value_from_namespace(PyObject* _, PyObject* args) {
    char* key;
    PyObject* ns;

    if (!PyArg_ParseTuple(args, "sO", &key, &ns)) {
        return NULL;
    }

    return _ns_lookup(key, ns);
}


static PyObject* value_from_frame_or_namespace(PyObject* _, PyObject* args) {
    char* key;
    PyObject* locals;
    PyObject* globals;
    PyObject* ns;
    PyObject* ret;

    if (!PyArg_ParseTuple(args, "sOOO", &key, &locals, &globals, &ns)) {
        return NULL;
    }

    if ((ret = _frame_lookup(key, locals, globals))) {
        return ret;
    } else {
        return _ns_lookup(key, ns);
    }
}

static PyObject* value_from_search_list(PyObject* _, PyObject* args) {
    char* key;
    PyObject* selfobj;
    PyObject* ns;
    PyObject* ret;

    if (!PyArg_ParseTuple(args, "sOO", &key, &selfobj, &ns)) {
        return NULL;
    }

    if ((ret = _self_lookup(key, selfobj))) {
        return ret;
    } else {
        return _ns_lookup(key, ns);
    }
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

    if ((ret = _frame_lookup(key, locals, globals))) {
        return ret;
    } else if ((ret = _self_lookup(key, selfobj))) {
        return ret;
    } else {
        return _ns_lookup(key, ns);
    }
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
        "value_from_namespace",
        (PyCFunction)value_from_namespace,
        METH_VARARGS
    },
    {
        "value_from_frame_or_namespace",
        (PyCFunction)value_from_frame_or_namespace,
        METH_VARARGS
    },
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
