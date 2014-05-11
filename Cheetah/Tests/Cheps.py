#!/usr/bin/env python

import unittest

import Cheetah
import Cheetah.Parser
import Cheetah.Template

class Chep_2_Conditionalized_Import_Behavior(unittest.TestCase):
    def test_ModuleLevelImport(self):
        ''' Verify module level (traditional) import behavior '''
        pass

    def test_InlineImport(self):
        '''Verify (new) inline import behavior works'''
        print 'this test is disabled'
        return

        template = '''
            #def funky($s)
                #try
                    #import urllib
                #except ImportError
                    #pass
                #end try
                #return urllib.quote($s)
            #end def
        '''
        try:
            template = Cheetah.Template.Template.compile(template)
        except Cheetah.Parser.ParseError, ex:
            self.fail('Failed to properly generate code %s' % ex)
        template = template()
        rc = template.funky('abc def')
        assert rc == 'abc+def'

if __name__ == '__main__':
    unittest.main()
