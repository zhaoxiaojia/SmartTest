class BrowserSession:
    def __init__(self, context):
        self._context = context
        self._closed = False

    async def new_page(self):
        return await self._context.new_page()

    async def close(self):
        if not self._closed:
            self._closed = True
            await self._context.close()
