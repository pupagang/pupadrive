import shutil
import time

from pyrogram import filters
from pyrogram.types import Message
from ..pupadrive import Pupadrive
from ..helper.tranlate import (BOT_HANDLE, HELP_MSG,
                               INFO_MSG,
                               STATS_MSG, WELCOME_MSG)
from ..helper.utils import get_readable_filesize, get_readable_time


@Pupadrive.on_message(filters.command(["start", f"start@{BOT_HANDLE}"]))
async def start(client: Pupadrive, msg: Message):
    await msg.reply_text(WELCOME_MSG)


@Pupadrive.on_message(filters.command(["info", f"info@{BOT_HANDLE}"]))
async def info(_, msg: Message):
    await msg.reply_text(INFO_MSG)


@Pupadrive.on_message(filters.command(["help", f"help@{BOT_HANDLE}"]))
async def help(_, msg: Message):
    await msg.reply_text(HELP_MSG)


@Pupadrive.on_message(filters.command(["stats", f"stats@{BOT_HANDLE}"]))
async def stats(client: Pupadrive, msg: Message):
    current_time = get_readable_time((time.time() - client.start_time))
    total, used, free = shutil.disk_usage('.')
    total = get_readable_filesize(total)
    used = get_readable_filesize(used)
    free = get_readable_filesize(free)
    await msg.reply(STATS_MSG.format(current_time, total, used, free))
