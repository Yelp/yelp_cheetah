import pytest

import Cheetah
import Cheetah.Parser
import Cheetah.Template


@pytest.mark.xfail
def test_Chep_2_Conditionalized_Import_Behavior_InlineImport():
    """Verify (new) inline import behavior works"""
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
    template = Cheetah.Template.Template.compile(template)
    template = template()
    rc = template.funky('abc def')
    assert rc == 'abc+def'
