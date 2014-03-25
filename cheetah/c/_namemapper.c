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

#include "namemapper.h"

#ifdef __cplusplus
extern "C" {
#endif


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
static void placeholderStackInit(struct PlaceholderStack *stack) {
    stack->current = &stack->items[PLACEHOLDER_STACK_SIZE];
}

/* Add a new element to the stack by adjusting 'stack->current'.  The new
 * element is left uninitialized - the caller is expected to initialize it.
 * This function returns 1 on success and 0 on failure (if the stack is full).
 */
static int placeholderStackPush(struct PlaceholderStack *stack) {
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
static int placeholderStackPop(struct PlaceholderStack *stack) {
    if (stack->current == &stack->items[PLACEHOLDER_STACK_SIZE]) {
        /* The stack is already empty.  This probably indicates a bug. */
        return 0;
    } else {
        ++stack->current;
        return 1;
    }
}

/* Check if the stack is empty. */
static int placeholderStackIsEmpty(struct PlaceholderStack *stack) {
    return (stack->current == &stack->items[PLACEHOLDER_STACK_SIZE]);
}

/* Get a pointer to the bottommost element on the stack.  The result points to
 * a valid PlaceholderInfo only if the stack is non-empty (or equivalently,
 * only if Bottom(&stack) >= stack.current). */
static struct PlaceholderInfo* placeholderStackBottom(struct PlaceholderStack *stack) {
    return &stack->items[PLACEHOLDER_STACK_SIZE - 1];
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
static uint32_t hashString(const char* str) {
    uint32_t hash = 0;
    while (*str != '\0') {
        hash = hash * 37 + (uint8_t)(*str);
        ++str;
    }
    return hash;
}

/* Given a filename, find the template name relative to yelp-main/ or the
 * deploy directory. */
static const char* findTemplateName(const char *filename) {
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
static void logItemInit(struct LogItem *logItem, struct PlaceholderInfo *placeholderInfo) {
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
 * finished, we take the whole buffer and write it out all at once.  This means
 * we don't have the overhead of multiple write calls, and we don't need to
 * worry about interleaving lines from different processes. */

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

static void logBufferInit(struct LogBuffer *buffer) {
    buffer->nextSlot = &buffer->items[0];
    buffer->insertAttempts = 0;
}

static void logBufferInsert(struct LogBuffer *buffer, struct LogItem *item) {
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

static int logBufferGetCount(struct LogBuffer *buffer) {
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
static void bloomFilterHash(struct LogItem *item, uint32_t* hashOutput) {
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
static void bloomFilterInit(struct BloomFilter *bloomFilter) {
    /* Fill the 'data' array with all zeros. */
    memset(&bloomFilter->data, 0, sizeof(bloomFilter->data));

    bloomFilter->itemCount = 0;
}

/* The primary operation on a bloom filter: check if an item is present, and
 * optionally add it if it's not.  Having this combined operation avoids code
 * duplication between the 'contains' and 'insert' operations. */
static int bloomFilterOperate(struct BloomFilter *filter, struct LogItem* item,
        int shouldInsert) {
    int i;
    uint32_t hash[BLOOM_FILTER_HASHES];
    int wasPresent = 1;

    /* Hash the PlaceholderInfo into the 'hash' array. */
    bloomFilterHash(item, hash);

    for (i = 0; i < BLOOM_FILTER_HASHES; ++i) {
        uint32_t index = hash[i] / BLOOM_FILTER_CHUNK_BITS;
        uint32_t offset = hash[i] % BLOOM_FILTER_CHUNK_BITS;

        /* Check if the corresponding bit is set.  If not, set it (if
         * shouldInsert is true) and remember that this item was not initially
         * present in the filter. */

        /* This can't overflow the 'data' array because bloomFilterHash
         * guarantees 0 <= hash[i] < BLOOM_FILTER_SIZE and there are
         * BLOOM_FILTER_SIZE / BLOOM_FILTER_CHUNK_BITS elements in 'data'. */
        if ((filter->data[index] & (1L << offset)) == 0) {
            wasPresent = 0;
            if (shouldInsert) {
                filter->data[index] |= (1L << offset);
            } else {
                break;
            }
        }
    }

    if (!wasPresent && shouldInsert) {
        ++filter->itemCount;
    }
    return wasPresent;
}

/* Check if a LogItem is present in the bloom filter, and if not, add it.
 * Returns true if the item was present before the call, and false if it was
 * not.  Regardless, after this function returns, the item is guaranteed to be
 * present in the bloom filter. */
static int bloomFilterContainsAndInsert(struct BloomFilter *filter, struct LogItem* item) {
    return bloomFilterOperate(filter, item, 1);
}

/* Check if a LogItem is present in the bloom filter. */
static int bloomFilterContains(struct BloomFilter *filter, struct LogItem* item) {
    return bloomFilterOperate(filter, item, 0);
}



/*** High-level placeholder tracking ***/

/* The placeholder tracking system has two main components:
 *  - A stack of PlaceholderInfos for all placeholders that are currently being
 *    evaluated.
 *  - A buffer of LogItems we plan to write out.  Each LogItem added to the
 *    buffer is checked against a bloom filter to prevent logging duplicate
 *    items.
 *
 * When an instrumented request begins, both structures are cleared.  As each
 * placeholder starts evaluation, a corresponding PlaceholderInfo is pushed onto the
 * stack, and that PlaceholderInfo is updated as evaluation proceeds.  When
 * evaluation is finished, the PlaceholderInfo is popped from the stack,
 * converted to a LogItem, and added to the buffer.  At the end of the
 * instrumented request, the contents of the buffer are written out using the
 * logging function provided from the calling Python code.
 */

/* The stack of placeholders we are currently evaluating. */
static struct PlaceholderStack activePlaceholders;

/* A Bloom filter for deduplicating LogItems. */
static struct BloomFilter dedupeFilter; 

/* The buffer of LogItems we have decided to record. */
static struct LogBuffer buffer;

/* Flag to indicate whether we should do instrumentation. */
static int instrumentationEnabled = 0;


/* Function to use to perform the actual logging.  This should never be null. */
static PyObject *loggingFunc = Py_None;


/* Initialize instrumentation data structures. */
static void instrumentInit(void) {
    /* Make sure we don't segfault if instrumented functions are called before
     * instrumentStartRequest. */
    placeholderStackInit(&activePlaceholders);
    bloomFilterInit(&dedupeFilter);
    logBufferInit(&buffer);

    instrumentationEnabled = 0;
}

/* Set the callback to use for logging instrumentation data.  This should
 * probably be done before enabling instrumentation - otherwise
 * instrumentFinishRequest will raise an exception and discard the recorded
 * data. */
static void instrumentSetLoggingCallback(PyObject *logger) {
    /* Replace the old reference with the new one, updating reference counts
     * appropriately. */
    Py_DECREF(loggingFunc);
    loggingFunc = logger;
    Py_INCREF(loggingFunc);
}

/* Prototype for instrumentLogPlaceholder, since it's used in several places. */
static void instrumentLogPlaceholder(int result);

/* Constants to indicate success or failure of a placeholder evaluation, for
 * use with instrumentLogPlaceholder. */
#define EVAL_SUCCESS    1
#define EVAL_FAILURE    0

/* Indicate the start of an instrumented request.  This resets the main data
 * structures and enables instrumentation of placeholder evaluations. */
static void instrumentStartRequest(void) {
    placeholderStackInit(&activePlaceholders);
    bloomFilterInit(&dedupeFilter);
    logBufferInit(&buffer);

    instrumentationEnabled = 1;
}

/* Indicate the end of an instrumented request.  This disables instrumentation
 * of placeholder evaluations and logs all the data collected during the
 * request. */
static int instrumentFinishRequest(void) {
    if (!instrumentationEnabled) {
        return 1;
    }

    /* Anything left on the stack as of the end of the request is assumed to
     * have failed during evaluation. */
    while (!placeholderStackIsEmpty(&activePlaceholders)) {
        instrumentLogPlaceholder(EVAL_FAILURE);
    }

    instrumentationEnabled = 0;

    /* If there is nothing recorded, don't bother logging anything. */
    if (buffer.insertAttempts == 0) {
        return 1;
    }

    /* Actually write out the contents of the LogBuffer. */
    PyObject *result = PyObject_CallFunction(loggingFunc, "s#",
            (const char*)&buffer.items, logBufferGetCount(&buffer) * sizeof(struct LogItem));
    return (result != NULL);
}


/* It turns out dealing with exceptions is rather complicated.  Here are some
 * interesting examples:
 *
 *      #def f
 *          #try
 *              $x[0].y     ## throws an exception from the __getitem__ call
 *          #except
 *              ## pass
 *          #end try
 *      #end def
 *
 *      $z[f()].w
 *
 * Here we have the following events (with parentheses indicating events that
 * we can't observe directly):
 *  - Evaluate "$z" for "$z[...].w"
 *  - (Call f() without using the namemapper)
 *  - Evaluate "$x" for "$x[0].y"
 *  - (An exception is thrown, then caught.  f returns.)
 *  - Evaluate ".w" for "$z[...].w"
 *  - Finish evaluation for "$z[...].w"
 * We are actually done evaluating "$x[0].y", but we did not see any event to
 * indicate that.  We have to figure it out by looking at the stack during the
 * next observable event (the evaluation of ".w").  We handle this in
 * instrumentCurrentPlaceholderMatches: if the top placeholder of the stack
 * does not match at first, we check for exceptions, clean up the stack, and
 * examine the top placeholder again.  (We "clean up the stack" by logging an
 * evaluation failure for any PlaceholderInfo whose pythonStackPointer points
 * to a Python stack frame that is no longer part of the current Python stack.)
 *
 *
 *      #def f
 *          #try
 *              $x[0].y     ## throws an exception from the __getitem__ call
 *          #except
 *              ## pass
 *          #end try
 *      #end def
 *
 *      $f()
 *      $z
 *
 * In this example, we have the following events:
 *  - Evaluate "$f" completely.  (Call f().)
 *  - Evaluate "$x" for "$x[0].y"
 *  - (An exception is thrown, then caught.  f returns.)
 *  - Evaluate "$z" completely
 * There is no call to CurrentPlaceholderMatches because "$z" just pushes a new
 * PlaceholderInfo instead of modifying an existing one.  To detect cases like
 * this, we check in StartPlaceholder if the pythonStackPointer for the
 * PlaceholderInfo on top of the stack is part of the current Python stack.  If
 * it is not, then that Python stack frame has returned, and any placeholder in
 * that stack frame has died with an evaluation error.  (We use the normal
 * stack cleanup to handle this.)
 *
 *
 *      #try
 *          $x[0].y     ## throws an exception from the __getitem__ call
 *      #except
 *          ## pass
 *      #end try
 *      $z
 *
 * This is similar to the previous example, but slightly more complicated.  We
 * have the following events:
 *  - Evaluate "$x" for "$x[0].y"
 *  - (An exception is thrown, then caught.)
 *  - Evaluate "$z" completely
 * Now there is no call to CurrentPlaceholderMatches, and the check in
 * StartPlaceholder will find that the pythonStackPointer of the topmost item
 * ("$x[0].y") is still live (since "$x[0].y" and "$z" are in the same
 * function).  In fact, we have no effective method of distinguishing this case
 * from "$x[$z].y", which triggers the events 'evaluate "$x"', 'evaluate "$z"',
 * and 'evaluate ".y"'.
 *
 * We handle this by leaving the failed "$x[0].y" on the stack for now.  Once
 * the function containing "$x[0].y" and "$z" returns, the same checks that
 * handle the previous two cases will notice that "$x[0].y" has failed and will
 * clean up its entry in the stack.  The only potential issue to worry about
 * is that the entire template rendering process might end after "$z" without
 * evaluating any more placeholders.  We handle this by logging everything left
 * on the stack at the time of FinishRequest() as having failed during
 * evaluation.
 *
 *
 * So our exception handling strategy has three parts:
 *  - During StartPlaceholder, if the top of the stack has a pythonStackFrame
 *    that points to a frame that has returned (is not live), run stack
 *    cleanup.  (Stack cleanup finds any items on the activePlaceholders stack
 *    whose pythonStackPointers point to Python stack frames that have
 *    returned, and logs each one as a failed evaluation.)
 *  - In CurrentPlaceholderMatches, if the top of the stack does not match the
 *    provided information, run stack cleanup (and check again).
 *  - In FinishRequest, assume all remaining PlaceholderInfos on the stack have
 *    failed evaluation, and log them all accordingly.
 */

/* Check if a Python stack frame is live.  Returns 1 if it is still live (part
 * of the Python callstack whose top is 'currentFrame'), and 0 if it is not
 * (due to returning or raising an exception).  This is optimized with the
 * expectation that most calls will return 'true'. */
static int isStackFrameLive(PyFrameObject *targetFrame, PyFrameObject *currentFrame) {
    while (currentFrame != targetFrame && currentFrame != NULL) {
        currentFrame = currentFrame->f_back;
    }

    return (currentFrame == targetFrame);
}

/* Search a stack of PlaceholderInfos for the last one whose pythonStackPointer
 * points to a non-live Python frame. */
static struct PlaceholderInfo* findLastDead(PyFrameObject *frame,
        struct PlaceholderInfo *placeholderBegin, struct PlaceholderInfo *placeholderEnd) {
    struct PlaceholderInfo* lastDead;

    /* Recursively descend the Python callstack until we run out of callstack
     * or we find placeholderEnd->pythonStackPointer. */

    /* If we ran out of Python stack, we're done.  For the way back up, start
     * by assuming every PlaceholderInfo in the list has a dead stack frame. */
    if (frame == NULL)
        return placeholderEnd;

    /* If 'frame' is the stack frame for placeholderEnd, then we can stop
     * walking the Python stack early. */
    if (placeholderEnd >= placeholderBegin && frame == placeholderEnd->pythonStackPointer) {
        lastDead = placeholderEnd - 1;
    } else {
        /* Continue descending the Python callstack. */
        lastDead = findLastDead(frame->f_back, placeholderBegin, placeholderEnd);
    }

    /* As we head back up the callstack, move 'lastDead' backward (to higher
     * PlaceholderStack items) as long as its pythonStackPointer points to a
     * live frame. */

    /* If the current 'frame' is the stack frame for 'lastDead', then
     * 'lastDead' actually points to a PlaceholderInfo with a live stack frame.
     * Adjust 'lastDead' until that's no longer the case.  (This is a loop
     * because there may be multiple placeholders with the same frame.) */
    while (lastDead >= placeholderBegin && frame == lastDead->pythonStackPointer)
        --lastDead;

    return lastDead;
}

/* Remove all PlaceholderInfos with non-live Python stack frames from the top
 * of the activePlaceholders stack.  We log all such placeholders as
 * EVAL_FAILURE, since we know control can never reach a corresponding FLUSH
 * call. */
static void cleanupStack(void) {
    if (placeholderStackIsEmpty(&activePlaceholders))
        return;

    struct PlaceholderInfo *lastDead = findLastDead(PyEval_GetFrame(),
            activePlaceholders.current, placeholderStackBottom(&activePlaceholders));

    while (activePlaceholders.current <= lastDead) {
        instrumentLogPlaceholder(EVAL_FAILURE);
    }
}


/* Indicate the start of evaluation for the placeholder with the given ID. */
static void instrumentStartPlaceholder(int placeholderID) {
    if (!instrumentationEnabled)
        return;

    if (!placeholderStackIsEmpty(&activePlaceholders) &&
            !isStackFrameLive(activePlaceholders.current->pythonStackPointer, PyEval_GetFrame())) {
        cleanupStack();
    }

    /* Add a new PlaceholderInfo to the stack, or do nothing if the stack is
     * full. */
    if (placeholderStackPush(&activePlaceholders)) {
        activePlaceholders.current->pythonStackPointer = PyEval_GetFrame();
        /* Make sure the Python stack frame doesn't get deallocated, which also
         * ensure its address does not get reused.  The corresponding DECREF is
         * in instrumentLogPlaceholder, which also contains the
         * placeholderStackPop corresponding to our placeholderStackPush. */
        Py_INCREF(activePlaceholders.current->pythonStackPointer);

        activePlaceholders.current->placeholderID = placeholderID;

        /* The namespace index will be set to a more appropriate value once we
         * finish the first lookup step.  If the first lookup step fails, we
         * don't need to do anything but leave the index as NS_NOT_FOUND. */
        activePlaceholders.current->nameSpaceIndex = NS_NOT_FOUND;

        activePlaceholders.current->lookupCount = 0;
        activePlaceholders.current->flags = 0;
    }
}

/* Check if the current placeholder (the top of the stack) matches the provided
 * placeholderID and the current Python stack frame.  If this function returns
 * true, then it is guaranteed that activePlaceholders.current contains data on
 * the placeholder with the provided ID being evaluated in the current Python
 * stack frame. */
static int instrumentCurrentPlaceholderMatches(uint16_t placeholderID) {
    /* Make the check, and if there is a mismatch, run stack cleanup and check
     * again. */
    int result = 0;
    if (instrumentationEnabled && !placeholderStackIsEmpty(&activePlaceholders)) {
        result = activePlaceholders.current->pythonStackPointer == PyEval_GetFrame() &&
                activePlaceholders.current->placeholderID == placeholderID;

        if (!result) {
            cleanupStack();
            result = instrumentationEnabled &&
                    !placeholderStackIsEmpty(&activePlaceholders) &&
                    activePlaceholders.current->pythonStackPointer == PyEval_GetFrame() &&
                    activePlaceholders.current->placeholderID == placeholderID;
        }
    }
    return result;
}

/* Record the flags for a lookup step of the current placeholder.  If the
 * provided placeholder ID doesn't match the placeholder on top of the stack,
 * this function does nothing. */
static void instrumentRecordLookup(uint16_t placeholderID, int flags) {
    if (!instrumentCurrentPlaceholderMatches(placeholderID))
        return;

    int index = activePlaceholders.current->lookupCount;
    ++activePlaceholders.current->lookupCount;
    if (index >= 16)
        /* We don't need an explicit warning for this case.  The code that
         * processes the log can detect this has happened by looking for lines
         * which report lookupCount >= 16. */
        return;

    activePlaceholders.current->flags |= (flags & 3) << (index * 2);
}

/* Record the namespace index for the first lookup step of the current
 * placeholder.  If the provided placeholder ID doesn't match the current
 * placeholder on stack, this function does nothing. */
static void instrumentRecordNameSpaceIndex(uint16_t placeholderID, int nameSpaceIndex) {
    if (!instrumentCurrentPlaceholderMatches(placeholderID))
        return;

    activePlaceholders.current->nameSpaceIndex = nameSpaceIndex;
}

/* Pop the topmost PlaceholderInfo from the activePlaceholders stack, and log a
 * corresponding LogItem to the buffer.  'result' should be EVAL_SUCCESS or
 * EVAL_FAILURE, to indicate whether the placeholder evaluation succeeded or
 * failed with an exception. */
static void instrumentLogPlaceholder(int result) {
    if (result != EVAL_SUCCESS) {
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

    Py_DECREF(activePlaceholders.current->pythonStackPointer);
    placeholderStackPop(&activePlaceholders);
}

/* Indicate the successful completion of evaluation of the placeholder with the
 * given ID.  The placeholder will be logged as EVAL_SUCCESS and popped from
 * the activePlaceholders stack. */
static void instrumentFinishPlaceholder(int placeholderID) {
    if (!instrumentCurrentPlaceholderMatches(placeholderID))
        return;

    instrumentLogPlaceholder(EVAL_SUCCESS);
}

/* Indicate that evaluation of the placeholder has aborted due to some kind of
 * error.  This will log the aborted placeholder and all others from the same
 * stack frame as EVAL_FAILURE. */
static void instrumentAbortPlaceholder(int placeholderID) {
    if (!instrumentCurrentPlaceholderMatches(placeholderID))
        return;

    /* We make one optimization on top of the basic exception handling
     * mechanism.  In some cases we are informed that a placeholder evaluation
     * has died with an exception.  In those cases, we clean up that
     * placeholder, and we also clean up all placeholders with the same
     * pythonStackPointer at the top of the placeholder stack.  This lets us
     * sometimes avoid an entire stack cleanup, which can be rather expensive.
     *
     * There are only two ways we can have multiple placeholder stack entries
     * with the same pythonStackPointer:
     *  1) We are evaluating a nested placeholder, such as the "$y" in
     *     "$x[$y].z".  The optimization is correct here because an exception
     *     while evalutating the inner placeholder will also abort evaluation
     *     of the outer placeholder.
     *  2) There was an exception during a previous placeholder evaluation in
     *     the same function, which was caught.  (Example #3 from the main
     *     exception handling comment.)  In this case, the additional
     *     PlaceholderInfos will be cleaned up at some point in the future, so
     *     it's fine for this optimization to clean them up a bit early
     *     instead.
     */

    PyFrameObject *targetFrame = activePlaceholders.current->pythonStackPointer;
    while (!placeholderStackIsEmpty(&activePlaceholders) &&
            activePlaceholders.current->pythonStackPointer == targetFrame) {
        instrumentLogPlaceholder(EVAL_FAILURE);
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

static PyObject *PyNamemapper_valueForName(PyObject *obj, char *nameChunks[], int numChunks, int placeholderID, int executeCallables, int useDottedNotation)
{
    int i;
    char *currentKey;
    int currentFlags;
    PyObject *currentVal = NULL;
    PyObject *nextVal = NULL;

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

        if (useDottedNotation && PyMapping_Check(currentVal) && PyMapping_HasKeyString(currentVal, currentKey)) {
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
            currentFlags |= DID_AUTOCALL;
            if (!(currentVal = PyObject_CallObject(nextVal, NULL))) {
                Py_DECREF(nextVal);
                return NULL;
            }
            Py_DECREF(nextVal);
        } else {
            currentVal = nextVal;
        }

        instrumentRecordLookup(placeholderID, currentFlags);
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
    int useDottedNotation = 1;
    int placeholderID = -1;

    char *nameCopy = NULL;
    char *tmpPntr1 = NULL;
    char *tmpPntr2 = NULL;
    char *nameChunks[MAXCHUNKS];
    int numChunks;

    PyObject *theValue;

    static char *kwlist[] = {"obj", "name", "executeCallables", "useDottedNotation", "placeholderID", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Os|iii", kwlist,  &obj, &name, &executeCallables, &useDottedNotation, &placeholderID)) {
        return NULL;
    }

    createNameCopyAndChunks();  

    theValue = PyNamemapper_valueForName(obj, nameChunks, numChunks, placeholderID, executeCallables, useDottedNotation);
    free(nameCopy);
    if (wrapInternalNotFoundException(name, obj)) {
        theValue = NULL;
    }

    if (theValue == NULL) {
        instrumentAbortPlaceholder(placeholderID);
    }

    return theValue;
}

static PyObject *namemapper_valueFromSearchList(PYARGS)
{
    PyObject *searchList;
    char *name;
    int executeCallables = 0;
    int useDottedNotation = 1;
    int placeholderID = -1;

    char *nameCopy = NULL;
    char *tmpPntr1 = NULL;
    char *tmpPntr2 = NULL;
    char *nameChunks[MAXCHUNKS];
    int numChunks;
    int searchListIndex;

    PyObject *nameSpace = NULL;
    PyObject *theValue = NULL;
    PyObject *theValue_tmp = NULL;
    PyObject *iterator = NULL;

    static char *kwlist[] = {"searchList", "name", "executeCallables", "useDottedNotation", "placeholderID", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Os|iii", kwlist, &searchList, &name, &executeCallables, &useDottedNotation, &placeholderID)) {
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
        instrumentAbortPlaceholder(placeholderID);
    }

    return theValue;
}

static PyObject *namemapper_valueFromFrameOrSearchList(PyObject *self, PyObject *args, PyObject *keywds)
{
    /* python function args */
    char *name;
    int executeCallables = 0;
    int useDottedNotation = 1;
    int placeholderID = -1;
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
    PyObject *theValue_tmp = NULL;
    PyObject *excString = NULL;
    PyObject *iterator = NULL;

    static char *kwlist[] = {"searchList", "name",  "executeCallables", "useDottedNotation", "placeholderID", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, keywds, "Os|iii", kwlist,  &searchList, &name, 
                    &executeCallables, &useDottedNotation, &placeholderID)) {
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
        instrumentAbortPlaceholder(placeholderID);
    }

    return theValue;
}

static PyObject *namemapper_valueFromFrame(PyObject *self, PyObject *args, PyObject *keywds)
{
    /* python function args */
    char *name;
    int executeCallables = 0;
    int useDottedNotation = 1;
    int placeholderID = -1;

    /* locals */
    char *tmpPntr1 = NULL;
    char *tmpPntr2 = NULL;

    char *nameCopy = NULL;
    char *nameChunks[MAXCHUNKS];
    int numChunks;

    PyObject *nameSpace = NULL;
    PyObject *theValue = NULL;
    PyObject *theValue_tmp = NULL;
    PyObject *excString = NULL;

    static char *kwlist[] = {"name", "executeCallables", "useDottedNotation", "placeholderID", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, keywds, "s|iii", kwlist, &name, &executeCallables, &useDottedNotation, &placeholderID)) {
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
        instrumentAbortPlaceholder(placeholderID);
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

    instrumentFinishPlaceholder(placeholderID);

    /* Python doesn't automatically increment the reference count of the
     * function's return value, so we have to do it manually. */
    Py_XINCREF(obj);
    return obj;
}

static PyObject *namemapper_setLoggingCallback(PyObject *self, PyObject *args, PyObject *keywds)
{
    /* python function args */
    PyObject* callback;

    static char *kwlist[] = {"callback", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, keywds, "O", kwlist, &callback)) {
        return NULL;
    }

    instrumentSetLoggingCallback(callback);

    return Py_None;
}

static PyObject *namemapper_startLogging(PyObject *self, PyObject *args, PyObject *keywds)
{
    instrumentStartRequest();
    return Py_None;
}

static PyObject *namemapper_finishLogging(PyObject *self, PyObject *args, PyObject *keywds)
{
    if (instrumentFinishRequest())
        return Py_None;
    else
        return NULL;
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
  {"setLoggingCallback", (PyCFunction)namemapper_setLoggingCallback, METH_VARARGS|METH_KEYWORDS},
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

    instrumentInit();
    /* Suppress a warning about bloomFilterContains being unused.  (It's used
     * only in the test code.) */
    (void)bloomFilterContains;

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

/* These are tests for the internal (static) functions, which would be
 * difficult to test otherwise.  There are additional tests in
 * cheetah/Tests/TestInstrumentation.py, which check for correct behavior
 * during actual template rendering. */

/* To run the tests:
 *      gcc -DBUILD_TESTS -O2 -I/usr/include/python2.6 -lpython2.6 _namemapper.c
 *      ./a.out
 * The tests have passed if you see "0 / ## assertions failed" for each
 * section, and the test program exits successfully (without segfault or other
 * errors).
 *
 * Some tests just check that certain patterns of calls don't cause overflows
 * of various data structures.  (These are the ones that look like
 * 'TEST_ASSERT("doing xyz doesn't crash", 1)'.)  These tests will likely fail
 * by causing a segfault.  If you want to be extra sure, you can run the test
 * program under valgrind (with the Python-provided suppression file from
 * http://svn.python.org/projects/python/trunk/Misc/valgrind-python.supp) and
 * make sure there are no reported errors (aside from the ones from
 * PyObject_Free and PyObject_Realloc, which seem to slip past the suppression
 * rules for some reason).  */

#ifdef BUILD_TESTS

#define DEFINE_COUNTERS() \
    int asserts_passed = 0, asserts_total = 0

#define TEST_ASSERT(what, cond) \
    do {\
        printf("%-70s   ", what);\
        fflush(stdout);\
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

static void testPlaceholderStack(void) {
    DEFINE_COUNTERS();
    struct PlaceholderStack stack;
    int i;

    placeholderStackInit(&stack);

    TEST_ASSERT("the stack starts empty",
            placeholderStackIsEmpty(&stack));

    struct PlaceholderInfo *current1 = stack.current;
    placeholderStackPush(&stack);
    struct PlaceholderInfo *current2 = stack.current;
    TEST_ASSERT("Push() changes the value of 'current'",
            current1 != current2);

    TEST_ASSERT("Push() makes the stack nonempty",
            !placeholderStackIsEmpty(&stack));

    placeholderStackPop(&stack);
    struct PlaceholderInfo *current3 = stack.current;
    TEST_ASSERT("Pop() after Push() restores the previous value to 'current'",
            current1 == current3);

    int failedPushCount = 0;
    int succeededPushCount = 0;
    for (i = 0; i < 1100; ++i) {
        if (placeholderStackPush(&stack))
            ++succeededPushCount;
        else
            ++failedPushCount;
    }
    TEST_ASSERT("Push() succeeds at least some of the time",
            succeededPushCount > 0);
    TEST_ASSERT("Push() indicates an error when it runs out of space",
            failedPushCount > 0);

    int failedPopCount = 0;
    int succeededPopCount = 0;
    for (i = 0; i < 1100; ++i) {
        if (placeholderStackPop(&stack))
            ++succeededPopCount;
        else
            ++failedPopCount;
    }
    TEST_ASSERT("Pop() returns success once for every successful Push()",
            succeededPopCount == succeededPushCount);
    TEST_ASSERT("Pop() indicates an error if the stack is empty",
            failedPopCount > 0);
    TEST_ASSERT("Pop() all elements leaves the stack empty",
            placeholderStackIsEmpty(&stack));

    SUMMARIZE();
}

static PyFrameObject* newMockStackFrame(const char *filename) {
    PyFrameObject* frame = malloc(sizeof(PyFrameObject));
    PyCodeObject* code = malloc(sizeof(PyCodeObject));
    PyObject* string = PyString_FromString(filename);
    code->co_filename = string;
    frame->f_code = code;
    return frame;
}

static void deleteMockStackFrame(PyFrameObject *frame) {
    Py_DECREF(frame->f_code->co_filename);
    free(frame->f_code);
    free(frame);
}

static void testLogItem(void) {
    DEFINE_COUNTERS();

    const char *deployFilename = "/nail/live/versions/r201308091019-61e5d1d574-deploy-breaking-bread/templates/blank.py";
    const char *playgroundFilename = "/nail/home/spernste/pg/yelp-main/templates/blank.py";
    const char *buildbotFilename = "./templates/blank.py";
    const char *badFilename = "this does not contain any template name";
    const char *templateName = "templates/blank.py";

    const char *foundTemplateName;
    foundTemplateName = findTemplateName(deployFilename);
    TEST_ASSERT("findTemplateName works on deploy directories",
            foundTemplateName != NULL && !strcmp(foundTemplateName, templateName));

    foundTemplateName = findTemplateName(playgroundFilename);
    TEST_ASSERT("findTemplateName works on playground directories",
            foundTemplateName != NULL && !strcmp(foundTemplateName, templateName));

    foundTemplateName = findTemplateName(buildbotFilename);
    TEST_ASSERT("findTemplateName works on buildbot directories",
            foundTemplateName != NULL && !strcmp(foundTemplateName, templateName));

    foundTemplateName = findTemplateName(badFilename);
    TEST_ASSERT("findTemplateName returns null on failure",
            foundTemplateName == NULL);


    struct PlaceholderInfo placeholderInfo;
    struct LogItem logItem;

    placeholderInfo.pythonStackPointer = newMockStackFrame(deployFilename);
    placeholderInfo.placeholderID = 0x1234;
    placeholderInfo.nameSpaceIndex = 0x56;
    placeholderInfo.lookupCount = 0x78;
    placeholderInfo.flags = 0x90abcdef;

    memset(&logItem, 0, sizeof(logItem));
    logItemInit(&logItem, &placeholderInfo);
    TEST_ASSERT("logItemInit hashes the template name hash correctly",
            logItem.templateNameHash == hashString(templateName));
    TEST_ASSERT("logItemInit copies all other PlaceholderInfo fields",
            logItem.placeholderID == 0x1234 &&
            logItem.nameSpaceIndex == 0x56 &&
            logItem.lookupCount == 0x78 &&
            logItem.flags == 0x90abcdef);

    deleteMockStackFrame(placeholderInfo.pythonStackPointer);
    placeholderInfo.pythonStackPointer = newMockStackFrame(badFilename);

    memset(&logItem, 0, sizeof(logItem));
    logItemInit(&logItem, &placeholderInfo);
    TEST_ASSERT("logItemInit hashes the full filename if findTemplateName fails",
            logItem.templateNameHash == hashString(badFilename));

    deleteMockStackFrame(placeholderInfo.pythonStackPointer);

    SUMMARIZE();
}

static void testLogBuffer(void) {
    DEFINE_COUNTERS();

    struct LogBuffer buffer;
    struct LogItem item;
    int i;

    logBufferInit(&buffer);
    TEST_ASSERT("LogBuffer is initialized to be empty",
            logBufferGetCount(&buffer) == 0 && buffer.insertAttempts == 0);

    logBufferInsert(&buffer, &item);
    TEST_ASSERT("logBufferInsert increases the item count",
            logBufferGetCount(&buffer) == 1);
    TEST_ASSERT("logBufferInsert increases insertAttempts",
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
    TEST_ASSERT("logBufferInsert stops inserting once the buffer is full",
            sawFailedInsert && !sawIncreaseWhenFull);
    TEST_ASSERT("insertAttempts continues to increase after the buffer is full",
            buffer.insertAttempts == TEST_LOG_BUFFER_INSERT_COUNT);

    SUMMARIZE();
}

static int countOnesInFilter(struct BloomFilter *filter) {
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

static int countEqual(uint32_t* hash1, uint32_t* hash2) {
    int i;
    int numEqual = 0;
    for (i = 0; i < BLOOM_FILTER_HASHES; ++i) {
        if (hash1[i] == hash2[i])
            ++numEqual;
    }
    return numEqual;
}

static void testBloomFilter(void) {
    DEFINE_COUNTERS();

    struct BloomFilter filter;
    int i;

    bloomFilterInit(&filter);
    TEST_ASSERT("bloomFilterInit makes the filter empty",
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
    TEST_ASSERT("bloomFilterHash uses item.templateNameHash",
            countEqual(oldHash, newHash) == 0);

    bloomFilterHash(&item, oldHash);
    item.placeholderID += 100;
    bloomFilterHash(&item, newHash);
    TEST_ASSERT("bloomFilterHash uses item.placeholderID",
            countEqual(oldHash, newHash) == 0);

    bloomFilterHash(&item, oldHash);
    item.nameSpaceIndex += 100;
    bloomFilterHash(&item, newHash);
    TEST_ASSERT("bloomFilterHash uses item.nameSpaceIndex",
            countEqual(oldHash, newHash) == 0);

    bloomFilterHash(&item, oldHash);
    item.lookupCount += 100;
    bloomFilterHash(&item, newHash);
    TEST_ASSERT("bloomFilterHash uses item.lookupCount",
            countEqual(oldHash, newHash) == 0);

    bloomFilterHash(&item, oldHash);
    item.flags += 100;
    bloomFilterHash(&item, newHash);
    TEST_ASSERT("bloomFilterHash uses item.flags",
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

    TEST_ASSERT("inserting an element updates no more than NUM_HASHES bits",
            !sawTooManyBitsChange);
    TEST_ASSERT("Bloom filter counts insertions correctly",
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

    TEST_ASSERT("all inserted items were found in the bloom filter",
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

    TEST_ASSERT("Bloom filter false positive rate is less than 0.01%",
            falsePositives <= TEST_BLOOM_FILTER_NUM_ITEMS / 10000);


    SUMMARIZE();
}


static int mockLogLineLength = 0;
static uint32_t mockLogLineHash = 0;

static PyObject *mockLog(PyObject *self, PyObject *args) {
    PyObject *line;

    if (!PyArg_ParseTuple(args, "O", &line)) {
        return NULL;
    }

    mockLogLineLength = PyObject_Length(line);
    mockLogLineHash = PyObject_Hash(line);

    return Py_None;
}

static struct PyMethodDef mockLogMethodDef = {
    "mockLog", (PyCFunction)mockLog, METH_VARARGS
};

static void testInstrumentation(void) {
    DEFINE_COUNTERS();
    int i;
    int result;

    instrumentInit();
    if (PyErr_Occurred()) {
        PyErr_PrintEx(0);
        printf("Error occurred during instrumentInit\n");
        return;
    }

    /* Run a fake placeholder evaluation before instrumentStartRequest and make
     * sure it doesn't crash.  (This should do nothing at all.) */
    instrumentStartPlaceholder(42);
    instrumentCurrentPlaceholderMatches(42);
    instrumentRecordNameSpaceIndex(42, 3);
    instrumentRecordLookup(42, DID_AUTOCALL);
    instrumentFinishPlaceholder(42);
    TEST_ASSERT("placeholder evaluation before first StartRequest didn't crash",
            !PyErr_Occurred());

    result = instrumentFinishRequest();
    TEST_ASSERT("FinishRequest before first StartRequest didn't crash",
            result && !PyErr_Occurred());


    /* Run a full request with no logging callback.  This should set a Python
     * exception in FinishRequest, but it should not segfault. */
    instrumentStartRequest();
    instrumentStartPlaceholder(42);
    instrumentRecordNameSpaceIndex(42, 3);
    instrumentRecordLookup(42, DID_AUTOCALL);
    instrumentFinishPlaceholder(42);
    TEST_ASSERT("full request with no logging callback didn't crash",
            !PyErr_Occurred());
    result = instrumentFinishRequest();
    TEST_ASSERT("FinishRequest with no logging callback raises exception",
            !result && PyErr_Occurred());
    PyErr_Clear();


    /* Set the Python logging callback. */
    PyObject *mockLogObject = PyCFunction_New(&mockLogMethodDef, NULL);
    instrumentSetLoggingCallback(mockLogObject);


    /* Test instrumentCurrentPlaceholderMatches */
    instrumentStartRequest();

    instrumentStartPlaceholder(42);
    TEST_ASSERT("CurrentPlaceholderMatches same ID immediately after Start",
            instrumentCurrentPlaceholderMatches(42));

    instrumentStartPlaceholder(99);
    TEST_ASSERT("only new ID matches after starting nested evaluation",
            instrumentCurrentPlaceholderMatches(99) &&
            !instrumentCurrentPlaceholderMatches(42));

    instrumentFinishPlaceholder(42);
    TEST_ASSERT("FinishPlaceholder with wrong ID is ignored",
            instrumentCurrentPlaceholderMatches(99) &&
            !instrumentCurrentPlaceholderMatches(42));

    instrumentFinishPlaceholder(99);
    TEST_ASSERT("only old ID matches after finishing nested evaluation",
            instrumentCurrentPlaceholderMatches(42) &&
            !instrumentCurrentPlaceholderMatches(99));

    instrumentFinishPlaceholder(42);
    TEST_ASSERT("no IDs match after finishing outer evaluations",
            !instrumentCurrentPlaceholderMatches(42) &&
            !instrumentCurrentPlaceholderMatches(99));

    instrumentFinishRequest();


    /* Start a request, evaluate a placeholder, and log the request. */
    instrumentStartRequest();

    instrumentStartPlaceholder(42);
    instrumentRecordNameSpaceIndex(42, 3);
    instrumentRecordLookup(42, DID_AUTOCALL);
    instrumentFinishPlaceholder(42);

    mockLogLineLength = -1;
    instrumentFinishRequest();
    int simpleLineLength = mockLogLineLength;
    uint32_t simpleLineHash = mockLogLineHash;
    TEST_ASSERT("simple placeholder evaluation was logged",
            simpleLineLength > 0);


    /* Same as before, but add a bunch of calls for non-matching placeholders
     * and make sure they're ignored. */
    instrumentStartRequest();

    instrumentStartPlaceholder(42);
    instrumentRecordNameSpaceIndex(42, 3);
    instrumentRecordNameSpaceIndex(99, 7);
    instrumentRecordLookup(42, DID_AUTOCALL);
    instrumentRecordLookup(99, DID_AUTOKEY);
    instrumentFinishPlaceholder(42);

    mockLogLineLength = -1;
    instrumentFinishRequest();
    uint32_t nonMatchingLineHash = mockLogLineHash;
    TEST_ASSERT("instrumentation data for non-matching placeholders is ignored",
            nonMatchingLineHash == simpleLineHash);


    /* Start a request then end it without evaluating any placeholders.  Should
     * log nothing at all. */
    instrumentStartRequest();

    mockLogLineLength = -1;
    instrumentFinishRequest();
    TEST_ASSERT("request with no placeholders logs nothing",
            mockLogLineLength == -1);


    /* Start a request, evaluate the same placeholder several times, and log
     * the request.  Should produce identical results to the simple case. */
    instrumentStartRequest();

    for (i = 0; i < 5; ++i) {
        instrumentStartPlaceholder(42);
        instrumentRecordNameSpaceIndex(42, 3);
        instrumentRecordLookup(42, DID_AUTOCALL);
        instrumentFinishPlaceholder(42);
    }

    mockLogLineLength = -1;
    instrumentFinishRequest();
    uint32_t duplicateLineHash = mockLogLineHash;
    TEST_ASSERT("duplicate log entries are discarded",
            duplicateLineHash == simpleLineHash);


    /* Run a request that overflows the placeholder stack. */
    instrumentStartRequest();

    for (i = 0; i < 1000; ++i) {
        instrumentStartPlaceholder(i);
        instrumentRecordNameSpaceIndex(i, 3);
        instrumentRecordLookup(i, DID_AUTOCALL);
    }
    for (i = 999; i >= 0; --i) {
        instrumentFinishPlaceholder(i);
    }

    instrumentFinishRequest();
    TEST_ASSERT("placeholder stack overflow doesn't cause a crash",
            1);


    /* Run a request that overflows the log buffer. */
    instrumentStartRequest();

    for (i = 0; i < 100000; ++i) {
        instrumentStartPlaceholder(i);
        instrumentRecordNameSpaceIndex(i, 3);
        instrumentRecordLookup(i, DID_AUTOCALL);
        instrumentFinishPlaceholder(i);
    }

    instrumentFinishRequest();
    TEST_ASSERT("log buffer overflow doesn't cause a crash",
            1);


    SUMMARIZE();
}

/* This horrible mess is necessary to run testInstrumentation with an active
 * stack frame in the Python interpreter. */

/* Wrapper around testInstrumentation that can be called from Python. */
static PyObject *pythonTestInstrumentation(PyObject *self, PyObject *args) {
    testInstrumentation();
    return Py_None;
}

static struct PyMethodDef pythonTestInstrumentationMethodDef = {
    "pythonTestInstrumentation", (PyCFunction)pythonTestInstrumentation, METH_VARARGS
};

static void runTestInstrumentation(void) {
    PyObject* testInstrumentationObject = PyCFunction_New(&pythonTestInstrumentationMethodDef, NULL);
    PyObject* locals = Py_BuildValue("{s:O}", "run", testInstrumentationObject);
    PyObject* globals = Py_BuildValue("{s:O}", "__builtins__", PyImport_ImportModule("__builtin__"));

    PyRun_String("run()", Py_file_input, globals, locals);
}

int main(void) {
    Py_Initialize();
    testPlaceholderStack();
    testLogItem();
    testLogBuffer();
    testBloomFilter();
    runTestInstrumentation();
    return 0;
}

#endif
