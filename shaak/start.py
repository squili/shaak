import asyncio

import discord

from shaak.custom_bot import CustomBot
from shaak.database import (get_command_prefix,
                            start_database)
from shaak.manager import Manager
from shaak.modules.word_watch import WordWatch
from shaak.modules.ban_utils import BanUtils
from shaak.utils import Utils
from shaak.settings import app_settings

def start_bot():

    print('Initializing database')

    # initialize database before starting bot
    loop = asyncio.get_event_loop()
    loop.run_until_complete(loop.create_task(start_database()))
    
    # intents and cache flags
    intents = discord.Intents.none()
    intents.guilds = True
    intents.guild_messages = True # bot supports dms, but currently has no reason to subscribe to them
    intents.reactions = True
    intents.bans = True
    member_cache_flags = discord.MemberCacheFlags(
        online=False,
        voice=False,
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
    
    # load modules
    print('Loading modules')
    manager.load_module(WordWatch)
    # manager.load_module(BanUtils)

    # start bot
    try:
        print('Starting bot')
        bot.run(app_settings.token)
    except discord.PrivilegedIntentsRequired:
        # we currently don't use any privlidged intents, but we could one day
        print('An intent required! Please go to https://discord.com/developers/applications/ and enable it.')
        exit(1)
