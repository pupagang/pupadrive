from __future__ import annotations

from typing import TYPE_CHECKING

from pyrogram import filters

from ..helper.tranlate import BOT_HANDLE
from ..pupadrive import Pupadrive

if TYPE_CHECKING:
    from pyrogram.types import Message


@Pupadrive.on_message(filters.command(["ddownload", f"ddownload@{BOT_HANDLE}"]))
async def mirror_ddownload(client: Pupadrive, msg: Message):
    await client.file_manager.add_ddownload(msg.command[1], msg.chat.id)
