import logging
import os
import time

from pyrogram import Client, filters
from pyrogram.raw.all import layer
from pyrogram.raw.functions.bots import SetBotCommands
from pyrogram.raw.types.bot_command import BotCommand
from pyrogram.types import Message

from . import __version__
from .helper.ddownload import Ddownload
from .helper.drive import Drive
from .helper.rapidgator import Rapidgator
from .helper.tranlate import BOT_HANDLE
from .helper.utils import try_get_env
from .manager import FileManager, StatusMessageManager

logger = logging.getLogger(__name__)


class Pupadrive(Client):
    def __init__(self):
        _name = self.__class__.__name__.lower()

        API_ID = int(try_get_env("API_ID"))
        API_HASH = try_get_env("API_HASH")
        BOT_TOKEN = try_get_env("BOT_TOKEN")
        OWNER_ID = int(try_get_env("OWNER_ID"))
        PROXY_HOSTNAME = try_get_env("PROXY_HOSTNAME")
        PROXY_USERNAME = try_get_env("PROXY_USERNAME")
        PROXY_PASSWORD = try_get_env("PROXY_PASSWORD")
        RG_USERNAME = try_get_env("RG_USERNAME")
        RG_PASSWORD = try_get_env("RG_PASSWORD")
        DDL_USERNAME = try_get_env("DDL_USERNAME")
        DDL_PASSWORD = try_get_env("DDL_PASSWORD")
        DDL_API_KEY = try_get_env("DDL_API_KEY")
        PROXY = f"http://{PROXY_USERNAME}:{PROXY_PASSWORD}@{PROXY_HOSTNAME}:3128"

        plugins = dict(root=f"{_name}.plugins")

        super().__init__(_name, API_ID, API_HASH, bot_token=BOT_TOKEN, plugins=plugins)

        PRIVATE = os.getenv("PRIVATE", "False").lower() in ("true", "1", "t")

        self.start_time = time.time()
        if PRIVATE:
            logger.info("Started in private mode.")
        self.owner_id = OWNER_ID
        self.auth_users = [OWNER_ID]
        self.auth_chats = []
        self.file_manager = FileManager(self)
        self.status_manager = StatusMessageManager(self)
        self.drive = Drive()
        self.rapidgator = Rapidgator(RG_USERNAME, RG_PASSWORD)
        self.ddownload = Ddownload(
            DDL_USERNAME, DDL_PASSWORD, DDL_API_KEY, PROXY)

        if PRIVATE:

            @self.on_message(filters.incoming & ~filters.service, group=-1)
            async def check_auth(client: Pupadrive, msg: Message):
                if msg.from_user.id in client.auth_users or msg.chat.id in self.auth_chats:
                    msg.continue_propagation()
                else:
                    await msg.reply("Sorry, you're not authorized")
                    msg.stop_propagation()

            @self.on_message(filters.command(["auth",
                             f"auth@{BOT_HANDLE}"]), group=-1)
            async def auth(client: Pupadrive, msg: Message):
                if msg.from_user.id != client.owner_id:
                    await msg.reply("Sorry, you're not authorized")
                else:
                    self.auth_chats.append(msg.chat.id)
                    await msg.reply("Chat authenticated.")

        @self.on_message(filters.command(["auth",
                         f"auth@{BOT_HANDLE}"]), group=-1)
        async def auth_public(client: Pupadrive, msg: Message):
            await msg.reply("Bot is already public")

    async def start(self):
        await super().start()
        await self.ddownload.setup()
        self.file_manager.start_worker()
        self.status_manager.start_worker()

        me = await self.get_me()

        await self.send(
            SetBotCommands(
                commands=[
                    BotCommand(
                        command="start",
                        description="Get the welcome message"),
                    BotCommand(
                        command="help",
                        description="How to use the bot"),
                    BotCommand(
                        command="info",
                        description="Get some useful information about the bot"),
                    BotCommand(
                        command="stats",
                        description="Get some statistics about the bot"),
                ]  # type: ignore
            )
        )
        logger.info(
            f"Pupadrive v{__version__} (Layer {layer}) started on @{me.username}.")

    async def stop(self, *args):
        await super().stop()
        logger.info("Pupadrive stopped.")
