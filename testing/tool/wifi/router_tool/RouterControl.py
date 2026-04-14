"""
Router control

This module is part of the AsusRouter package.
"""

import logging
import os
import time
from abc import ABCMeta, abstractmethod

from selenium import webdriver
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.common.exceptions import NoAlertPresentException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from testing.yamlTool import yamlTool

REGION_CHANNEL_MAP = {
        "US": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        "CN": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 149, 153, 157, 161, 165]
        },
        "EU": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        "JP": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        "IN": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        "KR": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        "AU": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        "GB": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        "RU": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },

        "CA": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 132, 136, 140, 144, 149, 153, 157, 161, 165]
        },
        "AE": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        "AR": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        "AT": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        "BR": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        "DE": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        "ES": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        "FR": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        "HK": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        "MY": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        "MX": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        "PH": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        # TH 泰国
        "TH": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        # ID 印度尼西亚
        "ID": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 149, 153, 157, 161, 165]},
        # VN 越南
        "VN": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        # SG 新加坡
        "SG": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                   157, 161, 165]
        },
        # KZ 哈萨克斯坦
        "KZ": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                      157, 161, 165]},
        # TR 土耳其
        "TR": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]},
        # OM 阿曼
        "OM": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]},
        # SA 沙特阿拉伯
        "SA": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
               },
        # EG 埃及
        "EG": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64]},
        # NG 尼日利亚
        "NG": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [52, 56, 60, 64, 149, 153, 157, 161]},
        # ZA 南非
        "ZA": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]},
        # UY 乌拉圭
        "UY": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 149, 153, 157, 161, 165]},
        # PE 秘鲁
        "PE": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                      157, 161, 165]},
        # CO 哥伦比亚
        "CO": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                      157, 161, 165]},
        # CR 哥斯达黎加
        "CR": {"2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
               "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153,
                      157, 161, 165]},

        # NL 荷兰
        "NL": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # IT 意大利
        "IT": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # PL 波兰
        "PL": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # RO 罗马尼亚
        "RO": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # RO 葡萄牙
        "PT": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # SE 瑞典
        "SE": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
        },
        # RS 塞尔维亚
        "RS": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        # UA 乌克兰
        "UA": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
        #CL:智利
        "CL": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 149, 153, 157, 161, 165]
        },
        # EC 厄瓜多尔
        "EC": {
            "2g": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "5g": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157,
                   161, 165]
        },
    }
