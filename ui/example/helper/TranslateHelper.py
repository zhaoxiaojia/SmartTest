from PySide6.QtCore import QObject, Signal, Property, QTranslator
from PySide6.QtCore import QLocale
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine

from FluentUI.FluApp import FluApp
from FluentUI.Singleton import Singleton
from example.helper.SettingsHelper import SettingsHelper


@Singleton
class TranslateHelper(QObject):
    currentChanged = Signal()
    languagesChanged = Signal()

    def __init__(self):
        QObject.__init__(self, QGuiApplication.instance())
        self._engine = None
        self._translator = None
        self._current = None
        self._languages = None
        self._languages = ['en_US', 'zh_CN']
        self._current = SettingsHelper().getLanguage()

    @Property(str, notify=currentChanged)
    def current(self):
        return self._current

    @current.setter
    def current(self, value):
        next_value = str(value or "").strip()
        if next_value == "" or next_value == self._current:
            return
        self._current = next_value
        SettingsHelper().saveLanguage(self._current)
        self._reload_translator()
        FluApp().applyLocale(QLocale(self._current))
        self.currentChanged.emit()

    @Property(list, notify=languagesChanged)
    def languages(self):
        return self._languages

    @languages.setter
    def languages(self, value):
        self._languages = value
        self.languagesChanged.emit()

    def init(self, engine: QQmlEngine):
        self._engine = engine
        self._translator = QTranslator()
        QGuiApplication.installTranslator(self._translator)
        self._reload_translator()

    def _reload_translator(self) -> None:
        if self._translator is None:
            return
        QGuiApplication.removeTranslator(self._translator)
        self._translator = QTranslator()
        QGuiApplication.installTranslator(self._translator)
        self._translator.load(f":/example/i18n/example_{self._current}.qm")
        if self._engine is not None:
            self._engine.retranslate()
