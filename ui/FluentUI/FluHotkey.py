import sys

from PySide6.QtCore import Signal, QObject, Property

keyboard = None

if not sys.platform.startswith("linux"):
    try:
        import keyboard
    except Exception:
        keyboard = None


# noinspection PyPep8Naming
class FluHotkey(QObject):
    sequenceChanged = Signal()
    nameChanged = Signal()
    isRegisteredChanged = Signal()
    activated = Signal()

    _warning_printed = False

    def hotkeyCallback(self):
        self.activated.emit()

    def __init__(self):
        QObject.__init__(self)
        self._sequence: str = ""
        self._name: str = ""
        self._isRegistered: bool = False

        def handleSequenceChanged():
            if sys.platform.startswith("linux"):
                self.isRegistered = False
                if not FluHotkey._warning_printed:
                    FluHotkey._warning_printed = True
                    print(
                        "[FluHotkey] global hotkeys disabled on linux because keyboard requires elevated permissions",
                        file=sys.stderr,
                    )
                return

            if keyboard is None:
                self.isRegistered = False
                return

            try:
                keyboard.add_hotkey(self._sequence, self.hotkeyCallback)
                self.isRegistered = True
            except Exception:
                self.isRegistered = False

        self.sequenceChanged.connect(lambda: handleSequenceChanged())

    @Property(bool, notify=isRegisteredChanged)
    def isRegistered(self):
        return self._isRegistered

    @isRegistered.setter
    def isRegistered(self, value):
        if self._isRegistered == value:
            return
        self._isRegistered = value
        self.isRegisteredChanged.emit()

    @Property(str, notify=nameChanged)
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if self._name == value:
            return
        self._name = value
        self.nameChanged.emit()

    @Property(str, notify=sequenceChanged)
    def sequence(self):
        return self._sequence

    @sequence.setter
    def sequence(self, value):
        if self._sequence == value:
            return
        self._sequence = value
        self.sequenceChanged.emit()
