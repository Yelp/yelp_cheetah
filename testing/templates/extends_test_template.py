import markupsafe

import Cheetah.Template


class YelpCheetahTemplate(Cheetah.Template.Template):
    def spacer(self):
        return markupsafe.Markup(
            '<img src="spacer.gif" width="1" height="1" alt="" />',
        )
