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

/*** Placeholder tracking ***/

/* Information about a placeholder evaluation. */
struct PlaceholderInfo {
    /* A pointer to the Python stack frame that is evaluating the placeholder.
     * This is used to distinguish placeholders with the same ID in different
     * templates, and to obtain the name of the template for logging purposes.
     */
    PyFrameObject* pythonStackPointer;

    /* The ID of the placeholder.  This is a number assigned by the Cheetah
     * compiler, which can be used to identify a specific placeholder in the
     * template file.  It is unique among all placeholders in the same
     * template, but not across different templates. */
    uint16_t placeholderID;

    /* The index of the item in the search list where the first lookup
     * succeeded.  (For "$x.y", this is the index of the searchlist item that
     * contained "x".)  This may also be one of the special NS_ constants
     * defined below. */
    uint8_t nameSpaceIndex;

    /* The number of lookups performed so far.  "$x.y[1].z" contains three
     * lookups (one each for "x", "y", and "z").  The "[1]" part does not
     * invoke the namemapper, so it is not counted as a lookup. */
    uint8_t lookupCount;

    /* A list of 16 two-bit entries, indicating whether each lookup used
     * autokey and/or autocall.  The least-significant two bits correspond to
     * the first lookup. */
    uint32_t flags;
};

/* Flags to indicate which namemapper features were used on a particular lookup
 * step. */
#define DID_AUTOKEY     1
#define DID_AUTOCALL    2

/* Special values for nameSpaceIndex to indicate that the first lookup was
 * completed using something other than the searchlist. */
/* The first lookup was completed using globals(). */
#define NS_GLOBALS      252
/* The first lookup was completed using locals(). */
#define NS_LOCALS       253
/* The first lookup was completed using __builtins__. */
#define NS_BUILTINS     254
/* The first lookup raised a NotFound error. */
#define NS_NOT_FOUND    255

/* We keep a stack of placeholders being evaluated.  This lets us handle nested
 * evaluations properly.  For example, evaluation of "$x[$y].z" will start by
 * looking up "x" for the outer placeholder, then will fully evaluate the inner
 * placeholder "$y", and finally will finish the outer placeholder by looking
 * up "z". */

/* The maximum size to use for the stack.  We limit the size to avoid dynamic
 * allocation, which increases the cost of the instrumentation by about 50%.
 *
 * In testing, I've never seen the stack depth exceed 3, so 64 seems like it
 * should be high enough to avoid problems.
 */
#define PLACEHOLDER_STACK_SIZE 64
struct PlaceholderInfo placeholderStack[PLACEHOLDER_STACK_SIZE];

/* A pointer to the current stack element.  The stack grows downward, just like
 * the x86 stack.  We initialize to past-the-end of placeholderStack. */
struct PlaceholderInfo *placeholderStackTop = &placeholderStack[PLACEHOLDER_STACK_SIZE];

/* Push a new item onto the placeholder stack, initialized with the provided
 * placeholderID and the current PyFrameObject (the current Python stack frame,
 * from PyEval_GetFrame()). */
void pushPlaceholderStack(int placeholderID) {
    if (placeholderStackTop == &placeholderStack[0])
        /* Don't push if the stack is already full.  Just let the checks
         * against currentPlaceholderMatches prevent any logging while the
         * stack is in this overflow state. */
        return;

    --placeholderStackTop;

    placeholderStackTop->pythonStackPointer = PyEval_GetFrame();
    placeholderStackTop->placeholderID = placeholderID;
    /* nameSpaceIndex will be changed to the correct value once the first
     * lookup succeeds.  We initialize it to NS_NOT_FOUND in case the lookup
     * fails before reaching that point. */
    placeholderStackTop->nameSpaceIndex = NS_NOT_FOUND;
    placeholderStackTop->lookupCount = 0;
    placeholderStackTop->flags = 0;
}

/* Pop an item from the placeholder stack. */
void popPlaceholderStack(void) {
    if (placeholderStackTop == &placeholderStack[PLACEHOLDER_STACK_SIZE]) {
        /* Don't pop if the stack is already empty.  This probably indicates a
         * bug. */
        return;
    }

    ++placeholderStackTop;
}

