from __future__ import annotations

from typing import TYPE_CHECKING

from pyrogram import filters

from ..helper.tranlate import BOT_HANDLE
from ..pupadrive import Pupadrive

if TYPE_CHECKING:
    from pyrogram.types import Message


@Pupadrive.on_message(filters.command(["mirror", f"mirror@{BOT_HANDLE}"]))
async def mirror(client: Pupadrive, msg: Message):
    magnet_link = msg.text.split(" ", 1)[1]
    await client.file_manager.add_magnet(magnet_link, msg.chat.id)
    await client.status_manager.resend_status_message(msg.chat.id)
