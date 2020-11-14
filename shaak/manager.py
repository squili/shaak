import asyncio, ormar, discord
from typing import Callable, List
from discord.ext import commands
from shaak.consts import ModuleInfo, ResponseLevel, settings_ignore
from shaak.database import Setting, get_setting, new_settings, set_setting
from shaak.helpers import str2bool
from shaak.checks import has_privlidged_role

class Manager(commands.Cog):
    
    def __init__(self, bot: commands.Bot):
        
        self.bot = bot
        self.modules = []
        self.added_cogs = []
        self.initialized = asyncio.Event()
        
        self.utils = bot.get_cog('Utils')
        if self.utils == None:
            raise RuntimeError('Failed getting Utils cog')
    
    def load_module(self, cls):
        
        if not hasattr(cls, 'meta') or not isinstance(cls.meta, ModuleInfo):
            print(f'Invalid module metadata: {cls.__name__}')
            return
        
        print(f'Loading {cls.__name__}')
        loaded_cog = cls(self.bot, self)
        self.bot.add_cog(loaded_cog)
        self.modules.append(cls.meta)
        self.added_cogs.append(loaded_cog)
    
    @commands.Cog.listener()
    async def on_ready(self):
        
        print('Initializing guilds')
        
        for guild in self.bot.guilds:
            try:
                await Setting.objects.get(server_id=guild.id)
            except ormar.NoMatch:
                await new_settings(guild.id)
        
        print('Initializing modules')
        
        for module in self.added_cogs:
            await module.initialize()
        
        self.initialized.set()
        
        print('Shaak initialized!')
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        
        await self.initialized.wait()
        await new_settings(guild.id)
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        
        await self.initialized.wait()
        settings = await Setting.objects.get(server_id=guild.id)
        await settings.delete()
    
    @commands.command('modules.enable')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role())
    async def modules_enable(self, ctx: commands.Context, module_name: str):
        
        for module in self.modules:
            if module.name == module_name:
                modules_enabled = await get_setting(ctx.guild.id, 'enabled_modules')
                await set_setting(ctx.guild.id, 'enabled_modules', modules_enabled | module.flag)
                await self.utils.respond(ctx, ResponseLevel.success)
                break
        else:
            await self.utils.respond(ctx, ResponseLevel.general_error, f'Module `{module_name}` not found')
        
    @commands.command('modules.disable')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role())
    async def modules_disable(self, ctx: commands.Context, module_name: str):
        
        for module in self.modules:
            if module.name == module_name:
                modules_enabled = await get_setting(ctx.guild.id, 'enabled_modules')
                await set_setting(ctx.guild.id, 'enabled_modules', modules_enabled &~ module.flag)
                await self.utils.respond(ctx, ResponseLevel.success)
                break
        else:
            await self.utils.respond(ctx, ResponseLevel.general_error, f'Module `{module_name}` not found')
    
    @commands.command('modules.list')
    async def modules_list(self, ctx: commands.Context):
        
        await self.utils.list_items(ctx, [
            module.name + ': ' + ('enabled' if (await get_setting(ctx.guild.id, 'enabled_modules')) & module.flag else 'disabled') for module in self.modules
        ])
    
    @commands.command('settings.set')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role())
    async def settings_set(self, ctx: commands.Context, setting_name: str, setting_value: str):
        
        if setting_name in settings_ignore:
            await self.utils.respond(ctx, ResponseLevel.forbidden)
        else:
            await set_setting(ctx.guild.id, setting_name, setting_value)
            await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command('settings.get')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role())
    async def settings_get(self, ctx: commands.Context, setting_name: str):
        
        if setting_name in settings_ignore:
            await self.utils.respond(ctx, ResponseLevel.forbidden)
        else:
            setting_value = await get_setting(ctx.guild.id, setting_name, True)
            await self.utils.respond(ctx, ResponseLevel.success, f'{setting_name}: {setting_value}')
    
    @commands.command('settings.reset')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role())
    async def settings_reset(self, ctx: commands.Context, setting_name: str):
        
        if setting_name in settings_ignore:
            await self.utils.respond(ctx, ResponseLevel.forbidden)
        else:
            await set_setting(ctx.guild.id, setting_name, None)
            await self.utils.respond(ctx, ResponseLevel.success)

    @commands.command('settings.list')
    async def settings_list(self, ctx: commands.Context):
        
        settings = await get_setting(ctx.guild.id, '*', False)
        formatted = []
        for i in settings:
            if i not in settings_ignore:
                formatted.append(f'{i}: {"unset" if settings[i] == None else settings[i]}')
        await self.utils.list_items(ctx, formatted)
