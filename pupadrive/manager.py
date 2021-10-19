from __future__ import annotations

from abc import ABC, abstractmethod
import logging
import os
from pupadrive.helper.ddownload import DDLFileDownload
import shutil
from pathlib import Path
import time
from typing import Any, Optional, Union
import asyncio
import libtorrent as lt
from pyrogram.types import Message

from .helper.drive import FileUpload, FolderUpload
from .helper.utils import try_get_env, get_readable_filesize
from .helper.rapidgator import RapidFileDownload
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pupadrive import Pupadrive


class Status(ABC):

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_status_text(self) -> str:
        pass


class RapidgatorStatus(Status):
    def __init__(self, name: str, status: RapidFileDownload):
        self.name = name
        self.status = status

    def get_name(self) -> str:
        return self.name

    def get_status_text(self) -> str:
        up_speed = self.status.downloaded_bytes / \
            (time.time() - self.status.start_time)
        if self.status.total_bytes == 0:
            up_progress = 0.0
        else:
            up_progress = float(self.status.downloaded_bytes) / \
                float(self.status.total_bytes)
        return f"""
**{self.name}**
__downloading__ {up_progress:.1%}

{get_readable_filesize(self.status.downloaded_bytes)} of {get_readable_filesize(self.status.total_bytes)} done.

⬇️ {get_readable_filesize(int(up_speed))}/s
"""


class DdownloadStatus(Status):
    def __init__(self, name: str, status: DDLFileDownload):
        self.name = name
        self.status = status

    def get_name(self) -> str:
        return self.name

    def get_status_text(self) -> str:
        up_speed = self.status.downloaded_bytes / \
            (time.time() - self.status.start_time)
        if self.status.total_bytes == 0:
            up_progress = 0.0
        else:
            up_progress = float(self.status.downloaded_bytes) / \
                float(self.status.total_bytes)
        return f"""
**{self.name}**
__downloading__ {up_progress:.1%}

{get_readable_filesize(self.status.downloaded_bytes)} of {get_readable_filesize(self.status.total_bytes)} done.

⬇️ {get_readable_filesize(int(up_speed))}/s
"""


class TorrentStatus(Status):
    def __init__(self, torrent_handle) -> None:
        self.torrent_handle = torrent_handle
        super().__init__()

    def get_name(self) -> str:
        return self.torrent_handle.status().name

    def get_status_text(self) -> str:
        status = self.torrent_handle.status()  # type: ignore
        state_str = ['queued', 'checking', 'downloading metadata',
                     'downloading', 'finished', 'seeding', '', 'checking fastresume']
        status_text = f"""
**{status.name[:80]}**
__{state_str[status.state]}__ {status.progress:.1%}

{get_readable_filesize(status.total_done)} of {get_readable_filesize(status.total)} done.
P: {status.num_peers} | S: {status.num_seeds}

⬇️ {get_readable_filesize(status.download_rate)}/s | ⬆️ {get_readable_filesize(status.upload_rate)}/s
"""
        return status_text


class DriveUploadStatus(Status):
    def __init__(self, name: str, status: Union[FolderUpload, FileUpload]) -> None:
        super().__init__()
        self.name = name
        self.status = status

    def get_name(self) -> str:
        return self.name

    def get_status_text(self) -> str:
        up_speed = self.status.total_uploaded() / (time.time() - self.status.start_time)
        total_uploaded = self.status.total_uploaded()
        if self.status.total_size == 0:
            up_progress = 0.0
        else:
            up_progress = float(total_uploaded) / float(self.status.total_size)
        status_text = f"""
**{self.name[:80]}**
__uploading__ {up_progress:.1%}

{get_readable_filesize(total_uploaded)} of {get_readable_filesize(self.status.total_size)} done.

⬆️ {get_readable_filesize(int(up_speed))}/s
"""
        return status_text


