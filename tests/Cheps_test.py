from __future__ import unicode_literals

from Cheetah.compile import compile_to_class


def test_Chep_2_Conditionalized_Import_Behavior_InlineImport():
    """Verify (new) inline import behavior works"""
    template = '''
        #def funky(s)
            #try
                #import os.path
            #except ImportError
                #pass
            #end try
            #return os.path.join('foo', $s)
        #end def
    '''
    template = compile_to_class(
        template, settings={'useLegacyImportMode': False},
    )
    template = template()
    rc = template.funky('abcdef')
    assert rc == 'foo/abcdef'
