from __future__ import absolute_import
from __future__ import unicode_literals

import markupsafe
import Cheetah.Template


class extends_test_template(Cheetah.Template.Template):
    def spacer(self):
        return markupsafe.Markup(
            '<img src="spacer.gif" width="1" height="1" alt="" />'
        )
