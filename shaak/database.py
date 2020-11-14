# pylint: disable=unsubscriptable-object # pylint/issues/3637
import dataclasses
import json

import databases
import discord
import ormar
import pydantic
import sqlalchemy

from shaak.helpers import str2bool
from shaak.settings import app_settings

database = databases.Database(app_settings.database_url)
metadata = sqlalchemy.MetaData()

class MainMeta(ormar.ModelMeta):
    metadata = metadata
    database = database

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

setting_converters = {
    'verbose_errors':     str2bool,
    'authenticated_role': int,
    'ww_log_channel':     int
}

class SusWord(ormar.Model):
    class Meta(MainMeta):
        tablename = 'sus_words'
    
    id:          int           = ormar.Integer    (primary_key=True)
    server_id:   int           = ormar.BigInteger (index=True)
    regex:       str           = ormar.Text       ()
    auto_delete: bool          = ormar.Boolean    ()

async def new_settings(server_id: int):
    
    return await Setting.objects.get_or_create(server_id=server_id)

async def get_setting(server_id: int, setting_name: str, descend: bool = True):
    
    try:
        server_setting = (await Setting.objects.get(server_id=server_id)).dict()
        setting_value = server_setting.get(setting_name)
    except ormar.NoMatch:
        await new_settings(server_id)
        return await get_setting(server_id, setting_name, descend)
        
    if (server_setting == None or setting_value == None) and descend:
        return await get_setting(0, setting_name, False)
        
    if setting_name == '*':
        if descend:
            return server_setting | await get_setting(0, setting_name, False)
        else:
            return server_setting
    else:
        return setting_value

async def set_setting(server_id: int, setting_name: str, setting_value: str):
    
    if setting_name in setting_converters and setting_value != None:
        setting_value = setting_converters[setting_name](setting_value)
    
    setting_row = await Setting.objects.get_or_create(server_id=server_id)
    await setting_row.update(**{setting_name: setting_value})
    
async def start_database():
    
    await database.connect()

async def get_command_prefix(_, message: discord.Message) -> str:
    
    return await get_setting(message.guild.id, 'command_prefix')