/* Pop all items from the placeholder stack. */
void clearPlaceholderStack(void) {
    placeholderStackTop = &placeholderStack[PLACEHOLDER_STACK_SIZE];
}

/* Record the flags for a lookup step of the current placeholder. */
void recordLookup(int flags) {
    int index = placeholderStackTop->lookupCount;
    ++placeholderStackTop->lookupCount;
    if (index >= 16)
        /* We don't need an explicit warning for this case.  The code that
         * processes the log can detect this has happened by looking for lines
         * which report lookupCount >= 16. */
        return;

    placeholderStackTop->flags |= (flags & 3) << (index * 2);
}

/* Check if the current placeholder matches the provided placeholderID and the
 * current PyFrameObject. */
int currentPlaceholderMatches(uint16_t placeholderID) {
    /* We make the placeholderID argument a uint16_t (like the placeholderID
     * field of PlaceholderInfo) because if the argument was signed, we would
     * run into problems with negative IDs (which are used to indicate calls to
     * Cheetah.Template.getVar / .hasVar). */
    return placeholderStackTop != &placeholderStack[PLACEHOLDER_STACK_SIZE] &&
        placeholderStackTop->pythonStackPointer == PyEval_GetFrame() &&
        placeholderStackTop->placeholderID == placeholderID;
}

/*** Placeholder Logging ***/

/* We log the following information about each placeholder evaluation:
 *
 *  - Deploy SHA, template name hash, placeholder ID:  Together, these
 *    uniquely identify a placeholder in a particular version of a particular
 *    template file.  Processing code can obtain the actual template name from
 *    the deploy SHA and the name hash by hashing the names of all compiled
 *    templates in the deployed version of yelp-main and looking for a hash
 *    that matches the one in the log.
 *
 *  - Namespace index:  This lets us detect use of Cheetah's searchlist
 *    feature, by looking for placeholders that have different namespace
 *    indices on different evaluations.
 *
 *  - Lookup count lets us know how many bits in the "flags" field are actually
 *    interesting.  We could live without this, but it makes parsing the log
 *    file a little bit easier - this way, we don't have to parse each .tmpl
 *    file to find the correct count for the placeholder.
 *
 *  - The list of flags lets us detect where autokey/autocall is being used.
 */

/* We send data to Scribe by calling the Python function clog.log_line. */
static PyObject *clogMod_log_line;

/* We consider logging only (loggingFraction / 10)% of placeholder evaluations.
 * This defaults to zero, but it can be adjusted from Python by calling
 * Cheetah.namemapper.setLoggingPercent.  This lets the percentage be adjusted
 * on a per-request basis.
 */
static int loggingFraction = 0;

/* Simple hash for strings.  We use this for hashing template filenames, so we
 * don't have to log the whole name. */
uint32_t hashString(const char* str) {
    uint32_t hash = 0;
    while (*str != '\0') {
        hash = hash * 37 + (uint8_t)(*str);
        ++str;
    }
    return hash;
}

/* Find the interesting parts of a template filename.  For our purposes,
 * "interesting" parts are (1) the SHA of the current deployment (included in
 * the directory name "r2013...-aabbccddee-deploy-some-branch") and (2) the
 * path relative to the deployment (or yelp-main checkout) directory, which is
 * sufficient to identify the template itself. */
