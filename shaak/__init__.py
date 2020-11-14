import asyncio, json, sqlalchemy, discord
from shaak.settings import app_settings
from shaak.database import metadata, Setting, start_database, get_command_prefix
from shaak.manager import Manager
from shaak.utils import Utils
from shaak.modules.word_watch import WordWatch
from shaak.custom_bot import CustomBot
from discord.ext import commands
from pathlib import Path
from alembic import command
from alembic.config import Config

def ask_user(msg: str, default_true: bool = True):
    return input(f'{msg} [{"Y" if default_true else "y"}/{"n" if default_true else "N"}] ').strip().lower()[0:] in (['y', ''] if default_true else ['y'])

async def set_db_defaults(settings):
    await start_database()
    await Setting.objects.create(server_id=0, **settings)
        
def initialize_bot():
    
    # initialize settings

    settings_path = Path('settings.json')
    if not settings_path.exists() or ask_user('Overwrite settings?'):

        settings = {}
        setting_names = [
            [ 'token',        str ],
            [ 'database_url', str ]
        ]

        for name in setting_names:
            settings[name[0]] = name[1](input(f'Enter {name[0]}: ').strip())

        print('Writing settings')
        with settings_path.open('w') as f:
            json.dump(settings, f, indent=4)

    # initialize database

    if ask_user('Overwrite DB?'):

        print('Creating tables')
        engine = sqlalchemy.create_engine(app_settings.database_url)
        metadata.drop_all(engine)
        metadata.create_all(engine)

        print('Stamping alembic')
        command.stamp(Config('./alembic.ini'), 'head', purge=True)
        
        print('Enter global settings (press enter for default)')
        settings = {}
        setting_names = [
            [ 'command_prefix', '-', str ]
        ]
        for name in setting_names:
            settings[name[0]] = name[2](input(f'{name[0]} [{name[1]}]: ').strip()) or name[1]
        bool_setting_names = [
            [ 'verbose_errors', True  ]
        ]
        for name in bool_setting_names:
            settings[name[0]] = ask_user(name[0], name[1])
        
        asyncio.run(set_db_defaults(settings))

def start_bot():
    
    print('Initializing database')
    
    # initialize database before starting bot
    loop = asyncio.get_event_loop()
    loop.run_until_complete(loop.create_task(start_database()))
    
    # intents and cache flags
    intents = discord.Intents.none()
    intents.guilds = True
    intents.messages = True
    intents.dm_messages = True
    intents.reactions = True
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
    manager.load_module(WordWatch)

    # start bot
    try:
        print('Starting bot')
        bot.run(app_settings.token)
    except discord.PrivilegedIntentsRequired:
        # we currently don't use any privlidged intents, but we could one day
        print('An intent required! Please go to https://discord.com/developers/applications/ and enable it.')
        exit(1)