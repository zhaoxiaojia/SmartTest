from __future__ import annotations


class InputMixin:
    def keyevent(self, keycode):
        return self._keyevent_impl(keycode)

    def _keyevent_impl(self, keycode):
        raise NotImplementedError

    def home(self):
        return self._home_impl()

    def _home_impl(self):
        raise NotImplementedError

    def back(self):
        return self._back_impl()

    def _back_impl(self):
        raise NotImplementedError

    def app_switch(self):
        return self._app_switch_impl()

    def _app_switch_impl(self):
        raise NotImplementedError

    def tap(self, x, y):
        return self._tap_impl(x, y)

    def _tap_impl(self, x, y):
        raise NotImplementedError

    def swipe(self, x_start, y_start, x_end, y_end, duration):
        return self._swipe_impl(x_start, y_start, x_end, y_end, duration)

    def _swipe_impl(self, x_start, y_start, x_end, y_end, duration):
        raise NotImplementedError

    def text(self, text):
        return self._text_impl(text)

    def _text_impl(self, text):
        raise NotImplementedError