void extractPathComponents(const char *filename, const char **deploySHAStartPtr, const char **templateNameStartPtr) {
    const char *deploySHAStart = NULL;
    const char *templateNameStart = NULL;

    const char *foundDeploy;
    const char *foundYelpMain;
    const char *foundSlash = NULL;

    /* Check for various things that look like yelp-main checkouts.  Set
     * 'foundSlash' to point to the slash following the checkout directory once
     * we find it. */

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

    /* Next, look for components containing "yelp-main".  This is how usually
     * it works in dev playgrounds. */
    if (foundSlash == NULL) {
        foundYelpMain = strstr(filename, "yelp-main");
        if (foundYelpMain != NULL) {
            foundSlash = strchr(foundYelpMain, '/');
        }
    }

    /* Finally, check if the path starts with "./".  If so, we assume "." is a
     * yelp-main checkout, because that's how things work on buildbot. */
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
        /* We didn't find anything that looks like a deployment, so hash the
         * whole fileName instead.  It's better than nothing - maybe if we are
         * lucky we can figure out the format and recover the actual name. */
        templateNameHash = hashString(fileName);
    }

    /* We log everything in hexadecimal, with each field separated by a space.
     * So the expected output width is: 10 (deploy SHA) + 8 (fileNameHash) +
     * 4 (placeholderID) + 2 (nameSpaceIndex) + 2 (lookupCount) +
     * 8 (flags) + 5 (spaces) = 39. */
    char buf[48];
    /* The 'size' argument to snprintf includes the terminating \0, which is
     * always written (even if the output is too long for the buffer). */
    snprintf(buf, 48, "%.10s %x %x %x %x %x",
            deploySHAStart,
            templateNameHash,
            placeholderStackTop->placeholderID,
            placeholderStackTop->nameSpaceIndex,
            placeholderStackTop->lookupCount,
            placeholderStackTop->flags);

    /* Call clog.log_line via Python to do the actual logging. */
    PyObject_CallFunction(clogMod_log_line, "ss", "tmp_namemapper_placeholder_uses", buf);
}



/*** Bloom filter ***/

/* We use a Bloom filter to avoid logging duplicate entries.  Each time we try
 * to log a placeholder, we first check that it is not in the bloom filter
 * already.  If it's not there, then we actually log the information and insert
 * it into the filter.
 *
 * (We actually use more than one Bloom filter - see the Filter Group section
 * for details.) */

/* We want a bloom filter that can hold n = 2000 elements with <0.01% false
 * positive rate.  According to wikipedia, we need m = 2**16 bits.  With that
 * many bits, we can get away with only eight 16-bit hash functions and keep
 * P(false positive) < 0.01% for up to 3000 elements.
 *
 * http://en.wikipedia.org/wiki/Bloom_filter#Probability_of_false_positives
 */

/* The number of bits in the bloom filter.  Wikipedia calls this 'm'. */
#define BLOOM_FILTER_SIZE (1 << 16)

/* The type to use for an individual array element. */
typedef uint64_t bloom_filter_chunk_type;

/* The number of bits stored by each array element. */
#define BLOOM_FILTER_CHUNK_BITS (sizeof(bloom_filter_chunk_type) * 8)

struct BloomFilter {
    bloom_filter_chunk_type data[BLOOM_FILTER_SIZE / BLOOM_FILTER_CHUNK_BITS];
};

/* The number of hash functions to use for the bloom filter.  Wikipedia calls
 * this 'k'. */
#define BLOOM_FILTER_HASHES 8

/* A bunch of prime numbers to use for hash functions.  We need five primes for
 * each hash function.
 *
 * The numbers in this array were selected at random from a list of all primes
 * below 10,000,000. */
static const int PRIMES[BLOOM_FILTER_HASHES * 5] = {
    9753463,  123979, 8701949, 1069219, 3704537,
    6366473,  272693, 1829587, 3188723, 8039501,
    6032921, 3638497, 4263253, 1788601, 9295687,
    4069397, 9887611, 3195623, 2066137, 2131799,
    7250263, 6188641, 1283903, 3376049, 2818817,
    8308891, 2677093, 6490409, 4825627, 6902711,
    3640543, 3535769, 8084729, 2022263, 1332329,
    2434013, 1608259, 3452689,  302143, 1366019,
};

/* Apply all 'k' hash functions to a PlaceholderInfo item.
 *
 * Each hash function combines five components:
 *  - filename hash
 *  - placeholder ID
 *  - namespace index
 *  - lookup count
 *  - flags
 *
 * We combine these five pieces by multiplying each by a large prime and adding
 * up the results.  I don't know how good of a hash this actually is, but it
 * seems to work well enough to avoid false positives in my tests.
 *
 * hashOutput should point to an array of BLOOM_FILTER_HASHES elements.  After
 * calling this function, the array will be filled with values in the range
 * 0 <= h < BLOOM_FILTER_SIZE.
 */
