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



static inline unsigned long long rdtsc(void)
{
  unsigned hi, lo;
  __asm__ __volatile__ ("rdtsc" : "=a"(lo), "=d"(hi));
  return ( (unsigned long long)lo)|( ((unsigned long long)hi)<<32 );
}

struct Timer {
    uint64_t start;
    uint64_t total;
    uint32_t count;
};

void timerStart(struct Timer* timer) {
    timer->start = rdtsc();
}

void timerEnd(struct Timer* timer, int incrementCount) {
    uint64_t diff = rdtsc() - timer->start;
    timer->total += diff;
    if (incrementCount)
        timer->count += 1;
}

void timerIncrementCount(struct Timer* timer) {
    timer->count += 1;
}

uint64_t timerAverage(struct Timer* timer) {
    uint32_t count = timer->count;
    if (count == 0)
        return 0;
    return timer->total / count;
}

void timerInit(struct Timer* timer) {
    timer->total = 0;
    timer->count = 0;
}

#define START(what)     (timerStart(&time##what))
#define END(what,inc)   (timerEnd(&time##what, inc))
#define COUNT(what)     (timerIncrementCount(&time##what))
#define SEEN(what)      (time##what.count)
#define TIME(what)      (timerAverage(&time##what))

struct Timer timeStart, timePlaceholder, timeFinish, timeLog;



static PyObject *NotFound;   /* locally-raised exception */
static PyObject *TooManyPeriods;   /* locally-raised exception */
static PyObject* pprintMod_pformat; /* used for exception formatting */



/* *************************************************************************** */
/* Instrumentation code */
/* *************************************************************************** */



/*** PlaceholderInfo ***/

/* All the interesting information about an active placeholder evaluation. */
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
     * lookups (one each for "x", "y", and "z"), which are performed in the
     * course of two namemapper calls (VFFSL on "x.y", and VFN on "z").  (The
     * "[1]" part does not invoke the namemapper, so it is not counted as a
     * lookup.) */
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



/*** Placeholder Stack ***/

/* We keep a stack of placeholders being evaluated.  This lets us handle nested
 * evaluations properly.  For example, evaluation of "$x[$y].z" will start by
 * looking up "x" for the outer placeholder, then will fully evaluate the inner
 * placeholder "$y", and finally will finish evaluating the outer placeholder
 * by looking up "z". */

/* The maximum number of items that can be stored on the stack.  We limit the
 * size to avoid dynamic allocation during placeholder evaluation, as it would
 * increase the cost of the placeholder instrumentation by about 50%.
 *
 * In testing, I've never seen the stack depth exceed 3, so 64 seems like it
 * should be high enough to avoid problems.
 */
#define PLACEHOLDER_STACK_SIZE 64

/* A stack of PlaceholderInfo records. */
struct PlaceholderStack {
    /* Storage for the items in the stack.  This array starts with all entries
     * uninitialized.  The stack grows downward, so only items at addresses >=
     * current are valid.
     */
    struct PlaceholderInfo items[PLACEHOLDER_STACK_SIZE];

    /* A pointer to the most recently pushed stack element.  This points
     * somewhere in or past-the-end of 'items', with &items[0] indicating that
     * the stack is full, and &items[PLACEHOLDER_STACK_SIZE] (past-the-end)
     * indicating that the stack is empty. */
    struct PlaceholderInfo *current;
};

/* Initialize a PlaceholderStack.  The stack starts out empty. */
void placeholderStackInit(struct PlaceholderStack *stack) {
    stack->current = &stack->items[PLACEHOLDER_STACK_SIZE];
}

/* Add a new element to the stack by adjusting 'stack->current'.  The new
 * element is left uninitialized - the caller is expected to initialize it.
 * This function returns 1 on success and 0 on failure (if the stack is full).
 */
int placeholderStackPush(struct PlaceholderStack *stack) {
    if (stack->current == &stack->items[0]) {
        /* The stack is full.  Tell the caller about this so they know not to
         * try to initialize stack->current. */
        return 0;
    } else {
        --stack->current;
        return 1;
    }
}

/* Remove an element from the stack.  Returns 1 on success and 0 on failure (if
 * the stack is already empty). */
int placeholderStackPop(struct PlaceholderStack *stack) {
    if (stack->current == &stack->items[PLACEHOLDER_STACK_SIZE]) {
        /* The stack is already empty.  This probably indicates a bug. */
        return 0;
    } else {
        ++stack->current;
        return 1;
    }
}

