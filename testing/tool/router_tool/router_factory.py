"""
Router factory

SmartTest adapter note:
This file was migrated from another internal repo. Keep it self-contained within
the `testing/` layer (no UI imports, no external config imports).
"""

from .AsusRouter.Asusax86uControl import Asusax86uControl
from .AsusRouter.Asusax88uControl import Asusax88uControl
from .AsusRouter.Asusax88uProControl import Asusax88uProControl
from .OpenWrtWlControl import OpenWrtWlControl

router_list = {
    "ASUS-AX86U": Asusax86uControl,
    "ASUS-AX88U": Asusax88uControl,
    "ASUS-AX88U Pro": Asusax88uProControl,
    "Glmt3000": OpenWrtWlControl,
}


def get_router(router_name: str, address: str | None = None):
    """
        Get router
            Parameters
            ----------
            router_name : object
                Description of parameter 'router_name'.
            address : object
                The router's login address or IP address; if None, a default is used.
            Returns
            -------
            object
                Description of the returned value.
    """
    if router_name not in router_list:
        raise ValueError("Doesn't support this router")

    return router_list[router_name](address)
