import asyncio
import signal

import discord
from tortoise import Tortoise

from shaak.custom_bot import CustomBot, get_command_prefix
from shaak.manager    import Manager
from shaak.conductor  import Conductor
from shaak.utils      import Utils
from shaak.settings   import app_settings

from shaak.modules.word_watch import WordWatch
from shaak.modules.previews   import Previews
from shaak.modules.ban_utils  import BanUtils

from shaak.tasks.guild_cleanup import GuildCleanupTask

async def start_bot():

    print('Initializing database')

    # initialize database before starting bot
    await Tortoise.init(
        db_url=app_settings.database_url,
        modules={'models': ['shaak.models']}
    )
    
    # intents and cache flags
    intents = discord.Intents.none()
    intents.guilds = True
    intents.guild_messages = True # bot supports dms, but currently has no reason to subscribe to them
    intents.reactions = True
    intents.bans = True
    intents.voice_states = True # hopefully this populates our cache enough
    member_cache_flags = discord.MemberCacheFlags(
        online=False,
        voice=True,
        joined=False
    )

    # create bot
    bot = CustomBot(
        command_prefix=get_command_prefix,
        intents=intents,
        member_cache_flags=member_cache_flags
    )
    
    # add cogs
    print('Loading cogs')
    bot.add_cog(Utils(bot))
    manager = Manager(bot)
    bot.add_cog(manager)
    conductor = Conductor(bot)
    bot.add_cog(conductor)
    
    # load modules
    print('Loading modules')
    manager.load_module(WordWatch)
    manager.load_module(Previews)
    manager.load_module(BanUtils)

    # load tasks
    print('Loading tasks')
    conductor.load_task(GuildCleanupTask)

    # start bot
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, lambda: loop.create_task(bot.close()))
    loop.add_signal_handler(signal.SIGTERM, lambda: loop.create_task(bot.close()))
    try:
        print('Starting bot')
        await bot.start(app_settings.token, reconnect=True)
    except discord.PrivilegedIntentsRequired:
        # we currently don't use any privlidged intents, but we could one day
        print('An intent is required! Please go to https://discord.com/developers/applications/ and enable it.')
        exit(1)
    finally:
        if not bot.is_closed():
            await bot.close()
        await Tortoise.close_connections()