/* Check if the stack is empty. */
int placeholderStackIsEmpty(struct PlaceholderStack *stack) {
    return (stack->current == &stack->items[PLACEHOLDER_STACK_SIZE]);
}



/*** Placeholder Logging ***/

/* We log the following information about each placeholder evaluation:
 *
 *  - Template name hash, placeholder ID:  Together with the deploy SHA, these
 *    uniquely identify a placeholder in a particular version of a particular
 *    template file.  Processing code can obtain the actual template name from
 *    the deploy SHA and the name hash by hashing the names of all compiled
 *    templates in that version of yelp-main and looking for a hash that
 *    matches the one in the log.
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

/* A LogItem is similar to a PlaceholderInfo, but it has the template name hash
 * instead of the Python stack fram pointer.  This means the LogItem is still
 * usable after the stack frame has been deallocated. */
struct LogItem {
    uint32_t templateNameHash;
    uint16_t placeholderID;
    uint8_t nameSpaceIndex;
    uint8_t lookupCount;
    uint32_t flags;
};

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

/* Given a filename, find the template name relative to yelp-main/ or the
 * deploy directory. */
const char* findTemplateName(const char *filename) {
    const char *foundDeploy;
    const char *foundYelpMain;
    const char *foundSlash = NULL;

    /* First check for path components that look like deployment directories.
     */
    foundDeploy = strstr(filename, "-deploy");
    if (foundDeploy != NULL) {
        /* Look for a slash after the -deploy part and return the following
         * character. */
        foundSlash = strchr(foundDeploy, '/');
        if (foundSlash != NULL)
            return foundSlash + 1;
    }

    /* Next, look for components containing "yelp-main".  This is how usually
     * it works in dev playgrounds. */
    foundYelpMain = strstr(filename, "yelp-main");
    if (foundYelpMain != NULL) {
        foundSlash = strchr(foundYelpMain, '/');
        if (foundSlash != NULL)
            return foundSlash + 1;
    }

    /* Finally, check if the path starts with "./".  If so, we assume "." is a
     * yelp-main checkout, because that's how things work on buildbot. */
    if (strstr(filename, "./") == filename) {
        foundSlash = strchr(filename, '/');
        if (foundSlash != NULL)
            return foundSlash + 1;
    }

    /* We didn't find a yelp-main directory anywhere. */
    return NULL;
}

/* Construct a LogItem containing the same data as a PlaceholderInfo. */
void logItemInit(struct LogItem *logItem, struct PlaceholderInfo *placeholderInfo) {
    /* Populate the templateNameHash field. */
    PyObject *pyFileName = placeholderInfo->pythonStackPointer->f_code->co_filename;
    const char *fileName = PyString_AsString(pyFileName);

    const char *templateName = findTemplateName(fileName);
    if (templateName == NULL)
        templateName = fileName;

    logItem->templateNameHash = hashString(templateName);

    /* Populate the other fields. */

    logItem->placeholderID = placeholderInfo->placeholderID;
    logItem->nameSpaceIndex = placeholderInfo->nameSpaceIndex;
    logItem->lookupCount = placeholderInfo->lookupCount;
    logItem->flags = placeholderInfo->flags;
}



/*** Log Item Buffer ***/

/* We keep a buffer of data we plan to log.  When the template rendering has
 * finished, we take the whole buffer and dump it into Scribe all at once.
 * This means we don't have the overhead of multiple Scribe calls, and we don't
 * need to worry about interleaving lines from different processes. */

/* The maximum number of PlaceholderInfos in the buffer.  Normally biz_details
 * produces about 5,000 entries after deduplication, so setting the size to
 * 20,000 should be plenty.
 */
#define LOG_BUFFER_SIZE 20000

struct LogBuffer {
    /* An array for storing LogItems.  This starts uninitialized.  Only items
     * at locations before 'nextSlot' are valid. */
    struct LogItem items[LOG_BUFFER_SIZE];

    /* A pointer to the next available slot in the buffer.  This always points
     * to somewhere in 'items', or to past-the-end if the buffer is full. */
    struct LogItem *nextSlot;

    /* The number of items we tried to insert, which may be greater than the
     * number *actually* inserted.  (We discard any items inserted after the
     * buffer is full, instead incrementing this counter to let consumers of
     * the log know that there was an overflow.) */
    int insertAttempts;
};

void logBufferInit(struct LogBuffer *buffer) {
    buffer->nextSlot = &buffer->items[0];
    buffer->insertAttempts = 0;
}

