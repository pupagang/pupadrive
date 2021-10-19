from __future__ import annotations
import aiohttp

import asyncio
import re
from pathlib import Path
import time
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


DDOWNLOAD_DL_URL_REGEX = re.compile(
    r"https?://(?:www\.)?ddownload\.com/(\w+)(?:/\w+)?")

DDOWNLOAD_API_URL = "https://api-v2.ddownload.com/api/"
DDOWNLOAD_URL = "https://ddownload.com"


class DDLFileDownload:
    """
    Represents a file download.
    """

    def __init__(self, client: Ddownload, file_id: str, save_path: Path):
        self.file_id = file_id
        self.save_path = save_path
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.is_started = False
        self.is_finished = False
        self.start_time = 0.0
        self._client = client
        self._task = None

    def start(self):
        self._task = asyncio.create_task(self.download())

    def cancel(self):
        if self._task:
            self._task.cancel()

    async def download(self) -> None:
        self.start_time = time.time()
        self.is_started = True

        payload = {
            "op": "download2",
            "id": self.file_id,
            "rand": "",
            "referer": "",
            "method_free": "",
            "method_premium": "1",
            "adblock_detected": "0"
        }

        with open(self.save_path, "wb") as f:
            async with self._client._http.post(f"{DDOWNLOAD_URL}/{self.file_id}", data=payload, proxy=self._client._proxy) as resp:
                if not resp.content_length:
                    raise Exception("Empty response")
                self.total_bytes = resp.content_length
                while True:
                    chunk = await resp.content.read(1024)
                    self.downloaded_bytes += len(chunk)
                    if not chunk:
                        break
                    f.write(chunk)
        self.is_finished = True


class Ddownload:
    def __init__(
            self,
            username: str,
            password: str,
            api_key: str,
            proxy: str = None) -> None:
        self._username = username
        self._password = password
        self._proxy = proxy
        self._api_key = api_key
        self._http = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(verify_ssl=False), trust_env=True)

    async def close(self) -> None:
        await self._http.close()

    def get_file_id(self, url: str) -> Optional[str]:
        m = re.match(DDOWNLOAD_DL_URL_REGEX, url)
        if m:
            return m.group(1)

    async def get_file_info(self, file_id: str) -> Optional[dict]:
        params = {
            "file_code": file_id,
        }
        data = await self.api_get("file/info", params)
        if data is None:
            return None
        return data[0]

    async def api_get(self, url: str, params: dict = {}) -> Optional[Any]:
        params["key"] = self._api_key
        async with self._http.get(DDOWNLOAD_API_URL + url, params=params, proxy=self._proxy) as resp:
            data = await resp.json()
            if data["status"] != 200:
                return None
            return data["result"]

    async def setup(self) -> None:
        payload = {
            "op": "login",
            "login": self._username,
            "password": self._password
        }
        await self._http.post(DDOWNLOAD_URL, data=payload, proxy=self._proxy)
        cookies = self._http.cookie_jar.filter_cookies(DDOWNLOAD_URL)
        if not "xfss" in cookies:
            raise Exception("Login failed")

    async def create_download(self, file_id: str, save_path: Path) -> DDLFileDownload:
        return DDLFileDownload(self, file_id, save_path)
