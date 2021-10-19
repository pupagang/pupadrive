from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import Optional

import aiohttp

RAPIDGATOR_DL_URL_REGEX = re.compile(
    r"https?://(?:www\.)?rapidgator\.net/file/(\w+)(?:/\w+)?")
RAPIDGATOR_API_URL = "https://rapidgator.net/api/v2/"


class RapidFileDownload:
    """
    Represents a file download.
    """

    def __init__(self, client: Rapidgator, file_id: str, save_path: Path):
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
        download_url = await self._client.get_direct_link(self.file_id)
        if download_url is None:
            return

        with open(self.save_path, "wb") as f:
            async with self._client._http.get(download_url, proxy=self._client._proxy) as response:
                if not response.content_length:
                    return
                self.total_bytes = response.content_length
                while True:
                    chunk = await response.content.read(16384)
                    self.downloaded_bytes += len(chunk)
                    if not chunk:
                        break
                    f.write(chunk)
        self.is_finished = True


class Rapidgator:
    def __init__(
            self,
            username: str,
            password: str,
            proxy: str = None) -> None:
        self._username = username
        self._password = password
        self._http = aiohttp.ClientSession(trust_env=True)
        self._proxy = proxy

    async def api_get(self, url: str, params: dict = None) -> Optional[dict]:
        async with self._http.get(RAPIDGATOR_API_URL + url, params=params, proxy=self._proxy) as response:
            data = await response.json()
            if data["status"] != 200:
                return None
            return data["response"]

    async def get_token(self) -> Optional[str]:
        params = {
            "login": self._username,
            "password": self._password
        }
        response = await self.api_get("user/login", params=params)
        if response is None:
            return None
        return response["token"]

    def get_file_id(self, url: str) -> Optional[str]:
        m = RAPIDGATOR_DL_URL_REGEX.match(url)
        if m is None:
            return None
        return m.group(1)

    async def get_file_info(self, file_id: str) -> Optional[dict]:
        token = await self.get_token()
        params = {"file_id": file_id, "token": token}
        response = await self.api_get("file/info", params=params)
        if response is None:
            return None
        return response["file"]

    async def get_direct_link(self, file_id: str) -> Optional[str]:
        token = await self.get_token()
        params = {"file_id": file_id, "token": token}
        response = await self.api_get("file/download", params=params)
        if response is None:
            return None
        return response["download_url"]

    def create_download(self, file_id: str, path: Path) -> RapidFileDownload:
        return RapidFileDownload(self, file_id, path)

    async def close(self) -> None:
        await self._http.close()
