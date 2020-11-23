# pylint: disable=unsubscriptable-object # pylint/issues/3882
import dataclasses
import json
from typing import Optional, List

import aredis
import databases
import discord
import ormar
import uuid
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

class WWPingGroup(ormar.Model):
    class Meta(MainMeta):
        tablename = 'ww_ping_groups'
    
    id:       int = ormar.Integer    (primary_key=True)
    guild_id: int = ormar.BigInteger (index=True)
    name:     str = ormar.Text       (allow_blank=False, index=True)

class WWPing(ormar.Model):
    class Meta(MainMeta):
        tablename = 'ww_pings'

    id:                      int = ormar.Integer    (primary_key=True)
    ping_type:               int = ormar.Integer    ()
    target_id:               int = ormar.BigInteger ()
    group: Optional[WWPingGroup] = ormar.ForeignKey (WWPingGroup, related_name='pings')

class WWWatch(ormar.Model):
    class Meta(MainMeta):
        tablename = 'ww_watches'
    
    id:                           int = ormar.Integer    (primary_key=True)
    guild_id:                     int = ormar.BigInteger (index=True)
    pattern:                      str = ormar.Text       (index=True)
    match_type:                   int = ormar.Integer    ()
    ping_group: Optional[WWPingGroup] = ormar.ForeignKey (WWPingGroup, related_name='watches')
    auto_delete:                 bool = ormar.Boolean    ()
    ignore_case:                 bool = ormar.Boolean    ()

class BanEvent(ormar.Model):
    class Meta(MainMeta):
        tablename = 'ban_events'

    id:        uuid.UUID = ormar.UUID       (primary_key=True, unique=True)
    guild_id:        int = ormar.BigInteger (index=True)
    message_id:      int = ormar.BigInteger ()
    message_channel: int = ormar.BigInteger ()
    target_id:       int = ormar.BigInteger ()
    banner_id:       int = ormar.BigInteger (nullable=True)
    ban_reason:      str = ormar.Text       ()
    reported:       bool = ormar.Boolean    (default=False)
    unbanned:       bool = ormar.Boolean    (default=False)

async def start_database():
    
    await database.connect()

async def get_command_prefix(bot: commands.Bot, message: discord.Message) -> str:
    
    await bot.manager_ready.wait()
    if message.guild != None:
        server_settings: Setting = await Setting.objects.get(server_id=message.guild.id)
        if server_settings.command_prefix:
            return server_settings.command_prefix
    global_settings: GlobalSetting = await GlobalSetting.objects.get(id=0)
    return global_settings.command_prefix
