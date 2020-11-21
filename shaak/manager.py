import asyncio
from typing import Callable, List, Dict

import discord
import ormar
from discord.ext import commands

from shaak.checks import has_privlidged_role
from shaak.consts import ModuleInfo, ResponseLevel, setting_structure
from shaak.database import Setting, redis
from shaak.settings import app_settings
from shaak.custom_bot import CustomBot
from shaak.helpers import redis_key

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
            print(f'Invalid module metadata: {cls.__name__}')
            return
        
        loaded_cog = cls(self.bot)
        self.bot.add_cog(loaded_cog)
        self.modules[cls.meta.name] = cls.meta
        self.added_cogs.append(loaded_cog)

    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role())
    async def cog_check(self, ctx: commands.Context):

        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        
        return True
    
    @commands.Cog.listener()
    async def on_ready(self):

        print('Initializing guilds')
        
        for guild in self.bot.guilds:
            await Setting.objects.get_or_create(server_id=guild.id)
        
        print('Initializing modules')
        
        for module in self.added_cogs:
            await module.initialize()

        print('Finishing up')

        await self.bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=app_settings.status
            )
        )
        
        self.bot.manager_ready.set()
        
        print('Shaak initialized!')
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        
        await self.bot.manager_ready.wait()

        # create settings
        await Setting.objects.get_or_create(server_id=guild.id)
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        
        await self.bot.manager_ready.wait()

        # delete settings
        try:
            settings: Setting = await Setting.objects.get(server_id=guild.id)
            await settings.delete()
        except ormar.NoMatch:
            pass

        # delete redis entries
        keys = await redis.scan_iter(redis_key('*', guild.id, '*'))
        if len(keys) > 0:
            await redis.delete(keys)
    
    @commands.command('modules.enable')
    async def modules_enable(self, ctx: commands.Context, module_name: str):
        
        if module_name in self.modules:
            server_settings: Setting = await Setting.objects.get(server_id=ctx.guild.id)
            await server_settings.update(enabled_modules=server_settings.enabled_modules | self.modules[module_name].flag)
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            await self.utils.respond(ctx, ResponseLevel.general_error, f'Module `{module_name}` not found')
        
    @commands.command('modules.disable')
    async def modules_disable(self, ctx: commands.Context, module_name: str):
        
        if module_name in self.modules:
            server_settings: Setting = await Setting.objects.get(server_id=ctx.guild.id)
            await server_settings.update(enabled_modules=server_settings.enabled_modules &~ self.modules[module_name].flag)
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            await self.utils.respond(ctx, ResponseLevel.general_error, f'Module `{module_name}` not found')
    
    @commands.command('modules.list')
    async def modules_list(self, ctx: commands.Context):
        
        entries = []
        server_settings: Setting = await Setting.objects.get(server_id=ctx.guild.id)
        for module in self.modules.values():
            entries.append(f"{module.name}: {'enabled' if server_settings.enabled_modules & module.flag else 'disabled'}")

        await self.utils.list_items(ctx, entries)
    
    @commands.command('settings.set')
    async def settings_set(self, ctx: commands.Context, setting_name: str, *args):

        setting_value = ' '.join(args) or None

        if setting_name in setting_structure:
            server_settings: Setting = await Setting.objects.get(server_id=ctx.guild.id)
            if setting_value != None:
                setting_value = setting_structure[setting_name][0](setting_value)
            await server_settings.update(**{setting_name: setting_value})
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Invalid setting name')

    @commands.command('settings.list')
    async def settings_list(self, ctx: commands.Context):
        
        server_settings: Setting = await Setting.objects.get(server_id=ctx.guild.id)
        formatted = []
        for i in server_settings.dict().items():
            if i[0] in setting_structure:
                formatted.append(f'{i[0]}: {"unset" if i[1] == None else setting_structure[i[0]][1](i[1])}')
        await self.utils.list_items(ctx, formatted)
