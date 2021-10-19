from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import MediaFileUpload, build
from googleapiclient.http import HttpRequest

from .utils import try_get_env

SCOPES = ["https://www.googleapis.com/auth/drive"]

logger = logging.getLogger(__name__)


class FileUpload:
    local_path: Path
    total_size: int
    uploaded_size: int = 0
    drive_parent: str
    drive_id: str
    is_uploading = False
    is_finished = False
    _manager: Drive

    def __init__(self, manager: Drive, local_path: Path, drive_parent: str) -> None:
        stat = local_path.stat()
        self.total_size = stat.st_size
        self.local_path = local_path
        self.drive_parent = drive_parent
        self._manager = manager
        self.start_time = 0.0

    def uploaded(self) -> bool:
        return self.drive_id is not None

    def total_uploaded(self) -> int:
        return self.uploaded_size

    async def upload(self):
        self.is_uploading = True
        self.start_time = time.time()
        file_name = self.local_path.name
        file_metadata = {
            "name": file_name,
            "parents": [self.drive_parent]
        }
        media = MediaFileUpload(self.local_path, resumable=True)
        request = self._manager.service.files().create(body=file_metadata,
                                                       media_body=media,
                                                       fields='id',
                                                       supportsAllDrives=True)  # type: HttpRequest

        loop = asyncio.get_event_loop()
        logger.debug(f"start uploading {self.local_path}")

        def upload_file():
            response = None
            while response is None:
                status, response = request.next_chunk(num_retries=3)
                if status:
                    self.uploaded_size = status.resumable_progress
                logger.debug(
                    f"uploading {self.local_path}: {self.uploaded_size} of {self.total_size}")

            self.uploaded_size = self.total_size
            self.drive_id = response["id"]

        await loop.run_in_executor(None, upload_file)
        self.is_uploading = False
        self.is_finished = True

    def start(self):
        self._task = asyncio.create_task(self.upload())

    async def wait_until_finished(self):
        await self._task

    def cancel(self):
        if self._task:
            self._task.cancel()


class FolderUpload:
    files: list[FileUpload] = []
    total_size: int = 0
    drive_parent: str
    local_path: Path
    is_uploading = False
    is_finished = False
    start_time: float = 0.0
    _manager: Drive

    def __init__(self, manager: Drive, path: Path, drive_parent: str) -> None:
        self.local_path = path
        self.drive_parent = drive_parent
        self._manager = manager

    def total_uploaded(self) -> int:
        total = 0
        for file in self.files:
            total += file.uploaded_size
        return total

    async def _setup(self, path: Path = None, drive_parent: str = None):
        if path is None:
            path = self.local_path
        if drive_parent is None:
            drive_parent = self.drive_parent

        for p in path.iterdir():
            if p.is_dir():
                sub_folder = await self._manager.create_folder(p.name, drive_parent)
                await self._setup(p, sub_folder)
            elif p.is_file():
                file = self._manager.upload_file(p, drive_parent)
                self.total_size += file.total_size
                self.files.append(file)

    async def upload(self):
        await self._setup()
        self.start_time = time.time()
        self.is_uploading = True
        for file in self.files:
            await file.upload()

        self.is_uploading = False
        self.is_finished = True

    def start(self):
        self._task = asyncio.create_task(self.upload())

    def cancel(self):
        if self._task:
            self._task.cancel()


class Drive:
    def __init__(self):
        self.root = try_get_env("DRIVE_ROOT")
        creds = None

        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_console()
            # Save the credentials for the next run
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        self.service = build('drive', 'v3', credentials=creds)
        self.loop = asyncio.get_event_loop()

    def upload_file(self, local_path: Path, drive_parent: str = None):
        if drive_parent is None:
            drive_parent = self.root
        return FileUpload(self, local_path, drive_parent)

    def upload_folder(self, path: Path, drive_parent: str):
        up = FolderUpload(self, path, drive_parent)
        return up

    async def create_folder(self, name: str, root: str = None, app_properties: dict[str, str] = None) -> str:
        if not root:
            root = self.root

        logger.debug(f"create folder {name}")

        file_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [root],
        }

        if app_properties:
            file_metadata["appProperties"] = app_properties

        request = self.service.files().create(
            body=file_metadata,
            fields="id",
            supportsTeamDrives=True)

        response = await self.loop.run_in_executor(None, request.execute)
        return response["id"]

    async def check_folder(self, name: str, drive_parent: str = None) -> Optional[tuple[str, Optional[str]]]:
        if drive_parent is None:
            drive_parent = self.root
        request = self.service.files().list(q=f"'{drive_parent}' in parents and mimeType='application/vnd.google-apps.folder' and name = '{name}' and trashed = false",
                                            spaces='drive',
                                            fields='files(id, appProperties)',
                                            includeItemsFromAllDrives=True,
                                            supportsAllDrives=True)

        response = await self.loop.run_in_executor(None, request.execute)
        results = response.get("files")
        if results is None or len(results) == 0:
            return None
        else:
            try:

                torrent_name: Optional[str] = results[0]["appProperties"]["torrent_name"]
            except KeyError:
                torrent_name = None
            id = results[0].get("id")  # type: str

            return (id, torrent_name)
