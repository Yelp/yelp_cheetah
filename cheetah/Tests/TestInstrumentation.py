#!/usr/bin/python

# We have to mock out clog.log_line before the _namemapper module is imported,
# because _namemapper saves a reference to it internally.
import mock
import clog

log_line_mock = mock.Mock()
clog.log_line = log_line_mock

import base64
from collections import namedtuple
import struct
import testify as T
import zlib

from Cheetah.Template import Template
import Cheetah._namemapper

LogItem = namedtuple('LogItem',
        ['fileNameHash', 'placeholderID', 'nameSpaceIndex', 'lookupCount', 'flags'])

LOG_ITEM_STRUCT_SPEC = '<IhbBI'

DID_AUTOKEY = 1
DID_AUTOCALL = 2

LOOKUP_FAILED = 0x80

def parse_log_line(line):
    deploy_sha, item_count, blob_b64 = line.split()
    blob_gz = base64.b64decode(blob_b64)
    blob = zlib.decompress(blob_gz)

    result = []
    for offset in xrange(0, len(blob), struct.calcsize(LOG_ITEM_STRUCT_SPEC)):
        item_tuple = struct.unpack_from(LOG_ITEM_STRUCT_SPEC, blob, offset)
        result.append(LogItem(*item_tuple))
    return result

class TestObject(object):
    def __init__(self, dct):
        self._dct = dct

    def __getattr__(self, key):
        return self._dct[key]

def get_log_items_for_template(source):
    log_line_mock.reset_mock()

    Cheetah._namemapper.startLogging()

    # Provide some things for the namemapper to reference.
    #   $x, $y, $z:     strings ($x == 'x', etc.)
    #   $sd, $so, $sf:  the strings 'd', 'o', 'f'
    #   $d:             a dict, containing all items listed here
    #   $o:             an object, containing all items listed here
    #   $f:             function, which returns $o
    # Since $d and $o contain all these same items, you can chain lookups as
    # deeply as you want, as in "$d.o.f".
    d = { 'x': 'x', 'y': 'y', 'z': 'z',
            'sd': 'd', 'so': 'o', 'sf': 'f' }
    d['d'] = d
    d['o'] = TestObject(d)
    d['f'] = lambda: d['o']
    template = Template(source, searchList=[d])

    try:
        template.respond()
    except (ZeroDivisionError,):
        pass

    Cheetah._namemapper.finishLogging()

    T.assert_equal(log_line_mock.call_count, 1)

    (log_name, line), _kwargs = log_line_mock.call_args

    return parse_log_line(line)

def assert_log_item_count(count, source):
    items = get_log_items_for_template(source)
    T.assert_equal(len(items), count)

def make_flags(*args):
    result = 0
    count = 0
    for item in args:
        result |= item << (count * 2)
        count += 1
    return result

def assert_log_items_match(items, pattern):
    observed = [(item.lookupCount, item.flags) for item in items]
    expected = [
            (len(flags_list) | (LOOKUP_FAILED if failed else 0), make_flags(*flags_list))
            for failed, flags_list in pattern]
    T.assert_sorted_equal(observed, expected)

class BasicTest(T.TestCase):
    def test_simple(self):
        """Test one placeholder using each combination of DID_AUTOKEY and DID_AUTOCALL.
        """
        items = get_log_items_for_template("""
            $o.x
            $d.x
            $o.f
            $d.f
            """)

        assert_log_items_match(items, [
            (False, [DID_AUTOKEY, 0]),
            (False, [DID_AUTOKEY, DID_AUTOKEY]),
            (False, [DID_AUTOKEY, DID_AUTOCALL]),
            (False, [DID_AUTOKEY, DID_AUTOKEY | DID_AUTOCALL]),
            ])

    def test_nested(self):
        """Test a placeholder that contains another placeholder as a
        subexpression.
        """
        items = get_log_items_for_template("$d[$sd].y")

        assert_log_items_match(items, [
            (False, [DID_AUTOKEY]),                 # $sd
            (False, [DID_AUTOKEY, DID_AUTOKEY]),    # $d[$sd].y
            ])

class ExceptionTest(T.TestCase):
    def test_simple_exception(self):
        """Test a placeholder that raises an exception partway through
        evaluation.
        """
        items = get_log_items_for_template("$d[1/0].y")

        assert_log_items_match(items, [
            (True, [DID_AUTOKEY])
            ])

    def test_abort_in_call(self):
        """Test aborting a placeholder evaluation inside a function call,
        without propagating the exception.
        """
        items = get_log_items_for_template("""
            #def g
                #try
                    $d[1/0].x
                #except ZeroDivisionError
                    #pass
                #end try
                #return 'o'
            #end def
     
            $d[$g()].y
                """)

        assert_log_items_match(items, [
            (True, [DID_AUTOKEY]),                  # $d[1/0].x
            (False, [0]),                           # $g()
            (False, [DID_AUTOKEY, 0]),              # $d[$g().y]
            ])

    def test_abort_in_call_non_nested(self):
        """Like test_abort_in_call, but the call is not nested inside another
        placeholder evaluation.
        """
        items = get_log_items_for_template("""
            #def g
                #try
                    $d[1/0].x
                #except ZeroDivisionError
                    #pass
                #end try
                #return 'o'
            #end def

            $g()
            $x
                """)

        assert_log_items_match(items, [
            (True, [DID_AUTOKEY]),                  # $d[1/0].x
            (False, [0]),                           # $g()
            (False, [DID_AUTOKEY]),                 # $x
            ])

    def test_abort_in_same_function(self):
        """Test aborting a placeholder evaluation with the next placeholder
        evaluation being in the same function rather than a caller.
        """
        items = get_log_items_for_template("""
            #try
                $d[1/0].x
            #except ZeroDivisionError
                #pass
            #end try

            $x
                """)

        assert_log_items_match(items, [
            (True, [DID_AUTOKEY]),                  # $d[1/0].x
            (False, [DID_AUTOKEY]),                 # $x
            ])

    def test_abort_inside_namemapper(self):
        """Test aborting a placeholder during a call made by the namemapper.
        """
        items = get_log_items_for_template("""
            #def g
                #return 1/0
            #end def

            $g
                """)

        assert_log_items_match(items, [
            (True, []),                            # $g
            ])

if __name__ == '__main__':
	T.run()
