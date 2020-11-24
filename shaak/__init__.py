import asyncio
import json
import secrets
from pathlib import Path

import discord
import sqlalchemy
from alembic import command
from alembic.config import Config
from discord.ext import commands

def ask_user(msg: str, default_true: bool = True):
    return input(f'{msg} [{"Y" if default_true else "y"}/{"n" if default_true else "N"}] ').strip().lower()[0:] in (['y', ''] if default_true else ['y'])

async def set_global_settings(settings):
    from shaak.database import GlobalSetting, start_database
    await start_database()
    await GlobalSetting.objects.create(id=0, **settings)

def initialize_bot():
    
    # initialize settings

    settings_path = Path('settings.json')
    if not settings_path.exists() or ask_user('Overwrite settings?'):

        settings = {}
        setting_names = [
            [ 'token',        str ],
            [ 'database_url', str ],
            [ 'status',       str ]
        ]

        try:
            for name in setting_names:
                settings[name[0]] = name[1](input(f'Enter {name[0]}: ').strip())
        except KeyboardInterrupt:
            return

        print('Writing settings')
        with settings_path.open('w') as f:
            json.dump(settings, f, indent=4)

    else:
        with settings_path.open() as f:
            settings = json.load(f)

    # initialize database

    if ask_user('Overwrite DB?'):

        from shaak.database import metadata

        print('Creating tables')
        engine = sqlalchemy.create_engine(settings['database_url'])
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
            [ 'verbose_errors', True ]
        ]
        for name in bool_setting_names:
            settings[name[0]] = ask_user(name[0], name[1])

        settings['secret_key'] = int(secrets.token_bytes(7).hex(), 16)
        
        print('Executing settings')
        asyncio.run(set_global_settings(settings))