class FileManager:
    _client: Pupadrive
    ongoing: dict[str, Any] = {}
    ongoing_lock = asyncio.Lock()

    def __init__(self, client: Pupadrive) -> None:
        self._client = client

        PROXY_HOSTNAME = try_get_env("PROXY_HOSTNAME")
        PROXY_USERNAME = try_get_env("PROXY_USERNAME")
        PROXY_PASSWORD = try_get_env("PROXY_PASSWORD")

        self._ses = lt.session({  # type: ignore
            "proxy_hostname": PROXY_HOSTNAME,
            "proxy_username": PROXY_USERNAME,
            "proxy_password": PROXY_PASSWORD,
            "proxy_type": lt.proxy_type_t.socks5_pw,  # type: ignore
            "proxy_port": 5080
        })

    async def add_magnet(self, magnet: str, chat_id: int):
        info = lt.parse_magnet_uri(magnet)  # type: ignore
        info_hash = str(info.info_hashes.get_best())

        async with self.ongoing_lock:
            if info_hash in self.ongoing:
                logging.info(
                    f"{info_hash} found, subscribing {chat_id} to existing status")
                self._client.status_manager.chat_subscribe(chat_id, info_hash)
                return

        drive_upload = await self._client.drive.check_folder(info_hash)
        if drive_upload:
            logging.info(
                f"{info_hash} already uploaded to drive folder {drive_upload[0]}")
            await self._client.send_message(
                chat_id, f"**{drive_upload[1]}**\n__already uploaded__ \n\nDrive Link: https://drive.google.com/drive/folders/{drive_upload[0]}")
            return

        logging.info(f"{info_hash} not found, new torrent by {chat_id}")
        info.save_path = f"./download/{info_hash}"
        torrent_handle = self._ses.add_torrent(info)
        async with self.ongoing_lock:
            self.ongoing[info_hash] = torrent_handle

        self._client.status_manager.set_status(
            info_hash, TorrentStatus(torrent_handle))
        self._client.status_manager.chat_subscribe(chat_id, info_hash)

    async def add_torrent(self, torrent_file: str, chat_id: int):
        torrent_info = lt.torrent_info(torrent_file)  # type: ignore
        info_hash = str(torrent_info.info_hash())

        async with self.ongoing_lock:
            if info_hash in self.ongoing:
                logging.info(
                    f"{info_hash} found, subscribing {chat_id} to existing status")
                return self.ongoing[info_hash]

        logging.info(f"{info_hash} not found, new torrent by {chat_id}")
        torrent_handle = self._ses.add_torrent({  # type: ignore
            "ti": torrent_info,
            "save_path": f"./download/{info_hash}"
        })

        async with self.ongoing_lock:
            self.ongoing[info_hash] = torrent_handle

        self._client.status_manager.set_status(
            info_hash, TorrentStatus(torrent_handle))
        self._client.status_manager.chat_subscribe(chat_id, info_hash)

    async def add_rapidgator(self, link: str, chat_id: int):
        file_id = self._client.rapidgator.get_file_id(link)
        if file_id is None:
            await self._client.send_message(
                chat_id, "**Rapidgator**\n__invalid url__")
            return
        file_info = await self._client.rapidgator.get_file_info(file_id)
        if file_info is None:
            await self._client.send_message(
                chat_id, "**Rapidgator**\n__not found__")
            return

        file_hash = str(file_info["hash"])
        if file_hash in self.ongoing:
            logging.info(
                f"{file_hash} found, subscribing {chat_id} to existing status")
            self._client.status_manager.chat_subscribe(chat_id, file_hash)
            return
        logging.info(f"{file_hash} not found, new download by {chat_id}")
        file_download = self._client.rapidgator.create_download(
            file_id, Path(f"./download/{file_info['name']}"))
        self.ongoing[file_hash] = file_download
        file_download.start()
        self._client.status_manager.set_status(
            file_hash, RapidgatorStatus(file_info["name"], file_download))
        self._client.status_manager.chat_subscribe(chat_id, file_hash)

    async def add_ddownload(self, link: str, chat_id: int):
        file_id = self._client.ddownload.get_file_id(link)
        if file_id is None:
            await self._client.send_message(
                chat_id, "**DDownload**\n__invalid url__")
            return
        file_info = await self._client.ddownload.get_file_info(file_id)
        if file_info is None:
            await self._client.send_message(
                chat_id, "**DDownload**\n__not found__")
            return
        file_hash = "ddownload_" + file_id
        if file_hash in self.ongoing:
            logging.info(
                f"{file_hash} found, subscribing {chat_id} to existing status")
            self._client.status_manager.chat_subscribe(chat_id, file_hash)
            return
        logging.info(f"{file_hash} not found, new download by {chat_id}")
        file_download = await self._client.ddownload.create_download(
            file_id, Path(f"./download/{file_info['name']}"))
        self.ongoing[file_hash] = file_download
        file_download.start()
        file_download.total_bytes = int(file_info["size"])
        self._client.status_manager.set_status(
            file_hash, DdownloadStatus(file_info["name"], file_download))
        self._client.status_manager.chat_subscribe(chat_id, file_hash)
        await file_download._task

    def start_worker(self) -> None:
        asyncio.create_task(self.worker())

    async def worker(self) -> None:
        while True:
            async with self.ongoing_lock:
                for id, handle in list(self.ongoing.items()):
                    if isinstance(handle, lt.torrent_handle):  # type: ignore
                        torrent_status = handle.status()
                        if torrent_status.is_seeding:
                            drive_parent = await self._client.drive.create_folder(id, app_properties={"torrent_name": torrent_status.name})
                            drive_upload = self._client.drive.upload_folder(
                                Path(torrent_status.save_path), drive_parent)
                            self.ongoing[id] = drive_upload
                            self._client.status_manager.set_status(
                                id, DriveUploadStatus(torrent_status.name, drive_upload))
                            self._ses.remove_torrent(handle)
                            drive_upload.start()
                    elif isinstance(handle, FolderUpload) or isinstance(handle, FileUpload):
                        if handle.is_finished:
                            del self.ongoing[id]
                            await self._client.status_manager.send_finished(id, handle)
                            if handle.local_path.is_dir():
                                shutil.rmtree(handle.local_path)
                            else:
                                os.remove(handle.local_path)
                    elif isinstance(handle, RapidFileDownload) or isinstance(handle, DDLFileDownload):
                        if handle.is_finished:
                            file_upload = self._client.drive.upload_file(
                                Path(handle.save_path))
                            self.ongoing[id] = file_upload
                            self._client.status_manager.set_status(
                                id, DriveUploadStatus(handle.save_path.name, file_upload))
                            file_upload.start()

            alerts = self._ses.pop_alerts()
            for a in alerts:
                if a.category() & lt.alert.category_t.error_notification:  # type: ignore
                    print(a)

            await asyncio.sleep(0.2)


