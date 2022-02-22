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

import logging
from typing import Dict, Optional

import discord
from discord     import Embed
from discord.ext import commands

from shaak.checks     import has_privlidged_role_check
from shaak.consts     import ModuleInfo, ResponseLevel, setting_structure
from shaak.models     import Guild, GuildSettings
from shaak.settings   import app_settings
from shaak.custom_bot import CustomBot

logger = logging.getLogger('shaak_manager')

class Manager(commands.Cog):

    def __init__(self, bot: CustomBot):
        
        self.bot = bot
        self.modules: Dict[str, ModuleInfo] = {}
        self.added_cogs = []
        
        self.utils = bot.get_cog('Utils')
        if self.utils == None:
            raise RuntimeError('Failed getting Utils cog')
    
    def load_module(self, cls):
        
        if not hasattr(cls, 'meta') or not isinstance(cls.meta, ModuleInfo):
            logger.warn(f'Invalid module metadata: {cls.__name__}')
            return
        
        loaded_cog = cls(self.bot)
        self.bot.add_cog(loaded_cog)
        self.modules[cls.meta.name] = cls.meta
        self.added_cogs.append(loaded_cog)

    async def cog_check(self, ctx: commands.Context):

        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        
        return True
    
    async def max_guilds_check(self, guild: discord.Guild):
        if guild.member_count <= 10:
            await guild.leave()
            embed = Embed(description='Shaak is currently not allowed in server with 10 or less members. You can join [the support server](https://discord.gg/SWMKshyutT) to learn when this restriction will be lifted.')
            embed.set_footer(text=f'You are receiving this message because you own the server {guild.name}')
            dm_channel = guild.owner.dm_channel
            if dm_channel == None:
                dm_channel = await guild.owner.create_dm()
            await dm_channel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_ready(self):
        
        if app_settings.max_guilds:
            logger.info('Ensuring guild member counts')
            for guild in self.bot.guilds:
                await self.max_guilds_check(guild)

        if self.bot.manager_ready.is_set():
            return # reconnects trigger on_ready as well

        logger.info('Initializing guilds')

        curr_ids = set()
        for guild in self.bot.guilds:
            curr_ids.add(guild.id)

            # initialize db
            await Guild.get_or_create(id=guild.id)
            await GuildSettings.get_or_create(guild_id=guild.id)
        
            # create module settings
            for module in self.modules.values():
                if module.settings != None:
                    await module.settings.get_or_create(guild_id=guild.id)
        
        for db_guild in await Guild.all():
            if db_guild.id not in curr_ids:
                await db_guild.delete()
        
        logger.info('Initializing modules')
        
        for module in self.added_cogs:
            await module.initialize()
        del self.added_cogs

        await self.bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=app_settings.status
            )
        )
        
        self.bot.manager_ready.set()
        
        logger.info('Manager initialized')
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        
        if app_settings.max_guilds:
            await self.max_guilds_check(guild)
            
        await self.bot.manager_ready.wait()

        logger.info(f'Added to guild {guild.name} ({guild.id})')

        # initialize database
        await Guild.get_or_create(id=guild.id)
        await GuildSettings.get_or_create(guild_id=guild.id)
        
        # create module settings
        for module in self.modules.values():
            if module.settings != None:
                await module.settings.get_or_create(guild_id=guild.id)
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        
        await self.bot.manager_ready.wait()

        logger.info(f'Removed from guild {guild.name} ({guild.id})')

    @commands.command('modules.enable')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def modules_enable(self, ctx: commands.Context, module_name: str):

        if module_name in self.modules:
            await self.modules[module_name].settings.filter(guild_id=ctx.guild.id).update(enabled=True)
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            await self.utils.respond(ctx, ResponseLevel.general_error, f'Module `{module_name}` not found')
        
    @commands.command('modules.disable')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def modules_disable(self, ctx: commands.Context, module_name: str):

        if module_name in self.modules:
            await self.modules[module_name].settings.filter(guild_id=ctx.guild.id).update(enabled=False)
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            await self.utils.respond(ctx, ResponseLevel.general_error, f'Module `{module_name}` not found')
    
    @commands.command('modules.list')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def modules_list(self, ctx: commands.Context):

        entries = []
        for module in self.modules.values():
            entries.append(f"{module.name}: {'enabled' if (await module.settings.get(guild_id=ctx.guild.id)).enabled else 'disabled'}")

        await self.utils.list_items(ctx, entries)
    
    @commands.command('settings.set')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def settings_set(self, ctx: commands.Context, setting_name: str, *, setting_value: Optional[str]):

        if setting_name in setting_structure:
            if setting_value != None:
                setting_value = setting_structure[setting_name][0](setting_value)
            await GuildSettings.filter(guild_id=ctx.guild.id).update(**{setting_name: setting_value})
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Invalid setting name')

    @commands.command('settings.list')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def settings_list(self, ctx: commands.Context):

        guild_settings = await GuildSettings.get(guild_id=ctx.guild.id)
        formatted = []
        for name, converter in setting_structure.items():
            value = getattr(guild_settings, name, None)
            formatted.append(f'{name}: {"unset" if value == None else converter[1](value)}')
        await self.utils.list_items(ctx, formatted)