void logBufferInsert(struct LogBuffer *buffer, struct LogItem *item) {
    ++buffer->insertAttempts;

    if (buffer->nextSlot == &buffer->items[LOG_BUFFER_SIZE]) {
        /* We can't store anything else to the buffer.  That's unfortunate, but
         * we can't do much about it. */
        return;
    }

    /* Copy the item into the next slot, and increment the nextSlot pointer. */
    memcpy(/*dest = */buffer->nextSlot, /*src = */item, sizeof(struct LogItem));
    ++buffer->nextSlot;
}

int logBufferGetCount(struct LogBuffer *buffer) {
    return (buffer->nextSlot - &buffer->items[0]);
}



/*** Bloom Filter ***/

/* We use a Bloom filter to avoid logging duplicate entries.  Each time we try
 * to record a LogItem, we first check that it is not in the bloom filter
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

/* The maximum number of items that we expect to be stored in a bloom filter.
 * It is possible to store more items, but the false positive rate may increase
 * beyond 0.01%. */
#define BLOOM_FILTER_MAX_ITEMS 2000

/* The number of bits in the bloom filter.  Wikipedia calls this 'm'. */
#define BLOOM_FILTER_SIZE (1 << 16)

/* The type to use for an individual array element. */
typedef uint64_t bloom_filter_chunk_type;

/* The number of bits stored by each array element. */
#define BLOOM_FILTER_CHUNK_BITS (sizeof(bloom_filter_chunk_type) * 8)

struct BloomFilter {
    /* The array of bits. */
    bloom_filter_chunk_type data[BLOOM_FILTER_SIZE / BLOOM_FILTER_CHUNK_BITS];