class RouterControl(metaclass=ABCMeta):
    """
        Router control
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """

    def __init__(self):
        """
            Init
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        ...

    @abstractmethod
    def login(self):
        """
            Login
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        ...

    @abstractmethod
    def change_setting(self, router):
        """
            Change setting
                Parameters
                ----------
                router : object
                    Router control object or router information required to perform operations.
                Returns
                -------
                None
                    This function does not return a value.
        """
        ...

    @abstractmethod
    def reboot_router(self):
        """
            Reboot router
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        ...


class ConfigError(Exception):
    """
        Config error
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """

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
        return 'element error'


class RouterTools(RouterControl):
    """
        Router tools
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """
    SCROL_JS = 'arguments[0].scrollIntoView();'

    BAND_LIST = ['2.4G', '5G']
    BANDWIDTH_2 = ['20/40 MHz', '20 MHz', '40 MHz']
    BANDWIDTH_5 = ['20/40/80 MHz', '20 MHz', '40 MHz', '80 MHz', '160 MHz']
    WIRELESS_2 = ['auto', '11b', '11g', '11n', '11ax']
    WIRELESS_5: list[str] = ['auto', '11a', '11n', '11ac', '11ax']

    AUTHENTICATION_METHOD = ['Open System', 'WPA2-Personal', 'WPA3-Personal', 'WPA/WPA2-Personal', 'WPA2/WPA3-Personal',
                             'WPA2-Enterprise', 'WPA/WPA2-Enterprise']

    AUTHENTICATION_METHOD_LEGCY = ['Open System', 'Shared Key', 'WPA2-Personal', 'WPA3-Personal',
                                   'WPA/WPA2-Personal', 'WPA2/WPA3-Personal', 'WPA2-Enterprise',
                                   'WPA/WPA2-Enterprise', 'Radius with 802.1x']

    PROTECT_FRAME = {
        '停用': 1,
        '非强制启用': 2,
        '强制启用': 3
    }

    WEP_ENCRYPT = ['None', 'WEP-64bits', 'WEP-128bits']

    WPA_ENCRYPT = {
        'AES': 1,
        'TKIP+AES': 2
    }

    PASSWD_INDEX_DICT = {
        '1': '1',
        '2': '2',
        '3': '3',
        '4': '4'
    }
    CHANNEL_2 = ['auto', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11']
    CHANNEL_5 = ['auto', '36', '40', '44', '48', '52', '56', '60', '64', '100', '104', '108', '112', '116', '120',
                 '124', '128', '132', '136', '140', '144', '149', '153', '157', '161', '165']
    COUNTRY_CODE = {
        '亚洲': '1',
        '中国 (默认值)': '2',
        '欧洲': '2',
        '韩国': '4',
        '俄罗斯': '5',
        '新加坡': '6',
        '美国': '7',
        '澳大利亚': '8'
    }
    COUNTRY_DISPLAY_NAMES = {
        'CN': {'zh': '中国 (默认值)', 'en': 'China (Default)'},
        'US': {'zh': '美国', 'en': 'United States'},
        'EU': {'zh': '欧洲', 'en': 'Europe'},
        'KR': {'zh': '韩国', 'en': 'Korea'},
        'RU': {'zh': '俄罗斯', 'en': 'Russia'},
        'SG': {'zh': '新加坡', 'en': 'Singapore'},
        'AU': {'zh': '澳大利亚', 'en': 'Australia'},
        'ASIA': {'zh': '亚洲', 'en': 'Asia'}
    }
    UI_TO_DRIVER_COUNTRY_MAP = {
        'US': 'US',  # 美国 → US
        'CN': 'CN',  # 中国 → CN
        'EU': 'E0',  # 欧洲 → E0 (华硕自定义)
        'KR': 'KR',  # 韩国 → KR
        'RU': 'RU',  # 俄罗斯 → RU
        'SG': 'SG',  # 新加坡 → SG
        'AU': 'AU',  # 澳大利亚 → AU
        'ASIA': 'AS',  # 亚洲 → AS (需确认，部分固件用 'AS')
    }

    def __init__(self, router_info, display=True, address: str | None = None):

        """
            Init
                Loads router‑specific configuration or XPath definitions from YAML files.
                Logs informational or debugging messages for tracing execution.
                Parameters
                ----------
                router_info : object
                    Router information string used to derive the model and configuration paths.
                display : object
                    Flag indicating whether the browser should run in visible mode.
                address : object
                    The router's login address or IP address; if None, a default is used.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.router_type = router_info.split("_")[0]

        self.router_info = router_info

        self.yaml_info = yamlTool(os.getcwd() + f'\\config\\router_xpath\\{self.router_type.split("_")[0]}_xpath.yaml')

        self.xpath = self.yaml_info.get_note(self.router_type)

        default_address = {
            'xiaomi': '192.168.31.1',
            'asus': '192.168.50.1',
            'h3c': '192.168.4.1',
            'linksys': '192.168.3.1',
            'netgear': '192.168.9.1',
            'tplink': '192.168.5.1',
            'zte': '192.168.2.1'
        }.get(self.router_type, '192.168.1.1')
        self.address = address or default_address
        logging.info("Router gateway address: %s", self.address)
        self.ping_address = self.address
        logging.info("Preparing router session for %s", self.router_info)

    def scroll_to(self, target):
        """
            Scroll to
                Parameters
                ----------
                target : object
                    Web element or element locator used for interaction via Selenium.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.driver.execute_script(self.SCROL_JS, target)

    def _init(self):
        """
            Init
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.option = webdriver.ChromeOptions()

        self.option.add_argument("--start-maximized")
        self.option.add_experimental_option("detach", True)
        self.driver = webdriver.Chrome(options=self.option)

        self.driver.implicitly_wait(3)

    def login(self):

        """
            Login
                Interacts with the router's web interface using Selenium WebDriver.
                Waits for specific web elements to satisfy conditions using WebDriverWait.
                Pauses execution for a specified duration to allow operations to complete.
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self._init()
        self.driver.get(f"http://{self.address}")
        time.sleep(1)
        WebDriverWait(driver=self.driver, timeout=10, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.ID, self.xpath['username_element'])))
        self.driver.find_element(By.ID, self.xpath['username_element']).click()
        self.driver.find_element(By.ID, self.xpath['username_element']).send_keys(self.xpath['account'])

        self.driver.find_element(By.NAME, self.xpath['password_element']).click()
        self.driver.find_element(By.NAME, self.xpath['password_element']).send_keys(self.xpath['passwd'])

        self.driver.find_element(By.XPATH, self.xpath['signin_element'][self.router_info]).click()

        WebDriverWait(driver=self.driver, timeout=10, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.ID, self.xpath['signin_done_element'])))
        time.sleep(1)

    def change_setting(self, router):
        """
            Change setting
                Parameters
                ----------
                router : object
                    Router control object or router information required to perform operations.
                Returns
                -------
                None
                    This function does not return a value.
        """
        ...

    def reboot_router(self):
        """
            Reboot router
                Waits for specific web elements to satisfy conditions using WebDriverWait.
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.driver.execute_script('reboot()')
        self.driver.switch_to.alert.accept()

        element = {
            'asus_86u': self.xpath['wait_reboot_element']['asus_86u'],
            'asus_88u': self.xpath['wait_reboot_element']['asus_88u'],
            'asus_88u_pro': self.xpath['wait_reboot_element']['asus_88u_pro'],
            'asus_5400': self.xpath['wait_reboot_element']['asus_5400'],
        }
        WebDriverWait(self.driver, 180).until(
            EC.visibility_of_element_located((By.XPATH, element[self.router_info]))
        )
        self.driver.quit()

    def change_band(self, band):
        """
            Change band
                Interacts with the router's web interface using Selenium WebDriver.
                Parameters
                ----------
                band : object
                    Radio band selection (e.g. 2.4G, 5G) when configuring wireless settings.
                Returns
                -------
                None
                    This function does not return a value.
        """
        bind_select = Select(self.driver.find_element(By.XPATH, self.xpath['band_element']))
        bind_select.select_by_visible_text(band)

    def change_ssid(self, ssid):
        """
            Change SSID
                Interacts with the router's web interface using Selenium WebDriver.
                Asserts conditions to validate the success of operations.
                Parameters
                ----------
                ssid : object
                    Wi‑Fi network SSID used for association.
                Returns
                -------
                None
                    This function does not return a value.
        """
        ssid_element = self.driver.find_element(By.ID, self.xpath['ssid_element'])
        self.driver.execute_script(f'arguments[0].value = "{ssid}"', ssid_element)
        assert ssid_element.get_attribute('value') == ssid, "Set ssid error"

    def change_hide_ssid(self, status):
        """
            Change hide SSID
                Parameters
                ----------
                status : object
                    Description of parameter 'status'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        ...

    def change_channel(self, channel):

        """
            Change channel
                Interacts with the router's web interface using Selenium WebDriver.
                Asserts conditions to validate the success of operations.
                Parameters
                ----------
                channel : object
                    Specific wireless channel to select during configuration.
                Returns
                -------
                None
                    This function does not return a value.
        """
        select = Select(
            self.driver.find_element(By.XPATH, self.xpath['channel_element'][self.router_info]))
        select.select_by_visible_text(channel)

        assert select.first_selected_option.text == channel, "Channel not selected"

    def change_bandwidth(self, bandwidth):
        """
            Change bandwidth
                Interacts with the router's web interface using Selenium WebDriver.
                Asserts conditions to validate the success of operations.
                Parameters
                ----------
                bandwidth : object
                    Channel bandwidth (e.g. 20 MHz, 40 MHz, 80 MHz) when configuring wireless settings.
                Returns
                -------
                None
                    This function does not return a value.
        """
        bandwidth_select = Select(self.driver.find_element(By.XPATH, self.xpath['bandwidth_element']))
        bandwidth_select.select_by_visible_text(bandwidth)

        assert bandwidth_select.first_selected_option.text == bandwidth, "Band width mode not selected"

    def change_authentication(self, mode):
        """
            Change authentication
                Interacts with the router's web interface using Selenium WebDriver.
                Asserts conditions to validate the success of operations.
                Parameters
                ----------
                mode : object
                    Wireless mode to configure on the router (e.g. 11n, 11ax).
                Returns
                -------
                None
                    This function does not return a value.
        """
        select = Select(self.driver.find_element(
            By.XPATH, self.xpath['authentication_element'][self.router_info]))
        select.select_by_visible_text(mode)

        assert select.first_selected_option.text == mode, "Authentication mode not selected"

    def change_wep_encrypt(self, text):
        """
            Change wep encrypt
                Interacts with the router's web interface using Selenium WebDriver.
                Asserts conditions to validate the success of operations.
                Parameters
                ----------
                text : object
                    Description of parameter 'text'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        select = Select(self.driver.find_element(
            By.XPATH, self.xpath['wep_encrypt_regu_element'][self.router_info].format(text)))
        select.select_by_visible_text(text)

        assert select.first_selected_option.text == text, "Wep encrypt not selected"

    def change_wpa_encrypt(self, encrpyt):
        """
            Change wpa encrypt
                Interacts with the router's web interface using Selenium WebDriver.
                Asserts conditions to validate the success of operations.
                Parameters
                ----------
                encrpyt : object
                    Description of parameter 'encrpyt'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        select = Select(self.driver.find_element(By.XPATH, self.xpath['wpa_encrypt_element']))
        select.select_by_visible_text(encrpyt)

        assert select.first_selected_option.text == encrpyt, "Wpa encrpyt not selected"

    def change_passwd_index(self, index):

        """
            Change passwd index
                Interacts with the router's web interface using Selenium WebDriver.
                Asserts conditions to validate the success of operations.
                Parameters
                ----------
                index : object
                    Description of parameter 'index'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        select = Select(self.driver.find_element(By.XPATH, self.xpath['passwd_index_element'][self.router_info]))
        select.select_by_visible_text(index)

        assert select.first_selected_option.text == index, "Password index not selected"

    def change_wep_passwd(self, passwd):
        """
            Change wep passwd
                Interacts with the router's web interface using Selenium WebDriver.
                Asserts conditions to validate the success of operations.
                Parameters
                ----------
                passwd : object
                    Description of parameter 'passwd'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        element = self.driver.find_element(By.ID, self.xpath['wep_passwd_element'])
        element.click()
        element.clear()
        element.send_keys(passwd)

        assert element.get_property('value') == passwd, "Wep password set error"

    def change_passwd(self, passwd):

        """
            Change passwd
                Interacts with the router's web interface using Selenium WebDriver.
                Asserts conditions to validate the success of operations.
                Parameters
                ----------
                passwd : object
                    Description of parameter 'passwd'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        element = self.driver.find_element(By.XPATH, self.xpath['wpa_passwd_element'][self.router_info])
        element.click()
        element.clear()
        element.send_keys(passwd)

        assert element.get_property('value') == passwd, "Wpa password set error"

    def change_protect_frame(self, frame):
        """
            Change protect frame
                Interacts with the router's web interface using Selenium WebDriver.
                Asserts conditions to validate the success of operations.
                Parameters
                ----------
                frame : object
                    Description of parameter 'frame'.
                Returns
                -------
                None
                    This function does not return a value.
        """
        bind_select = Select(
            self.driver.find_element(By.XPATH, self.xpath['protect_frame_element'][self.router_info]))
        bind_select.select_by_visible_text(frame)

        assert bind_select.first_selected_option.text == frame, "Protect frame not selected"

    def apply_setting(self):
        """
            Apply setting
                Interacts with the router's web interface using Selenium WebDriver.
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        self.driver.find_element(By.ID, self.xpath['apply_element']).click()

    def click_alert(self):
        """
            Click alert
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        try:
            self.driver.switch_to.alert.accept()
        except Exception as e:
            ...

    def wait_setting_done(self):
        """
            Wait setting done
                Waits for specific web elements to satisfy conditions using WebDriverWait.
                Pauses execution for a specified duration to allow operations to complete.
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        WebDriverWait(self.driver, 20).until_not(

            EC.visibility_of_element_located((By.XPATH, self.xpath['setting_load_element']))
        )
        time.sleep(2)

    def element_is_selected(self, xpath):
        """
            Element is selected
                Interacts with the router's web interface using Selenium WebDriver.
                Parameters
                ----------
                xpath : object
                    Description of parameter 'xpath'.
                Returns
                -------
                object
                    Description of the returned value.
        """
        element = self.driver.find_element(By.XPATH, xpath)
        if element.is_selected():
            return True
        else:
            return False

    def handle_alert_or_popup(self, timeout=3):

        """
            Handle alert or popup
                Interacts with the router's web interface using Selenium WebDriver.
                Waits for specific web elements to satisfy conditions using WebDriverWait.
                Parameters
                ----------
                timeout : object
                    Maximum time in seconds to wait for a condition to be satisfied.
                Returns
                -------
                object
                    Description of the returned value.
        """
        try:
            alert = self.driver.switch_to.alert
            alert.accept()
            return True
        except NoAlertPresentException:
            pass

        selectors = [
            "//button[text()='OK']",
            "//button[text()='确定']",
            "//button[contains(., '确认')]",
            "//input[@value='OK']",
            "//input[@value='确定']",
        ]
        for sel in selectors:
            try:
                btn = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((By.XPATH, sel))
                )
                btn.click()
                return True
            except TimeoutException:
                continue

        return False

    def close_browser(self):
        """
        显式关闭浏览器和 WebDriver 进程
        安全：可重复调用，不会报错
        """
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()  # 完全退出 Chrome + chromedriver
            except Exception as e:
                logging.warning(f"Warning: Failed to quit WebDriver: {e}")
            finally:
                self.driver = None