void bloomFilterHash(struct PlaceholderInfo *placeholderInfo, uint32_t* hashOutput) {
    int i;
    uint32_t hash;

    PyObject* fileNamePyString = placeholderInfo->pythonStackPointer->f_code->co_filename;
    uint32_t fileNameHash = hashString(PyString_AsString(fileNamePyString));

    for (i = 0; i < BLOOM_FILTER_HASHES; ++i) {
        hash =
            PRIMES[i * 5 + 0] * fileNameHash  +
            PRIMES[i * 5 + 1] * placeholderInfo->placeholderID +
            PRIMES[i * 5 + 2] * placeholderInfo->nameSpaceIndex +
            PRIMES[i * 5 + 3] * placeholderInfo->lookupCount +
            PRIMES[i * 5 + 4] * placeholderInfo->flags;

        hash %= BLOOM_FILTER_SIZE;

        hashOutput[i] = hash;
    }
}

/* Initialize a bloom filter to an empty state. */
void bloomFilterInit(struct BloomFilter *bloomFilter) {
    /* Fill the 'data' array with all zeros. */
    memset(&bloomFilter->data, 0, sizeof(bloomFilter->data));
}

/* Insert a PlaceholderInfo item into a bloom filter. */
void bloomFilterInsert(struct BloomFilter *bloomFilter, struct PlaceholderInfo* placeholderInfo) {
    int i;
    uint32_t hash[BLOOM_FILTER_HASHES];

    /* Hash the PlaceholderInfo into the 'hash' array. */
    bloomFilterHash(placeholderInfo, hash);

    for (i = 0; i < BLOOM_FILTER_HASHES; ++i) {
        uint32_t index = hash[i] / BLOOM_FILTER_CHUNK_BITS;
        uint32_t offset = hash[i] % BLOOM_FILTER_CHUNK_BITS;

        /* This can't overflow the 'data' array because bloomFilterHash
         * guarantees 0 <= hash[i] < BLOOM_FILTER_SIZE and there are
         * BLOOM_FILTER_SIZE / BLOOM_FILTER_CHUNK_BITS elements in 'data'. */
        bloomFilter->data[index] |= (1L << offset);
    }
}

/* Check if a PlaceholderInfo has already been inserted into a bloom filter.
 * Returns 1 if the placeholder might have been inserted, and 0 if it
 * definitely has not been inserted. */
int bloomFilterContains(struct BloomFilter *bloomFilter, struct PlaceholderInfo* placeholderInfo) {
    int i;
    uint32_t hash[BLOOM_FILTER_HASHES];

    bloomFilterHash(placeholderInfo, hash);

    for (i = 0; i < BLOOM_FILTER_HASHES; ++i) {
        uint32_t index = hash[i] / BLOOM_FILTER_CHUNK_BITS;
        uint32_t offset = hash[i] % BLOOM_FILTER_CHUNK_BITS;

        if ((bloomFilter->data[index] & (1L << offset)) == 0)
            return 0;
    }

    return 1;
}

/* Remove all items from a bloom filter. */
void bloomFilterClear(struct BloomFilter *bloomFilter) {
    bloomFilterInit(bloomFilter);
}



/*** Filter Group ***/

/* The amount of space required for a bloom filter is proportional to the
 * number of items we wish to insert (if we hold constant the probability of
 * false positives).  This means if we want to avoid using tons of space and
 * also avoid large numbers of false positives, we need to clear the filter
 * periodically.  If we did this with a single filter, then immediately after
 * the filter was cleared, we would end up with a large number of redundant log
 * entries, since the logging code would forget that it had just recorded
 * identical entries.
 *
 * Instead, we use multiple bloom filters (which I called a "filter group"), as
 * follows:
 *  - To insert into the filter group, insert into all component bloom filters.
 *  - To check for membership in the filter group, check for membership in the
 *    "current filter".
 *  - After every N insertions, clear the current filter, and make the next
 *    filter in the group the new current filter.
 * This allows the logging code to lose only part of its "memory" when we clear
 * a filter, since the newly-current filter contains some fraction of the items
 * that were present in the previously-current filter.
 */

/* Number of bloom filters to include in the filter group. */
#define FILTER_GROUP_SIZE 2
/* Clear a filter after this many insertions. */
#define FILTER_GROUP_ROTATION_INTERVAL 1000
/* Note that each bloom filter will have SIZE * ROTATION_INTERVAL elements
 * added to it.  The bloom filter parameters should be tuned accordingly. */

