"""
Router performance

This module is part of the AsusRouter package.
"""

import logging
import sys
from collections.abc import Mapping
from dataclasses import dataclass
import re
import os
import json
from typing import Literal
from src.util.mixin import json_mixin, nested_dict
from src.util.constants import RouterConst

wifichip, interface = RouterConst.dut_wifichip.split('_')

FPGA_CONFIG = {
    'W1': {'mimo': '1X1', '2.4G': '11N', '5G': '11AC'},
    'W1L': {'mimo': '1X1', '2.4G': '11N', '5G': '11AC'},
    'W1U': {'mimo': '1X1', '2.4G': '11N', '5G': '11AC'},
    'W2': {'mimo': '2X2', '2.4G': '11AX', '5G': '11AX'},
    'W2U': {'mimo': '2X2', '2.4G': '11AX', '5G': '11AX'},
    'W2L': {'mimo': '2X2', '2.4G': '11AX', '5G': '11AX'}
}
@dataclass
class compatibility_router(json_mixin):
    """
        Compatibility router
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """
    _instances = []

    def set_info(self, ip, port, brand, model, setup):
        """
            Set info
                Parameters
                ----------
                ip : object
                    Description of parameter 'ip'.
                port : object
                    Description of parameter 'port'.
                brand : object
                    Description of parameter 'brand'.
                model : object
                    Description of parameter 'model'.
                setup : object
                    Description of parameter 'setup'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        info = nested_dict()
        if not re.match(r'\d+\.\d+\.\d+\.', ip):
            raise ValueError("Format error, pls check the ip address")
        if not port.isdigit():
            raise ValueError("Format error, pls check the port")
        info['ip'] = ip
        info['port'] = port
        info['brand'] = brand.upper()
        info['model'] = model.upper()
        for k, v in setup.items():
            info[k] = v
        self._instances.append(info)

    def __str__(self):
        """
            Str
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                object
                    Description of the returned value.
        """
        return self.to_dict()

    def save_expect(self):
        """
            Save expect
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        with open(f"{os.getcwd()}/config/compatibility_router.json", 'w') as f:
            json.dump(self._instances, f, indent=4, ensure_ascii=False)


