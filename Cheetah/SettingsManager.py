from __future__ import unicode_literals


def convert_value(s):
    if s.lower() == 'none':
        return None
    elif s.lower() == 'true':
        return True
    elif s.lower() == 'false':
        return False
    return s


class SettingsManager(object):
    """A mixin class that provides facilities for managing application settings.
    """

    def __init__(self):
        super(SettingsManager, self).__init__()
        self._settings = {}
        self._initializeSettings()

    def _initializeSettings(self):
        raise NotImplementedError

    def setting(self, name):
        """Get a setting from self._settings, with or without a default value."""
        return self._settings[name]

    def setSetting(self, name, value):
        """Set a setting in self._settings."""
        self._settings[name] = value

    def settings(self):
        """Return a reference to the settings dictionary"""
        return self._settings

    def updateSettings(self, newSettings):
        """Update the settings with a selective merge or a complete overwrite."""
        self._settings.update(newSettings)

    def updateSettingsFromConfigStr(self, config_str):
        """See the docstring for updateSettingsFromConfigFile()"""
        values = [line.split('=') for line in config_str.strip().splitlines()]
        settings = dict(
            (key.strip(), convert_value(value.strip()))
            for key, value in values
        )
        self.updateSettings(settings)