struct FilterGroup {
    /* The actual bloom filters. */
    struct BloomFilter bloomFilters[FILTER_GROUP_SIZE];
    /* The index of the current filter to read from. */
    int currentFilterIndex;
    /* The number of insertions since the last time a filter was cleared. */
    int insertCount;
};

struct FilterGroup dedupeFilterGroup;

/* Initialize a filter group. */
void filterGroupInit(struct FilterGroup *filterGroup) {
    int i;
    for (i = 0; i < FILTER_GROUP_SIZE; ++i) {
        bloomFilterInit(&filterGroup->bloomFilters[i]);
    }
    filterGroup->currentFilterIndex = 0;
    filterGroup->insertCount = 0;
}

/* Insert a PlaceholderInfo item into a filter group. */
void filterGroupInsert(struct FilterGroup *filterGroup, struct PlaceholderInfo* placeholderInfo) {
    int i;
    /* Insert into all component bloom filters. */
    for (i = 0; i < FILTER_GROUP_SIZE; ++i) {
        bloomFilterInsert(&filterGroup->bloomFilters[i], placeholderInfo);
    }

    ++filterGroup->insertCount;
    if (filterGroup->insertCount >= FILTER_GROUP_ROTATION_INTERVAL) {
        /* Clear the current filter and change to the next filter in the group.
         */
        bloomFilterClear(&filterGroup->bloomFilters[filterGroup->currentFilterIndex]);
        filterGroup->currentFilterIndex = (filterGroup->currentFilterIndex + 1) % FILTER_GROUP_SIZE;

        filterGroup->insertCount = 0;
    }
}

/* Check if a filter group contains a particular PlaceholderInfo. */
int filterGroupContains(struct FilterGroup *filterGroup, struct PlaceholderInfo* placeholderInfo) {
    return bloomFilterContains(&filterGroup->bloomFilters[filterGroup->currentFilterIndex], placeholderInfo);
}



/*** High-level placeholder tracking functions ***/

void startPlaceholder(int placeholderID) {
    pushPlaceholderStack(placeholderID);
}

#define FP_SUCCESS  1
#define FP_ERROR    0

void finishPlaceholder(int placeholderID, int status) {
    if (currentPlaceholderMatches(placeholderID)) {
        if (status != FP_SUCCESS) {
            placeholderStackTop->lookupCount |= 0x80;
        }

        if (rand() % 1000 < loggingFraction) {
            if (!filterGroupContains(&dedupeFilterGroup, placeholderStackTop)) {
                logPlaceholderInfo();
                filterGroupInsert(&dedupeFilterGroup, placeholderStackTop);
            }
        }
        popPlaceholderStack();
    } else {
        // TODO: warn
    }
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
     * placeholder that's not the current stack top, there's a bug somewhere.
     */
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

    if (theValue == NULL) {
        finishPlaceholder(placeholderID, FP_ERROR);
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

    startPlaceholder(placeholderID);

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

    if (theValue == NULL) {
        /* An error of some kind occurred.  We are done with this placeholder,
         * since its evaluation has raised some kind of exception. */
        finishPlaceholder(placeholderID, FP_ERROR);
    }

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

    startPlaceholder(placeholderID);

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

    if (theValue == NULL) {
        finishPlaceholder(placeholderID, FP_ERROR);
    }

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

    startPlaceholder(placeholderID);

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

    if (theValue == NULL) {
        finishPlaceholder(placeholderID, FP_ERROR);
    }

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

    finishPlaceholder(placeholderID, FP_SUCCESS);

    /* Python doesn't automatically increment the reference count of the
     * function's return value, so we have to do it manually. */
    Py_XINCREF(obj);
    return obj;
}

static PyObject *namemapper_setLoggingPercent(PyObject *self, PyObject *args, PyObject *keywds)
{
    /* python function args */
    float loggingPercent;

    static char *kwlist[] = {"loggingPercent", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, keywds, "f", kwlist, &loggingPercent)) {
        return NULL;
    }

    loggingFraction = (int)(10 * loggingPercent);

    return Py_None;
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
  {"setLoggingPercent", (PyCFunction)namemapper_setLoggingPercent,  METH_VARARGS|METH_KEYWORDS},
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

    filterGroupInit(&dedupeFilterGroup);

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
