from aiohttp import ClientSession


class HttpMethods:
    def __init__(
            self,
            client: ClientSession,
            headers: dict = None,
            proxy: dict = None) -> None:
        self.__session = client
        self.__HEADERS = headers
        self.__PROXY = proxy

    async def get_download_file(self, url: str, file_name: str, payload: dict = None, params: dict = None) -> None:
        async with self.__session.get(url, headers=self.__HEADERS, proxy=self.__PROXY, data=payload, params=params) as resp:
            with open(file_name, 'wb') as fd:
                while True:
                    chunk = await resp.content.read(1024)
                    if not chunk:
                        break
                    fd.write(chunk)

    async def post_download_file(self, url: str, file_name: str, payload: dict = None, params: dict = None) -> None:
        async with self.__session.post(url, headers=self.__HEADERS, proxy=self.__PROXY, data=payload, params=params, ssl=False) as resp:
            with open(file_name, 'wb') as fd:
                while True:
                    chunk = await resp.content.read(1024)
                    if not chunk:
                        break
                    fd.write(chunk)

    async def api_call_get(self, url: str, params: dict = None, payload: dict = None):
        async with self.__session.get(url, params=params, proxy=self.__PROXY, headers=self.__HEADERS, data=payload) as resp:
            return await resp.json()

    async def api_call_post(self, url: str, params: dict = None, payload: dict = None):
        async with self.__session.post(url, params=params, proxy=self.__PROXY, headers=self.__HEADERS, data=payload) as resp:
            return await resp.json()

    async def api_call_get_text(self, url: str, params: dict = None, payload: dict = None) -> str:
        async with self.__session.get(url, params=params, proxy=self.__PROXY, headers=self.__HEADERS, data=payload) as resp:
            return await resp.text()

    async def get_cookie(self, url: str, payload: dict) -> dict:
        async with self.__session.post(url, data=payload) as r:
            cookies = self.__session.cookie_jar.filter_cookies(url)
            return tuple([value.value for key, value in cookies.items()])

    async def close(self):
        await self.__session.close()