    /* The number of distinct items that have been inserted. */
    int itemCount;
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

/* Apply all 'k' hash functions to a LogItem.
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
void bloomFilterHash(struct LogItem *item, uint32_t* hashOutput) {
    int i;
    uint32_t hash;

    for (i = 0; i < BLOOM_FILTER_HASHES; ++i) {
        hash =
            PRIMES[i * 5 + 0] * item->templateNameHash  +
            PRIMES[i * 5 + 1] * item->placeholderID +
            PRIMES[i * 5 + 2] * item->nameSpaceIndex +
            PRIMES[i * 5 + 3] * item->lookupCount +
            PRIMES[i * 5 + 4] * item->flags;

        hash %= BLOOM_FILTER_SIZE;

        hashOutput[i] = hash;
    }
}

/* Initialize a bloom filter to an empty state. */
void bloomFilterInit(struct BloomFilter *bloomFilter) {
    /* Fill the 'data' array with all zeros. */
    memset(&bloomFilter->data, 0, sizeof(bloomFilter->data));

    bloomFilter->itemCount = 0;
}

int bloomFilterOperate(struct BloomFilter *filter, struct LogItem* item,
        int shouldInsert) {
    int i;
    uint32_t hash[BLOOM_FILTER_HASHES];
    int wasPresent = 1;

    /* Hash the PlaceholderInfo into the 'hash' array. */
    bloomFilterHash(item, hash);

    for (i = 0; i < BLOOM_FILTER_HASHES; ++i) {
        uint32_t index = hash[i] / BLOOM_FILTER_CHUNK_BITS;
        uint32_t offset = hash[i] % BLOOM_FILTER_CHUNK_BITS;

        /* Check if the corresponding bit is set.  If not, set it and remember
         * that this item was not initially present in the filter. */

        /* This can't overflow the 'data' array because bloomFilterHash
         * guarantees 0 <= hash[i] < BLOOM_FILTER_SIZE and there are
         * BLOOM_FILTER_SIZE / BLOOM_FILTER_CHUNK_BITS elements in 'data'. */
        if ((filter->data[index] & (1L << offset)) == 0) {
            wasPresent = 0;
            if (shouldInsert) {
                filter->data[index] |= (1L << offset);
            }
        }
    }

    if (!wasPresent) {
        ++filter->itemCount;
    }
    return wasPresent;
}

/* Check if a LogItem is present in the bloom filter, and if not, add it.  This
 * is somewhat faster than performing the two operations separately, because we
 * only need to compute the hashes once. */
int bloomFilterContainsAndInsert(struct BloomFilter *filter, struct LogItem* item) {
    return bloomFilterOperate(filter, item, 1);
}

int bloomFilterContains(struct BloomFilter *filter, struct LogItem* item) {
    return bloomFilterOperate(filter, item, 0);
}


/* We send data to Scribe by calling the Python function clog.log_line. */
static PyObject *clogMod_log_line;

/* Get the deploy SHA from util.version on startup, then save it here so we can
 * include it in our log lines.*/
#define DEPLOY_SHA_SIZE 10
char deploySHA[DEPLOY_SHA_SIZE + 1];

void deploySHAInit(void) {
    PyObject* utilVersionMod = PyImport_ImportModule("util.version");
    PyObject* versionSHAFunc = PyObject_GetAttrString(utilVersionMod, "version_sha");
    PyObject* pythonDeploySHA = PyObject_CallObject(versionSHAFunc, NULL);

    strncpy(deploySHA, PyString_AsString(pythonDeploySHA), sizeof(deploySHA));
    /* strncpy does not guarantee that the destination is null-terminated, so
     * have to make sure it is ourselves. */
    deploySHA[sizeof(deploySHA) - 1] = '\0';
}



/*** High-level placeholder tracking functions ***/

/* The stack of placeholders we are currently evaluating. */
struct PlaceholderStack activePlaceholders;

/* A Bloom filter for deduplicating LogItems. */
struct BloomFilter dedupeFilter; 

/* The buffer of LogItems we have decided to record. */
struct LogBuffer buffer;

/* Flag to indicate whether we should do instrumentation. */
int instrumentationEnabled = 0;

void instrumentStartRequest(void) {
    START(Start);
    placeholderStackInit(&activePlaceholders);
    bloomFilterInit(&dedupeFilter);
    logBufferInit(&buffer);
    instrumentationEnabled = 1;
    END(Start, 1);

    timerInit(&timeStart);
    timerInit(&timePlaceholder);
    timerInit(&timeFinish);
    timerInit(&timeLog);
}

void instrumentFinishRequest(void) {
    if (!instrumentationEnabled) {
        return;
    }

    START(Finish);

    instrumentationEnabled = 0;

    /* If there is nothing recorded, don't bother logging anything. */
    if (buffer.insertAttempts == 0) {
        return;
    }

    PyObject *rawString = PyString_FromStringAndSize((const char*)&buffer.items,
            logBufferGetCount(&buffer) * sizeof(struct LogItem));

    PyObject *zlibMod = PyImport_ImportModule("zlib");
    PyObject *zlibMod_compress = PyObject_GetAttrString(zlibMod, "compress");

    PyObject *gzippedString = PyObject_CallFunction(zlibMod_compress, "O", rawString);

    PyObject *base64Mod = PyImport_ImportModule("base64");
    PyObject *base64Mod_b64encode = PyObject_GetAttrString(base64Mod, "b64encode");

    PyObject *base64EncodedString = PyObject_CallFunction(base64Mod_b64encode, "O", gzippedString);

    PyObject *formatString = PyString_FromString("%s %d %s");
    PyObject *formatArgs = Py_BuildValue("siO", deploySHA, buffer.insertAttempts, base64EncodedString);

    PyObject *formattedLine = PyString_Format(formatString, formatArgs);

    /* Release all objects except for formattedLine. */
    Py_DECREF(rawString);
    Py_DECREF(zlibMod);
    Py_DECREF(zlibMod_compress);
    Py_DECREF(gzippedString);
    Py_DECREF(base64Mod);
    Py_DECREF(base64Mod_b64encode);
    Py_DECREF(base64EncodedString);
    Py_DECREF(formatString);
    Py_DECREF(formatArgs);

    END(Finish, 1);
    START(Log);

    PyObject_CallFunction(clogMod_log_line, "sO", "tmp_namemapper_placeholder_uses", formattedLine);
    Py_DECREF(formattedLine);

    END(Log, 1);

    /* Log timer results */
    char buf[256];
    snprintf(buf, 256, "times: %lu %lu(%lu/%u) %lu %lu",
            TIME(Start), TIME(Placeholder), timePlaceholder.total, timePlaceholder.count, TIME(Finish), TIME(Log));

    PyObject_CallFunction(clogMod_log_line, "ss", "tmp_namemapper_placeholder_uses", buf);
}

void instrumentStartPlaceholder(int placeholderID) {
    if (!instrumentationEnabled)
        return;

    START(Placeholder);

    if (placeholderStackPush(&activePlaceholders)) {
        activePlaceholders.current->pythonStackPointer = PyEval_GetFrame();
        activePlaceholders.current->placeholderID = placeholderID;

        /* The namespace index will be set to a more appropriate value once we
         * finish the first lookup step.  If the first lookup step fails, we
         * don't need to do anything but leave the index as NS_NOT_FOUND. */
        activePlaceholders.current->nameSpaceIndex = NS_NOT_FOUND;

        activePlaceholders.current->lookupCount = 0;
        activePlaceholders.current->flags = 0;
    }

    END(Placeholder, 0);
}

/* Record the flags for a lookup step of the current placeholder. */
void instrumentRecordLookup(int flags) {
    if (!instrumentationEnabled)
        return;

    START(Placeholder);

    int index = activePlaceholders.current->lookupCount;
    ++activePlaceholders.current->lookupCount;
    if (index >= 16)
        /* We don't need an explicit warning for this case.  The code that
         * processes the log can detect this has happened by looking for lines
         * which report lookupCount >= 16. */
        return;

    activePlaceholders.current->flags |= (flags & 3) << (index * 2);

    END(Placeholder, 0);
}

void instrumentRecordNameSpaceIndex(int nameSpaceIndex) {
    if (!instrumentationEnabled)
        return;

    START(Placeholder);

    activePlaceholders.current->nameSpaceIndex = nameSpaceIndex;

    END(Placeholder, 0);
}

/* Check if the current placeholder matches the provided placeholderID and the
 * current PyFrameObject. */
int instrumentCurrentPlaceholderMatches(uint16_t placeholderID) {
    /* We make the placeholderID argument a uint16_t (like the placeholderID
     * field of PlaceholderInfo) because if the argument was signed, we would
     * run into problems with negative IDs (which are used to indicate calls to
     * Cheetah.Template.getVar / .hasVar). */
    START(Placeholder);
    int result =
        instrumentationEnabled &&
        !placeholderStackIsEmpty(&activePlaceholders) &&
        activePlaceholders.current->pythonStackPointer == PyEval_GetFrame() &&
        activePlaceholders.current->placeholderID == placeholderID;
    END(Placeholder, 0);
    return result;
}

#define FP_SUCCESS  1
#define FP_ERROR    0

void instrumentFinishPlaceholder(int placeholderID, int status) {
    if (!instrumentationEnabled)
        return;

    START(Placeholder);

    if (instrumentCurrentPlaceholderMatches(placeholderID)) {
        if (status != FP_SUCCESS) {
            activePlaceholders.current->lookupCount |= 0x80;
        }

        struct LogItem item;
        logItemInit(&item, activePlaceholders.current);

        if (!bloomFilterContainsAndInsert(&dedupeFilter, &item)) {
            /* The item was not already present. */
            logBufferInsert(&buffer, &item);

            if (dedupeFilter.itemCount > BLOOM_FILTER_MAX_ITEMS) {
                /* Clear out the filter once it hits MAX_ITEMS, to avoid
                 * increasing the false positive rate. */
                bloomFilterInit(&dedupeFilter);
            }
        }

        placeholderStackPop(&activePlaceholders);
    } else {
        // TODO: warn
    }

    END(Placeholder, 1);
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
    placeholderIsCurrent = instrumentCurrentPlaceholderMatches(placeholderID);
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
            instrumentRecordLookup(currentFlags);
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
        instrumentFinishPlaceholder(placeholderID, FP_ERROR);
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

    instrumentStartPlaceholder(placeholderID);

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
        instrumentFinishPlaceholder(placeholderID, FP_ERROR);
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

    instrumentStartPlaceholder(placeholderID);

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
        instrumentFinishPlaceholder(placeholderID, FP_ERROR);
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

    instrumentStartPlaceholder(placeholderID);

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
        instrumentFinishPlaceholder(placeholderID, FP_ERROR);
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

    instrumentFinishPlaceholder(placeholderID, FP_SUCCESS);

    /* Python doesn't automatically increment the reference count of the
     * function's return value, so we have to do it manually. */
    Py_XINCREF(obj);
    return obj;
}

static PyObject *namemapper_startLogging(PyObject *self, PyObject *args, PyObject *keywds)
{
    instrumentStartRequest();
    return Py_None;
}

static PyObject *namemapper_finishLogging(PyObject *self, PyObject *args, PyObject *keywds)
{
    instrumentFinishRequest();
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
  {"startLogging", (PyCFunction)namemapper_startLogging,  METH_VARARGS|METH_KEYWORDS},
  {"finishLogging", (PyCFunction)namemapper_finishLogging,  METH_VARARGS|METH_KEYWORDS},
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

    deploySHAInit();

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




/* *************************************************************************** */
/* Tests for instrumentation code */
/* *************************************************************************** */

/* To run the tests:
 *      gcc -DBUILD_TESTS -O2 -I/usr/lib/python2.6 -lpython2.6 _namemapper.c
 *      ./a.out
 * The tests have passed if you see "0 / ## assertions failed" for each
 * section, and the test program exits successfully (without segfault or other
 * errors).
 * 
 * To run the tests with valgrind:
 *      gcc -DBUILD_TESTS -DTEST_WITH_VALGRIND -O2 -I/usr/lib/python2.6 -lpython2.6 _namemapper.c
 *      valgrind ./a.out
 * The tests have passed if you see "0 / ## assertions failed" for each
 * section, and valgrind reports no errors.
 *
 * (The -DTEST_WITH_VALGRIND flag disables tests which call into Python, since
 * the Python interpreter generates tons of valgrind errors.)
 */

#ifdef BUILD_TESTS

#include <assert.h>

#define DEFINE_COUNTERS() \
    int asserts_passed = 0, asserts_total = 0

#define CHECK_THAT(what, cond) \
    do {\
        printf("%-70s   ", what);\
        if (cond) {\
            printf("[  OK  ]\n");\
            ++asserts_passed;\
        } else {\
            printf("[FAILED]\n"); \
        }\
        ++asserts_total;\
    } while(0)

#define SUMMARIZE() \
    do {\
        printf("%d / %d assertions failed\n\n",\
                asserts_total - asserts_passed, asserts_total);\
    } while(0)

void testPlaceholderStack(void) {
    DEFINE_COUNTERS();
    struct PlaceholderStack stack;
    int i;

    placeholderStackInit(&stack);

    CHECK_THAT("the stack starts empty",
            placeholderStackIsEmpty(&stack));

    struct PlaceholderInfo *current1 = stack.current;
    placeholderStackPush(&stack);
    struct PlaceholderInfo *current2 = stack.current;
    CHECK_THAT("Push() changes the value of 'current'",
            current1 != current2);

    CHECK_THAT("Push() makes the stack nonempty",
            !placeholderStackIsEmpty(&stack));

    placeholderStackPop(&stack);
    struct PlaceholderInfo *current3 = stack.current;
    CHECK_THAT("Pop() after Push() restores the previous value to 'current'",
            current1 == current3);

    int failedPushCount = 0;
    int succeededPushCount = 0;
    for (i = 0; i < 1100; ++i) {
        if (placeholderStackPush(&stack))
            ++succeededPushCount;
        else
            ++failedPushCount;
    }
    CHECK_THAT("Push() succeeds at least some of the time",
            succeededPushCount > 0);
    CHECK_THAT("Push() indicates an error when it runs out of space",
            failedPushCount > 0);

    int failedPopCount = 0;
    int succeededPopCount = 0;
    for (i = 0; i < 1100; ++i) {
        if (placeholderStackPop(&stack))
            ++succeededPopCount;
        else
            ++failedPopCount;
    }
    CHECK_THAT("Pop() returns success once for every successful Push()",
            succeededPopCount == succeededPushCount);
    CHECK_THAT("Pop() indicates an error if the stack is empty",
            failedPopCount > 0);
    CHECK_THAT("Pop() all elements leaves the stack empty",
            placeholderStackIsEmpty(&stack));

    SUMMARIZE();
}

PyFrameObject* newMockStackFrame(const char *filename) {
    PyFrameObject* frame = malloc(sizeof(PyFrameObject));
    PyCodeObject* code = malloc(sizeof(PyCodeObject));
    PyObject* string = PyString_FromString(filename);
    code->co_filename = string;
    frame->f_code = code;
    return frame;
}

void deleteMockStackFrame(PyFrameObject *frame) {
    Py_DECREF(frame->f_code->co_filename);
    free(frame->f_code);
    free(frame);
}

void testLogItem(void) {
    DEFINE_COUNTERS();

    const char *deployFilename = "/nail/live/versions/r201308091019-61e5d1d574-deploy-breaking-bread/templates/blank.py";
    const char *playgroundFilename = "/nail/home/spernste/pg/yelp-main/templates/blank.py";
    const char *buildbotFilename = "./templates/blank.py";
    const char *badFilename = "this does not contain any template name";
    const char *templateName = "templates/blank.py";

    const char *foundTemplateName;
    foundTemplateName = findTemplateName(deployFilename);
    CHECK_THAT("findTemplateName works on deploy directories",
            foundTemplateName != NULL && !strcmp(foundTemplateName, templateName));

    foundTemplateName = findTemplateName(playgroundFilename);
    CHECK_THAT("findTemplateName works on playground directories",
            foundTemplateName != NULL && !strcmp(foundTemplateName, templateName));

    foundTemplateName = findTemplateName(buildbotFilename);
    CHECK_THAT("findTemplateName works on buildbot directories",
            foundTemplateName != NULL && !strcmp(foundTemplateName, templateName));

    foundTemplateName = findTemplateName(badFilename);
    CHECK_THAT("findTemplateName returns null on failure",
            foundTemplateName == NULL);


#ifndef TEST_WITH_VALGRIND
    struct PlaceholderInfo placeholderInfo;
    struct LogItem logItem;

    placeholderInfo.pythonStackPointer = newMockStackFrame(deployFilename);
    placeholderInfo.placeholderID = 0x1234;
    placeholderInfo.nameSpaceIndex = 0x56;
    placeholderInfo.lookupCount = 0x78;
    placeholderInfo.flags = 0x90abcdef;

    memset(&logItem, 0, sizeof(logItem));
    logItemInit(&logItem, &placeholderInfo);
    CHECK_THAT("logItemInit hashes the template name hash correctly",
            logItem.templateNameHash == hashString(templateName));
    CHECK_THAT("logItemInit copies all other PlaceholderInfo fields",
            logItem.placeholderID == 0x1234 &&
            logItem.nameSpaceIndex == 0x56 &&
            logItem.lookupCount == 0x78 &&
            logItem.flags == 0x90abcdef);

    deleteMockStackFrame(placeholderInfo.pythonStackPointer);
    placeholderInfo.pythonStackPointer = newMockStackFrame(badFilename);

    memset(&logItem, 0, sizeof(logItem));
    logItemInit(&logItem, &placeholderInfo);
    CHECK_THAT("logItemInit hashes the full filename if findTemplateName fails",
            logItem.templateNameHash == hashString(badFilename));

    deleteMockStackFrame(placeholderInfo.pythonStackPointer);
#endif

    SUMMARIZE();
}

void testLogBuffer(void) {
    DEFINE_COUNTERS();

    struct LogBuffer buffer;
    struct LogItem item;
    int i;

    logBufferInit(&buffer);
    CHECK_THAT("LogBuffer is initialized to be empty",
            logBufferGetCount(&buffer) == 0 && buffer.insertAttempts == 0);

    logBufferInsert(&buffer, &item);
    CHECK_THAT("logBufferInsert increases the item count",
            logBufferGetCount(&buffer) == 1);
    CHECK_THAT("logBufferInsert increases insertAttempts",
            buffer.insertAttempts == 1);

    /* Reset the buffer */
    logBufferInit(&buffer);

#define TEST_LOG_BUFFER_INSERT_COUNT    50000
    /* The item count should increase on every insert for a while, and then
     * stop increasing past a certain point. */
    int sawFailedInsert = 0;
    int sawIncreaseWhenFull = 0;
    for (i = 0; i < TEST_LOG_BUFFER_INSERT_COUNT; ++i) {
        int oldCount = logBufferGetCount(&buffer);
        logBufferInsert(&buffer, &item);
        int newCount = logBufferGetCount(&buffer);

        if (newCount == oldCount) {
            sawFailedInsert = 1;
        } else {
            if (sawFailedInsert) {
                sawIncreaseWhenFull = 1;
            }
        }
    }
    CHECK_THAT("logBufferInsert stops inserting once the buffer is full",
            sawFailedInsert && !sawIncreaseWhenFull);
    CHECK_THAT("insertAttempts continues to increase after the buffer is full",
            buffer.insertAttempts == TEST_LOG_BUFFER_INSERT_COUNT);

    SUMMARIZE();
}

int countOnesInFilter(struct BloomFilter *filter) {
    int i;
    uint8_t *data = (uint8_t*)&filter->data;
    int totalCount = 0;
    for (i = 0; i < sizeof(filter->data); ++i) {
        uint8_t a = data[i];
        /* Fast popcount, for explanation see
         * https://en.wikipedia.org/wiki/Hamming_weight#Efficient_implementation
         */
        a = (a & 0x55) + ((a >> 1) & 0x55);
        a = (a & 0x33) + ((a >> 2) & 0x33);
        a = (a & 0x0f) + ((a >> 4) & 0x0f);
        totalCount += a;
    }
    return totalCount;
}

int countEqual(uint32_t* hash1, uint32_t* hash2) {
    int i;
    int numEqual = 0;
    for (i = 0; i < BLOOM_FILTER_HASHES; ++i) {
        if (hash1[i] == hash2[i])
            ++numEqual;
    }
    return numEqual;
}

void testBloomFilter(void) {
    DEFINE_COUNTERS();

    struct BloomFilter filter;
    int i;

    bloomFilterInit(&filter);
    CHECK_THAT("bloomFilterInit makes the filter empty",
            filter.itemCount == 0 && countOnesInFilter(&filter) == 0);

    struct LogItem item;
    memset(&item, 0, sizeof(item));
    item.templateNameHash = 1;
    item.placeholderID = 2;
    item.nameSpaceIndex = 3;
    item.lookupCount = 4;
    item.flags = 5;

    uint32_t oldHash[BLOOM_FILTER_HASHES];
    uint32_t newHash[BLOOM_FILTER_HASHES];

    bloomFilterHash(&item, oldHash);
    item.templateNameHash += 100;
    bloomFilterHash(&item, newHash);
    CHECK_THAT("bloomFilterHash uses item.templateNameHash",
            countEqual(oldHash, newHash) == 0);

    bloomFilterHash(&item, oldHash);
    item.placeholderID += 100;
    bloomFilterHash(&item, newHash);
    CHECK_THAT("bloomFilterHash uses item.placeholderID",
            countEqual(oldHash, newHash) == 0);

    bloomFilterHash(&item, oldHash);
    item.nameSpaceIndex += 100;
    bloomFilterHash(&item, newHash);
    CHECK_THAT("bloomFilterHash uses item.nameSpaceIndex",
            countEqual(oldHash, newHash) == 0);

    bloomFilterHash(&item, oldHash);
    item.lookupCount += 100;
    bloomFilterHash(&item, newHash);
    CHECK_THAT("bloomFilterHash uses item.lookupCount",
            countEqual(oldHash, newHash) == 0);

    bloomFilterHash(&item, oldHash);
    item.flags += 100;
    bloomFilterHash(&item, newHash);
    CHECK_THAT("bloomFilterHash uses item.flags",
            countEqual(oldHash, newHash) == 0);


    /* (1) Insert some items, and make sure that each insert sets at most
     * BLOOM_FILTER_NUM_HASHES bits. */
#define TEST_BLOOM_FILTER_NUM_ITEMS 2000
    int oldBitsSet;
    int newBitsSet;
    oldBitsSet = countOnesInFilter(&filter);
    int sawTooManyBitsChange = 0;
    int itemsInserted = 0;

    memset(&item, 0, sizeof(item));
    for (i = 0; i < TEST_BLOOM_FILTER_NUM_ITEMS; ++i) {
        ++item.templateNameHash;
        int wasPresent = bloomFilterContainsAndInsert(&filter, &item);

        if (!wasPresent) {
            ++itemsInserted;
        }

        newBitsSet = countOnesInFilter(&filter);
        if ((!wasPresent && newBitsSet - oldBitsSet > BLOOM_FILTER_HASHES) ||
                (wasPresent && newBitsSet != oldBitsSet)) {
            sawTooManyBitsChange = 1;
        }
        oldBitsSet = newBitsSet;
    }

    CHECK_THAT("inserting an element updates no more than NUM_HASHES bits",
            !sawTooManyBitsChange);
    CHECK_THAT("Bloom filter counts insertions correctly",
            itemsInserted == filter.itemCount);


    /* (2) Check that all the items we inserted are detected as present. */
    memset(&item, 0, sizeof(item));
    int foundItems = 0;
    for (i = 0; i < TEST_BLOOM_FILTER_NUM_ITEMS; ++i) {
        ++item.templateNameHash;
        if (bloomFilterContains(&filter, &item)) {
            ++foundItems;
        }
    }

    CHECK_THAT("all inserted items were found in the bloom filter",
            foundItems == TEST_BLOOM_FILTER_NUM_ITEMS);


    /* (3) Check that items we *didn't* insert are mostly not detected as
     * present. */
    int falsePositives = 0;
    for (i = 0; i < TEST_BLOOM_FILTER_NUM_ITEMS; ++i) {
        ++item.templateNameHash;
        if (bloomFilterContains(&filter, &item)) {
            ++falsePositives;
        }
    }

    CHECK_THAT("Bloom filter false positive rate is less than 0.01%",
            falsePositives <= TEST_BLOOM_FILTER_NUM_ITEMS / 10000);


    SUMMARIZE();
}

int main() {
#ifndef TEST_WITH_VALGRIND
    Py_Initialize();
#endif
    testPlaceholderStack();
    testLogItem();
    testLogBuffer();
    testBloomFilter();
#ifndef TEST_WITH_VALGRIND
    Py_Finalize();
#endif
    return 0;
}

#endif
