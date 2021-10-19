from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from pyrogram import filters

from ..helper.tranlate import BOT_HANDLE
from ..pupadrive import Pupadrive

if TYPE_CHECKING:
    from pyrogram.types import Message


@Pupadrive.on_message(filters.command(["upload", f"upload@{BOT_HANDLE}"]))
async def upload_file(client: Pupadrive, msg: Message):
    filename = msg.reply_to_message.document.file_name
    file_id = msg.reply_to_message.document.file_id
    check = await client.drive.check_folder(filename)
    if check is None:
        await msg.reply(f"Mirroring {msg.reply_to_message.document.file_name}")
        await client.download_media(file_id, msg.reply_to_message.document.file_name)
        folder_id = await client.drive.create_folder(filename)
        file_upload = client.drive.upload_file(Path(
            f"pupadrive/downloads/{msg.reply_to_message.document.file_name}"), folder_id)
        await file_upload.upload()
        os.remove(
            f"pupadrive/downloads/{msg.reply_to_message.document.file_name}")
    else:
        await msg.reply(f'File already exists\n\nhttps://drive.google.com/drive/folders/{check[0]}')
