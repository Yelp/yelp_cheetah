import pytest

from Cheetah.compile import compile_to_class


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
    template = compile_to_class(template)
    template = template()
    rc = template.funky('abc def')
    assert rc == 'abc+def'