class Chat:
    def __init__(self, chat_id: int) -> None:
        self.chat_id = chat_id
        self.message: Optional[Message] = None
        self.last_message_text: Optional[str] = None
        self.subscribed: set[str] = set()
        self.should_resend = False


class StatusMessageManager:
    """
    Keeps track of the statuses of the torrents that are currently downloading and updates the
    status messages in the subscribed chats.
    """
    client: Pupadrive

    def __init__(self, client: Pupadrive) -> None:
        self.client = client
        self.statuses: dict[str, Status] = {}
        self.chats: dict[int, Chat] = {}

    def start_worker(self) -> None:
        asyncio.create_task(self.worker())

    def chat_subscribe(self, chat_id: int, id: str):
        if chat_id not in self.chats:
            self.chats[chat_id] = Chat(chat_id)

        logging.info(f"{chat_id} subscribed to {id}")
        self.chats[chat_id].subscribed.add(id)

    def chat_unsubscribe(self, chat_id: int, id: str) -> None:
        self.chats[chat_id].subscribed.remove(id)

    def set_status(self, id: str, status: Status) -> None:
        self.statuses[id] = status

    async def send_finished(self, id: str, status: Union[FolderUpload, FileUpload]):
        """
        Send finished text to all subscribed chats and remove the status from the list.
        """
        s = self.statuses.pop(id)
        for chat in self.chats.values():
            if id in chat.subscribed:
                status_text = f"""
**{s.get_name()[:80]}**
__finished__ (Total: {get_readable_filesize(status.total_size)})

Drive link: https://drive.google.com/drive/folders/{status.drive_parent}
"""
                chat.subscribed.remove(id)
                await self.client.send_message(chat.chat_id, status_text)

    async def resend_status_message(self, chat_id):
        self.chats[chat_id].should_resend = True

    async def worker(self) -> None:
        while True:
            for chat in self.chats.values():

                if chat.should_resend:
                    if chat.message:
                        await chat.message.delete()
                        chat.message = None
                        chat.last_message_text = None
                    chat.should_resend = False

                if not chat.subscribed:
                    if chat.message:
                        await chat.message.delete()
                        chat.message = None
                        chat.last_message_text = None
                    continue

                status_text = ""
                for subscribed in chat.subscribed:
                    status_text += self.statuses[subscribed].get_status_text()

                if chat.message:
                    if chat.last_message_text != status_text:
                        await chat.message.edit(status_text)
                else:
                    chat.message = await self.client.send_message(chat.chat_id, status_text)

                chat.last_message_text = status_text

            await asyncio.sleep(2)
