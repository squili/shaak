# pylint: disable=unsubscriptable-object # pylint/issues/3637
import dataclasses
import json

import aredis
import databases
import discord
import ormar
import pydantic
import sqlalchemy
from discord.ext import commands

from shaak.settings import app_settings

database = databases.Database(app_settings.database_url)
metadata = sqlalchemy.MetaData()
redis = aredis.StrictRedis(
                host = app_settings.redis_host,
                port = app_settings.redis_port,
                  db = app_settings.redis_db,
    decode_responses = True
)

class MainMeta(ormar.ModelMeta):
    metadata = metadata
    database = database

class GlobalSetting(ormar.Model):
    class Meta(MainMeta):
        tablename = 'global_settings'

    # only allow one entry
    id:              int = ormar.Integer    (primary_key=True, unique=True, minimum=0, maximum=0)

    # defaults
    command_prefix:  str = ormar.Text       ()
    verbose_errors: bool = ormar.Boolean    ()

    # misc
    secret_key:      int = ormar.BigInteger ()
    status:          str = ormar.Text       ()

class Setting(ormar.Model):
    class Meta(MainMeta):
        tablename = 'settings'
    
    # internal
    server_id:          int = ormar.BigInteger (primary_key=True, autoincrement=False, unique=True)
    enabled_modules:    int = ormar.Integer    (default=0b0)
    
    # general
    command_prefix:     str = ormar.Text       (nullable=True)
    verbose_errors:    bool = ormar.Boolean    (nullable=True)
    authenticated_role: int = ormar.BigInteger (nullable=True)
    
    # word watch
    ww_log_channel:     int = ormar.BigInteger (nullable=True)
    ww_exemptions:      str = ormar.Text       (default='')

class SusWord(ormar.Model):
    class Meta(MainMeta):
        tablename = 'sus_words'
    
    id:          int           = ormar.Integer    (primary_key=True)
    server_id:   int           = ormar.BigInteger (index=True)
    regex:       str           = ormar.Text       ()
    auto_delete: bool          = ormar.Boolean    ()

async def start_database():
    
    await database.connect()

async def get_command_prefix(bot: commands.Bot, message: discord.Message) -> str:
    
    await bot.manager_ready.wait()
    server_settings: Setting = await Setting.objects.get(server_id=message.guild.id)
    if server_settings.command_prefix:
        return server_settings.command_prefix
    else:
        global_settings: GlobalSetting = await GlobalSetting.objects.get(id=0)
        return global_settings.command_prefix
