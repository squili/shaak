'''
This file is part of Shaak.

Shaak is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Shaak is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with Shaak.  If not, see <https://www.gnu.org/licenses/>.
'''

import asyncio
import logging
import signal

import discord
import os
from tortoise import Tortoise

from shaak.custom_bot import CustomBot, get_command_prefix, CustomHelp
from shaak.settings import app_settings

from shaak.manager import Manager
from shaak.conductor import Conductor
from shaak.utils import Utils
from shaak.debug import Debug

from shaak.modules.word_watch import WordWatch
from shaak.modules.previews import Previews
from shaak.modules.ban_utils import BanUtils
from shaak.modules.user_watch import UserWatch
from shaak.modules.hotline import Hotline

from shaak.tasks.guild_cleanup import GuildCleanupTask
from shaak.tasks.bu_event_cleanup import BUEventCleanupTask
from shaak.tasks.performance_metrics import PerformanceMetrics

logger = logging.getLogger('shaak_start')


async def start_bot():

    logger.info('Initializing database')

    # migrate database
    os.system('aerich upgrade')

    # initialize database before starting bot
    await Tortoise.init(
        db_url=app_settings.database_url,
        modules={
            'models': ['shaak.models']
        }
    )

    # intents and cache flags
    intents = discord.Intents(
        guilds=True,
        members=True,
        bans=True,
        messages=True,
        reactions=True,
        message_content=True,
    )
    member_cache_flags = discord.MemberCacheFlags.from_intents(intents)

    # create bot
    bot = CustomBot(
        command_prefix=get_command_prefix,
        intents=intents,
        member_cache_flags=member_cache_flags,
        help_command=CustomHelp()
    )

    # add cogs
    logger.info('Loading cogs')
    await bot.add_cog(Utils(bot))
    await bot.add_cog(Debug(bot))
    manager = Manager(bot)
    await bot.add_cog(manager)
    conductor = Conductor(bot)
    await bot.add_cog(conductor)

    # load modules
    logger.info('Loading modules')
    await manager.load_module(WordWatch)
    await manager.load_module(Previews)
    await manager.load_module(BanUtils)
    await manager.load_module(UserWatch)
    await manager.load_module(Hotline)

    # load tasks
    logger.info('Loading tasks')
    conductor.load_task(GuildCleanupTask)
    conductor.load_task(BUEventCleanupTask)
    conductor.load_task(PerformanceMetrics)

    # start bot
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(
        signal.SIGINT, lambda: loop.create_task(bot.close()))
    loop.add_signal_handler(
        signal.SIGTERM, lambda: loop.create_task(bot.close()))
    try:
        logger.info('Starting bot')
        await bot.start(app_settings.token, reconnect=True)
    except discord.PrivilegedIntentsRequired:
        logger.info(
            'An intent is required! Please go to https://discord.com/developers/applications/ and enable it.')
        exit(1)
    finally:
        if not bot.is_closed():
            await bot.close()
        await Tortoise.close_connections()
