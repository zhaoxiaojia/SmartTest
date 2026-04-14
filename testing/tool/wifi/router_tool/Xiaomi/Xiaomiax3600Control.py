"""
Xiaomiax3600 control

This module is part of the AsusRouter package.
"""

import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ..RouterControl import ConfigError
from .XiaomiBaseControl import XiaomiBaseControl


class Xiaomiax3600Control(XiaomiBaseControl):
    """
        Xiaomiax3600 control
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """

    def __init__(self, address: str | None = None):
        """
            Init
                Parameters
                ----------
                address : object
                    The router's login address or IP address; if None, a default is used.
                Returns
                -------
                None
                    This function does not return a value.
        """
        super().__init__('xiaomi_ax3600', display=True, address=address)

    def change_setting(self, router):
        """
            Change setting
                Interacts with the router's web interface using Selenium WebDriver.
                Pauses execution for a specified duration to allow operations to complete.
                Logs informational or debugging messages for tracing execution.
                Parameters
                ----------
                router : object
                    Router control object or router information required to perform operations.
                Returns
                -------
                object
                    Description of the returned value.
        """
        super().change_setting(router)

        try:
            temp = 'apply_2g' if router.band == self.BAND_2 else 'apply_5g'
            wait_for = self.driver.find_element(
                By.XPATH, self.xpath['apply_element'][temp])
            self.scroll_to(wait_for)
            wait_for.click()
            self.driver.find_element(By.XPATH, '/html/body/div[1]/div/div[3]/div/a[1]/span').click()
        except Exception as e:
            logging.warning("Failed to click apply")
        try:
            if ('需要30秒请等待...' in self.driver.
                    find_element(By.XPATH, '/html/body/div[1]/div/div[2]/div/div/div[2]').text):
                logging.info('Need wait 30 seconds')
                time.sleep(30)
            else:
                logging.info('Need wait 75 seconds')
                time.sleep(75)
        except Exception as e:
            time.sleep(75)
            logging.warning("Fail to find hold on windows")
        time.sleep(3)

        if router.wireless_mode:
            logging.info(f'coco {router.wireless_mode}')
            wifi6_switch = self.driver.find_element(By.XPATH,
                                                    '//*[@id="WIFI6switch"]')
            self.scroll_to(wifi6_switch)
            logging.info(wifi6_switch.get_attribute("data-on"))
            if wifi6_switch.get_attribute("data-on") != ('0' if router.wireless_mode == '11ax' else '1'):
                logging.info('click')
                wifi6_switch.click()
                time.sleep(35)

        logging.info('Router setting done')
        self.driver.quit()
        return True