class dut_standard(json_mixin):
    """
        Dut standard
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """

    def set_expect(self, *args):
        """
            Set expect
                Parameters
                ----------
                args : object
                    Description of parameter 'args'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        if len(args) == 9:
            chip, band, interface, mode, security_mode, bandwidth, mimo, direction, expect_data = args
        elif len(args) == 8:
            chip = 'COMMON'
            band, interface, mode, security_mode, bandwidth, mimo, direction, expect_data = args
        else:
            raise TypeError("set_expect() expects 8 or 9 positional arguments.")

        chip = str(chip).upper()
        band = str(band).upper()
        interface = str(interface).upper()
        mode = str(mode).upper()
        security_mode = str(security_mode).upper()
        bandwidth_key = str(bandwidth).upper()
        mimo_key = str(mimo).upper()
        direction_key = str(direction).upper()

        valid_bands = {'2.4G': ["11N", "11AX"], '5G': ["11AX", "11AC"]}
        valid_bandwidth = {'2.4G': ["20/40MHZ", "20MHZ", "40MHZ"],
                           '5G': ["20/40/80MHZ", "20MHZ", "40MHZ", "80MHZ"]}
        valid_mimo = ["1X1", "2X2", "3X3", "4X4"]
        valid_auth = ["WPA3", "WPA2", "WEP", "OPEN SYSTEM"]
        valid_direction = ["UL", "DL"]

        if band not in valid_bands:
            raise ValueError("band must be one of: 2.4G, 5G")
        if mode not in valid_bands[band]:
            raise ValueError(f"mode for {band} must be one of: {valid_bands[band]}")
        if bandwidth_key not in valid_bandwidth[band]:
            raise ValueError(f"bandwidth for {band} must be one of: {valid_bandwidth[band]}")
        if mimo_key not in valid_mimo:
            raise ValueError(f"mimo must be one of: {valid_mimo}")
        if direction_key not in valid_direction:
            raise ValueError("direction must be UL or DL")
        if security_mode not in valid_auth:
            raise ValueError("security_mode must be one of: WPA3, WPA2, WEP, OPEN SYSTEM")

        self[chip][band][interface][mode][security_mode][bandwidth_key][mimo_key][direction_key] = expect_data


a = compatibility_router()
a.set_info("192.168.200.3", '1', 'ZTE', 'ZXSLC SR7410',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.3", '2', 'LINKSYS', 'E8450',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.3", '3', 'NETGEAR', 'RAX70',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.3", '4', 'NETGEAR', 'RAX50',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.3", '5', 'NETCORE', 'LK-DS7587',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.3", '6', 'TP-LINK', 'TL-7DR7230YIZHANBAN',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.3", '7', 'RUIJIE', 'X60',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.3", '8', 'AT&T', 'BGW320-500',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.4", '1', 'TP-LINK', 'TL-WDR7660QIANZHAOYIZHANBAN',
           {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.4", '2', 'ASUS', 'RT-AX88U PRO',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.4", '3', 'HONOR', 'X4PRO HLB-600',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.4", '4', 'ZTE', 'ZXSLC SR6110',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.4", '5', 'ARRIS', 'TG3492LG-LG',
           {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.4", '6', 'TENDA', 'JD12LPROXINHAOZENGQIANGBAN',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.4", '7', 'TP-LINK', 'TL-XDR5410YIZHANBAN',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.4", '8', 'RUIJIE', 'RG-EW1300G',
           {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.5", '1', 'NETGEAR', 'AX1800 RAX20',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.5", '2', 'TP-LINK', 'TL-XDR6030YIZHANBAN',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.5", '3', 'THUNDEROBOT', 'SR5301ZA',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.5", '4', 'H3C', 'NX30PRO',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.5", '5', 'XIAOMI', 'BE3600 RD15',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.5", '6', 'XIAOMI', 'R4A',
           {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.5", '7', 'XIAOMI', 'AX3000T RD03',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.5", '8', 'ASUS', 'TX-AX6000',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.6", '1', 'ASUS', 'XD4 PRO',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.6", '2', 'HUAWEI', 'XIHE-BE70',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.6", '3', 'COMFAST', 'CF-WR633AX',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.6", '4', 'H3C', 'MAGIC NX54',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.6", '5', 'TP-LINK', 'TL-7DR3630YIZHANBAN',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.6", '6', 'HUAWEI', 'AX3PRO WS7206',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.6", '7', 'XIAOMI', 'AX3000 RA80',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.6", '8', 'ASUS', 'RT-AC1900P',
           {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.7", '1', 'ARRIS', 'TR4400',
           {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.7", '2', 'TENDA', 'BE6L-PRO',
           {'2.4G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '40MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.7", '3', 'ARRIS', 'W21',
           {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.7", '4', 'HUAWEI', 'BE7',
           {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.7", '5', 'BAFFALO', 'WZR-1750DHP',
           {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.7", '6', 'ARRIS', 'SBR-AC1200P-LAN100M',
           {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.7", '7', 'HUAWEI', 'BE3 PRO',
           {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.7", '8', 'ARRIS', 'TG3452',
           {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'}})

a.set_info("192.168.200.8", '4', 'MERCURY', 'D126-LAN100M',
           {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

# a.set_info("192.168.200.8", '5', 'VANTIVA', 'SETUP-E089',
#            {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '40MHz'},
#             '5G': {'mode': '11AX', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.8", '7', 'BUFFALO', 'WNR-5400XE6P/N',
           {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.set_info("192.168.200.8", '8', 'ARRIS', 'SBR-AC1750',
           {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
            '5G': {'mode': '11AC', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

# a.set_info("192.168.200.103", '1', 'ARRISAAAAA', 'SBR-AAAAA',
#            {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
#             '5G': {'mode': '11AC', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})
#
# a.set_info("192.168.200.103", '2', 'ARRISBBBBB', 'SBR-BBBBBB',
#            {'2.4G': {'mode': '11N', 'security_mode': 'wpa2', 'bandwidth': '20MHz'},
#             '5G': {'mode': '11AC', 'security_mode': 'wpa2', 'bandwidth': '80MHz'}})

a.save_expect()
dut = dut_standard()

dut.set_expect('W1', '2.4G', 'sdio', '11N', 'wpa2', '20MHz', '1x1', 'UL', 42.8)
dut.set_expect('W1', '2.4G', 'sdio', '11N', 'wpa2', '20MHz', '1x1', 'DL', 42.8)
dut.set_expect('W1', '2.4G', 'sdio', '11N', 'wpa2', '40MHz', '1x1', 'UL', 85.5)
dut.set_expect('W1', '2.4G', 'sdio', '11N', 'wpa2', '40MHz', '1x1', 'DL', 85.5)
dut.set_expect('W1', '5G', 'sdio', '11AC', 'wpa2', '80MHz', '1x1', 'UL', 209)
dut.set_expect('W1', '5G', 'sdio', '11AC', 'wpa2', '80MHz', '1x1', 'DL', 237.5)

dut.set_expect('W2', '2.4G', 'sdio', '11N', 'wpa2', '20MHz', '2x2', 'UL', 85.5)
dut.set_expect('W2', '2.4G', 'sdio', '11N', 'wpa2', '20MHz', '2x2', 'DL', 85.5)
dut.set_expect('W2', '2.4G', 'usb', '11N', 'wpa2', '20MHz', '2x2', 'UL', 85.5)
dut.set_expect('W2', '2.4G', 'usb', '11N', 'wpa2', '20MHz', '2x2', 'DL', 85.5)
dut.set_expect('W2', '2.4G', 'pcie', '11N', 'wpa2', '20MHz', '2x2', 'UL', 85.5)
dut.set_expect('W2', '2.4G', 'pcie', '11N', 'wpa2', '20MHz', '2x2', 'DL', 85.5)
dut.set_expect('W2', '2.4G', 'sdio', '11N', 'wpa2', '40MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2', '2.4G', 'sdio', '11N', 'wpa2', '40MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2', '2.4G', 'usb', '11N', 'wpa2', '40MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2', '2.4G', 'usb', '11N', 'wpa2', '40MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2', '2.4G', 'pcie', '11N', 'wpa2', '40MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2', '2.4G', 'pcie', '11N', 'wpa2', '40MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2', '2.4G', 'sdio', '11AX', 'wpa2', '20MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2', '2.4G', 'sdio', '11AX', 'wpa2', '20MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2', '2.4G', 'usb', '11AX', 'wpa2', '20MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2', '2.4G', 'usb', '11AX', 'wpa2', '20MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2', '2.4G', 'pcie', '11AX', 'wpa2', '20MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2', '2.4G', 'pcie', '11AX', 'wpa2', '20MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2', '2.4G', 'sdio', '11AX', 'wpa2', '40MHz', '2x2', 'UL', 325)
dut.set_expect('W2', '2.4G', 'sdio', '11AX', 'wpa2', '40MHz', '2x2', 'DL', 325)
dut.set_expect('W2', '2.4G', 'usb', '11AX', 'wpa2', '40MHz', '2x2', 'UL', 239)
dut.set_expect('W2', '2.4G', 'usb', '11AX', 'wpa2', '40MHz', '2x2', 'DL', 239)
dut.set_expect('W2', '2.4G', 'pcie', '11AX', 'wpa2', '40MHz', '2x2', 'UL', 325)
dut.set_expect('W2', '2.4G', 'pcie', '11AX', 'wpa2', '40MHz', '2x2', 'DL', 325)
dut.set_expect('W2', '5G', 'sdio', '11AC', 'wpa2', '80MHz', '2x2', 'UL', 456)
dut.set_expect('W2', '5G', 'sdio', '11AC', 'wpa2', '80MHz', '2x2', 'DL', 456)
dut.set_expect('W2', '5G', 'usb', '11AC', 'wpa2', '80MHz', '2x2', 'UL', 266)
dut.set_expect('W2', '5G', 'usb', '11AC', 'wpa2', '80MHz', '2x2', 'DL', 266)
dut.set_expect('W2', '5G', 'pcie', '11AC', 'wpa2', '80MHz', '2x2', 'UL', 570)
dut.set_expect('W2', '5G', 'pcie', '11AC', 'wpa2', '80MHz', '2x2', 'DL', 570)
dut.set_expect('W2', '5G', 'sdio', '11AX', 'wpa2', '80MHz', '2x2', 'UL', 456)
dut.set_expect('W2', '5G', 'sdio', '11AX', 'wpa2', '80MHz', '2x2', 'DL', 456)
dut.set_expect('W2', '5G', 'usb', '11AX', 'wpa2', '80MHz', '2x2', 'UL', 266)
dut.set_expect('W2', '5G', 'usb', '11AX', 'wpa2', '80MHz', '2x2', 'DL', 266)
dut.set_expect('W2', '5G', 'pcie', '11AX', 'wpa2', '80MHz', '2x2', 'UL', 712.5)
dut.set_expect('W2', '5G', 'pcie', '11AX', 'wpa2', '80MHz', '2x2', 'DL', 712.5)

dut.set_expect('W2L', '2.4G', 'sdio', '11N', 'wpa2', '20MHz', '2x2', 'UL', 85.5)
dut.set_expect('W2L', '2.4G', 'sdio', '11N', 'wpa2', '20MHz', '2x2', 'DL', 85.5)
dut.set_expect('W2L', '2.4G', 'usb', '11N', 'wpa2', '20MHz', '2x2', 'UL', 85.5)
dut.set_expect('W2L', '2.4G', 'usb', '11N', 'wpa2', '20MHz', '2x2', 'DL', 85.5)
dut.set_expect('W2L', '2.4G', 'sdio', '11N', 'wpa2', '40MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2L', '2.4G', 'sdio', '11N', 'wpa2', '40MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2L', '2.4G', 'usb', '11N', 'wpa2', '40MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2L', '2.4G', 'usb', '11N', 'wpa2', '40MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2L', '2.4G', 'sdio', '11AX', 'wpa2', '20MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2L', '2.4G', 'sdio', '11AX', 'wpa2', '20MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2L', '2.4G', 'usb', '11AX', 'wpa2', '20MHz', '2x2', 'UL', 162.5)
dut.set_expect('W2L', '2.4G', 'usb', '11AX', 'wpa2', '20MHz', '2x2', 'DL', 162.5)
dut.set_expect('W2L', '2.4G', 'sdio', '11AX', 'wpa2', '40MHz', '2x2', 'UL', 325)
dut.set_expect('W2L', '2.4G', 'sdio', '11AX', 'wpa2', '40MHz', '2x2', 'DL', 325)
dut.set_expect('W2L', '2.4G', 'usb', '11AX', 'wpa2', '40MHz', '2x2', 'UL', 239)
dut.set_expect('W2L', '2.4G', 'usb', '11AX', 'wpa2', '40MHz', '2x2', 'DL', 239)
dut.set_expect('W2L', '5G', 'sdio', '11AC', 'wpa2', '80MHz', '2x2', 'UL', 456)
dut.set_expect('W2L', '5G', 'sdio', '11AC', 'wpa2', '80MHz', '2x2', 'DL', 456)
dut.set_expect('W2L', '5G', 'usb', '11AC', 'wpa2', '80MHz', '2x2', 'UL', 266)
dut.set_expect('W2L', '5G', 'usb', '11AC', 'wpa2', '80MHz', '2x2', 'DL', 266)
dut.set_expect('W2L', '5G', 'sdio', '11AX', 'wpa2', '80MHz', '2x2', 'UL', 475)
dut.set_expect('W2L', '5G', 'sdio', '11AX', 'wpa2', '80MHz', '2x2', 'DL', 503.5)
dut.set_expect('W2L', '5G', 'usb', '11AX', 'wpa2', '80MHz', '2x2', 'UL', 266)
dut.set_expect('W2L', '5G', 'usb', '11AX', 'wpa2', '80MHz', '2x2', 'DL', 266)

with open(f"{os.getcwd()}/config/compatibility_dut.json", 'w', encoding='utf-8') as f:
    json.dump(dut.to_dict(), f, indent=4, ensure_ascii=False)


def handle_expectdata(router_info, band, direction, chip_info=None):
    """
        Handle expectdata
            Parameters
            ----------
            router_info : object
                Router information string used to derive the model and configuration paths.
            band : object
                Radio band selection (e.g. 2.4G, 5G) when configuring wireless settings.
            direction : object
                Description of parameter 'direction'.
            chip_info : object
                Description of parameter 'chip_info'.
            Returns
            -------
            object
                Description of the returned value.
    """
    if chip_info is None:
        chip_info = RouterConst.dut_wifichip

    def _normalize_mode(m: str) -> str:
        """
            Normalize mode
                Parameters
                ----------
                m : object
                    Description of parameter 'm'.
                Returns
                -------
                str
                    Description of the returned value.
        """
        if not m:
            return "11AX"
        return str(m).upper().replace("802.11", "")

    def _normalize_bandwidth(bw: str) -> str:
        """
            Normalize bandwidth
                Parameters
                ----------
                bw : object
                    Description of parameter 'bw'.
                Returns
                -------
                str
                    Description of the returned value.
        """
        if not bw:
            return "80MHZ"
        bw = str(bw).upper().replace(" ", "")
        if "160" in bw:
            return "160MHZ"
        if "80" in bw:
            return "80MHZ"
        if "40" in bw:
            return "40MHZ"
        if "20" in bw:
            return "20MHZ"
        return bw

    def _normalize_auth(auth: str) -> str:
        """
            Normalize auth
                Parameters
                ----------
                auth : object
                    Description of parameter 'auth'.
                Returns
                -------
                str
                    Description of the returned value.
        """
        if not auth:
            return "WPA2"
        auth = str(auth).upper().replace("_", "-")
        if "WPA3" in auth:
            return "WPA3"
        if "WPA2" in auth:
            return "WPA2"
        return auth

    mode = _normalize_mode(router_info.get(band, {}).get('mode', '11AX'))
    bandwidth = _normalize_bandwidth(router_info.get(band, {}).get('bandwidth', '80MHz'))
    security_mode = _normalize_auth(router_info.get(band, {}).get('security_mode', 'WPA2'))

    def _parse_chip_payload(payload):
        """
            Parse chip payload
                Parameters
                ----------
                payload : object
                    Description of parameter 'payload'.
                Returns
                -------
                object
                    Description of the returned value.
        """
        wifi_module = ""
        interface = ""
        if isinstance(payload, str):
            parts = payload.split('_', 1)
            wifi_module = parts[0].strip().upper() if parts and parts[0] else ""
            if len(parts) > 1 and parts[1]:
                interface = parts[1].strip().upper()
        elif isinstance(payload, Mapping):
            wifi_module = str(
                payload.get("wifi_module")
                or payload.get("series")
                or payload.get("main_chip")
                or ""
            ).strip().upper()
            interface = str(payload.get("interface") or "").strip().upper()
        elif isinstance(payload, (list, tuple)):
            if payload:
                wifi_module = str(payload[0]).strip().upper()
            if len(payload) > 1:
                interface = str(payload[1]).strip().upper()
        return wifi_module, interface

    default_chip, default_interface = _parse_chip_payload(RouterConst.dut_wifichip)
    raw_chip, raw_interface = _parse_chip_payload(chip_info)
    chip_key = raw_chip or default_chip
    interface = raw_interface or default_interface

    if chip_key in ('W1', 'W1U'):
        chip_key = 'W1'
    elif chip_key in ('W2', 'W2U'):
        chip_key = 'W2'
    elif chip_key == 'W2L':
        chip_key = 'W2L'

    if chip_key not in RouterConst.FPGA_CONFIG:
        chip_key = default_chip if default_chip in RouterConst.FPGA_CONFIG else next(iter(RouterConst.FPGA_CONFIG))

    interface = (interface or default_interface or '').upper().replace('-', '').replace(' ', '')
    mimo_key = RouterConst.FPGA_CONFIG[chip_key]['mimo']

    with open(f"{os.getcwd()}/config/compatibility_dut.json", 'r', encoding='utf-8') as f2:
        dut_data = json.load(f2)

    def _get_default(data, key):
        """
            Get default
                Parameters
                ----------
                data : object
                    Description of parameter 'data'.
                key : object
                    Description of parameter 'key'.
                Returns
                -------
                object
                    Description of the returned value.
        """
        try:
            return data[key]
        except KeyError:
            return data[next(reversed(data))]

    data = _get_default(dut_data, chip_key)
    data = _get_default(data, band.upper())
    data = _get_default(data, interface)
    data = _get_default(data, mode)
    data = _get_default(data, security_mode)
    data = _get_default(data, bandwidth)
    data = _get_default(data, mimo_key)
    return _get_default(data, direction.upper())
