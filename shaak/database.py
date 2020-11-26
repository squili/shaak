# pylint: disable=unsubscriptable-object # pylint/issues/3882
import dataclasses
import json
from datetime import datetime
from typing import Optional, List

import databases
import discord
import ormar
import uuid
import sqlalchemy
from discord.ext import commands

from shaak.settings import app_settings

database = databases.Database(app_settings.database_url)
metadata = sqlalchemy.MetaData()

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

class DBGuild(ormar.Model):
    class Meta(MainMeta):
        tablename = 'guilds'
    
    id:             int = ormar.BigInteger (primary_key=True, autoincrement=False, unique=False)
    delete_at: datetime = ormar.DateTime(nullable=True, default=None)

class Setting(ormar.Model):
    class Meta(MainMeta):
        tablename = 'settings'
    
    id:                  int = ormar.Integer    (primary_key=True)
    guild: Optional[DBGuild] = ormar.ForeignKey (DBGuild, related_name='settings', ondelete='CASCADE')
    command_prefix:      str = ormar.Text       (nullable=True)
    verbose_errors:     bool = ormar.Boolean    (nullable=True)
    authenticated_role:  int = ormar.BigInteger (nullable=True)

class WWSetting(ormar.Model):
    class Meta(MainMeta):
        tablename = 'ww_settings'
    
    id:                  int = ormar.Integer    (primary_key=True)
    guild: Optional[DBGuild] = ormar.ForeignKey (DBGuild, related_name='ww_settings', ondelete='CASCADE')
    enabled:            bool = ormar.Boolean    (default=False)
    log_channel:         int = ormar.BigInteger (nullable=True)
    header:              str = ormar.Text       (nullable=True)

class WWPingGroup(ormar.Model):
    class Meta(MainMeta):
        tablename = 'ww_ping_groups'
    
    id:                  int = ormar.Integer    (primary_key=True)
    guild: Optional[DBGuild] = ormar.ForeignKey (DBGuild, related_name='ww_ping_groups', ondelete='CASCADE')
    name:                str = ormar.Text       (allow_blank=False, index=True)

class WWPing(ormar.Model):
    class Meta(MainMeta):
        tablename = 'ww_pings'

    id:                      int = ormar.Integer    (primary_key=True)
    ping_type:               str = ormar.String     (max_length=2)
    target_id:               int = ormar.BigInteger ()
    group: Optional[WWPingGroup] = ormar.ForeignKey (WWPingGroup, related_name='ww_pings', ondelete='CASCADE')

class WWWatch(ormar.Model):
    class Meta(MainMeta):
        tablename = 'ww_watches'
    
    id:                           int = ormar.Integer    (primary_key=True)
    guild:          Optional[DBGuild] = ormar.ForeignKey (DBGuild, related_name='ww_watches', ondelete='CASCADE')
    pattern:                      str = ormar.Text       (index=True)
    match_type:                   int = ormar.Integer    ()
    ping_group: Optional[WWPingGroup] = ormar.ForeignKey (WWPingGroup, related_name='ww_watches', ondelete='SET NULL')
    auto_delete:                 bool = ormar.Boolean    ()
    ignore_case:                 bool = ormar.Boolean    ()

class WWIgnore(ormar.Model):
    class Meta(MainMeta):
        tablename = 'ww_ignores'
    
    id:                  int = ormar.Integer    (primary_key=True)
    guild: Optional[DBGuild] = ormar.ForeignKey (DBGuild, related_name='ww_ignores', ondelete='CASCADE')
    target_id:           int = ormar.BigInteger (index=True, unqiue=True)
    mention_type:        str = ormar.String     (max_length=2)

class PVSetting(ormar.Model):
    class Meta(MainMeta):
        tablename = 'pv_settings'
    
    id:                    int = ormar.Integer    (primary_key=True)
    guild:   Optional[DBGuild] = ormar.ForeignKey (DBGuild, related_name='pv_settings', ondelete='CASCADE')
    enabled:              bool = ormar.Boolean    (default=False)
    log_channel: Optional[int] = ormar.BigInteger (nullable=True)

class PVFilter(ormar.Model):
    class Meta(MainMeta):
        tablename = 'pv_filter'
    
    id:                  int = ormar.Integer    (primary_key=True)
    guild: Optional[DBGuild] = ormar.ForeignKey (DBGuild, related_name='pv_filters', ondelete='CASCADE')
    channel_id:          int = ormar.BigInteger (unique=True)

class BUEvent(ormar.Model):
    class Meta(MainMeta):
        tablename = 'bu_events'

    id:            uuid.UUID = ormar.UUID       (primary_key=True, unique=True)
    guild: Optional[DBGuild] = ormar.ForeignKey (DBGuild, related_name='bu_events', ondelete='CASCADE')
    message_id:          int = ormar.BigInteger ()
    message_channel:     int = ormar.BigInteger ()
    target_id:           int = ormar.BigInteger ()
    banner_id:           int = ormar.BigInteger (nullable=True)
    ban_reason:          str = ormar.Text       ()
    reported:           bool = ormar.Boolean    (default=False)
    unbanned:           bool = ormar.Boolean    (default=False)

async def start_database():
    
    await database.connect()

async def get_command_prefix(bot: commands.Bot, message: discord.Message) -> str:
    
    await bot.manager_ready.wait()
    if message.guild != None:
        guild_settings: Setting = await Setting.objects.get(guild__id=message.guild.id)
        if guild_settings.command_prefix:
            return guild_settings.command_prefix
    global_settings: GlobalSetting = await GlobalSetting.objects.get(id=0)
    return global_settings.command_prefix
