class BrowserSession:
    def __init__(self, context, *, on_close=None):
        self._context = context
        self._closed = False
        self._on_close = on_close

    @property
    def closed(self):
        return self._closed

    async def new_page(self):
        return await self._context.new_page()

    async def close(self):
        if not self._closed:
            self._closed = True
            try:
                await self._context.close()
            finally:
                if self._on_close:
                    self._on_close(self)
