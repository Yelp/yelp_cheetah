#!/usr/bin/python

from collections import namedtuple
import struct
import unittest

from Cheetah.Template import Template
import Cheetah._namemapper

LogItem = namedtuple('LogItem',
        ['fileNameHash', 'placeholderID', 'nameSpaceIndex', 'lookupCount', 'flags'])

LOG_ITEM_STRUCT_SPEC = '<IhbBI'

DID_AUTOKEY = 1
DID_AUTOCALL = 2

LOOKUP_FAILED = 0x80

class LoggingMock(object):
    def __init__(self):
        self.reset_mock()
    
    def reset_mock(self):
        self.call_count = 0
        self.call_args = ()

    def __call__(self, *args, **kwargs):
        self.call_count += 1
        self.call_args = (args, kwargs)

class TestObject(object):
    def __init__(self, dct):
        self._dct = dct

    def __getattr__(self, key):
        return self._dct[key]

class InstrumentationTestCase(unittest.TestCase):
    def parse_log_data(self, blob):
        result = []
        for offset in xrange(0, len(blob), struct.calcsize(LOG_ITEM_STRUCT_SPEC)):
            item_tuple = struct.unpack_from(LOG_ITEM_STRUCT_SPEC, blob, offset)
            result.append(LogItem(*item_tuple))
        return result

    def get_log_items_for_template(self, source, logging_mock=None):
        if logging_mock is None:
            logging_mock = LoggingMock()

        Cheetah._namemapper.setLoggingCallback(logging_mock)

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

        self.assertEqual(logging_mock.call_count, 1)

        (blob,), _kwargs = logging_mock.call_args

        return self.parse_log_data(blob)

    def assert_log_item_count(self, count, source):
        items = self.get_log_items_for_template(source)
        unittest.assertEqual(len(items), count)

    def make_flags(self, *args):
        result = 0
        count = 0
        for item in args:
            result |= item << (count * 2)
            count += 1
        return result

    def assert_log_items_match(self, items, pattern):
        observed = [(item.lookupCount, item.flags) for item in items]
        expected = [
                (len(flags_list) | (LOOKUP_FAILED if failed else 0), self.make_flags(*flags_list))
                for failed, flags_list in pattern]
        self.assertEqual(sorted(observed), sorted(expected))

class BasicTest(InstrumentationTestCase):
    def test_simple(self):
        """Test one placeholder using each combination of DID_AUTOKEY and DID_AUTOCALL.
        """
        items = self.get_log_items_for_template("""
            $o.x
            $d.x
            $o.f
            $d.f
            """)

        self.assert_log_items_match(items, [
            (False, [DID_AUTOKEY, 0]),
            (False, [DID_AUTOKEY, DID_AUTOKEY]),
            (False, [DID_AUTOKEY, DID_AUTOCALL]),
            (False, [DID_AUTOKEY, DID_AUTOKEY | DID_AUTOCALL]),
            ])

    def test_nested(self):
        """Test a placeholder that contains another placeholder as a
        subexpression.
        """
        items = self.get_log_items_for_template("$d[$sd].y")

        self.assert_log_items_match(items, [
            (False, [DID_AUTOKEY]),                 # $sd
            (False, [DID_AUTOKEY, DID_AUTOKEY]),    # $d[$sd].y
            ])

class ExceptionTest(InstrumentationTestCase):
    def test_simple_exception(self):
        """Test a placeholder that raises an exception partway through
        evaluation.
        """
        items = self.get_log_items_for_template("$d[1/0].y")

        self.assert_log_items_match(items, [
            (True, [DID_AUTOKEY])
            ])

    def test_abort_in_call(self):
        """Test aborting a placeholder evaluation inside a function call,
        without propagating the exception.
        """
        items = self.get_log_items_for_template("""
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

        self.assert_log_items_match(items, [
            (True, [DID_AUTOKEY]),                  # $d[1/0].x
            (False, [0]),                           # $g()
            (False, [DID_AUTOKEY, 0]),              # $d[$g().y]
            ])

    def test_abort_in_call_non_nested(self):
        """Like test_abort_in_call, but the call is not nested inside another
        placeholder evaluation.
        """
        items = self.get_log_items_for_template("""
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

        self.assert_log_items_match(items, [
            (True, [DID_AUTOKEY]),                  # $d[1/0].x
            (False, [0]),                           # $g()
            (False, [DID_AUTOKEY]),                 # $x
            ])

    def test_abort_in_same_function(self):
        """Test aborting a placeholder evaluation with the next placeholder
        evaluation being in the same function rather than a caller.
        """
        items = self.get_log_items_for_template("""
            #try
                $d[1/0].x
            #except ZeroDivisionError
                #pass
            #end try

            $x
                """)

        self.assert_log_items_match(items, [
            (True, [DID_AUTOKEY]),                  # $d[1/0].x
            (False, [DID_AUTOKEY]),                 # $x
            ])

    def test_abort_inside_namemapper(self):
        """Test aborting a placeholder during a call made by the namemapper.
        """
        items = self.get_log_items_for_template("""
            #def g
                #return 1/0
            #end def

            $g
                """)

        self.assert_log_items_match(items, [
            (True, []),                            # $g
            ])

    def test_propagation_through_finishLogging(self):
        """Test propagation of exceptions from the logging callback through
        finishLogging.
        """
        class DummyError(Exception): pass

        def raising_callback(blob):
            raise DummyError()

        self.assertRaises(DummyError,
            self.get_log_items_for_template, "$d.x", logging_mock=raising_callback)

if __name__ == '__main__':
    unittest.main()
