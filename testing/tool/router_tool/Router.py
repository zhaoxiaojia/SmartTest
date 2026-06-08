"""
Router

This module is part of the AsusRouter package.
"""



from collections import namedtuple


def _info(info):
    """
        Info
            Parameters
            ----------
            info : object
                Description of parameter 'info'.
            Returns
            -------
            object
                Description of the returned value.
    """
    return 'Default' if info == None else info


def router_str(self):
    """
        Router str
            Parameters
            ----------
            None
                This function does not accept any parameters beyond the implicit context.
            Returns
            -------
            object
                Description of the returned value.
    """
    return f'{_info(self.band)},{_info(self.ssid)},{_info(self.wireless_mode)},{_info(self.channel)},{_info(self.bandwidth)},{_info(self.security_mode)}'


RUN_SETTING_ACTIVITY = "am start -n com.android.tv.settings/.MainSettings"
fields = [
    "band",
    "ssid",
    "wireless_mode",
    "channel",
    "bandwidth",
    "security_mode",
    "password",
    "country",
    "hidden",
]
Router = namedtuple('Router', fields, defaults=(None,) * len(fields))
Router.__str__ = router_str
Router.__repr__ = router_str
