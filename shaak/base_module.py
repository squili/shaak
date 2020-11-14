import asyncio
from discord.ext import commands
from shaak.consts import ModuleInfo, ResponseLevel
from shaak.database import get_setting
from shaak.manager import Manager

class ModuleDisabled(commands.CheckFailure): pass

class BaseModule(commands.Cog):
    
    meta = ModuleInfo(
        name='base_module',
        flag=0b0
    )

    def __init__(self, bot: commands.Bot, manager: Manager):
        
        self.bot     = bot
        self.manager = manager
        self.utils   = bot.get_cog('Utils')
        if self.utils == None:
            raise RuntimeError('Failed getting Utils cog')
        self.initialized = asyncio.Event()
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        
        if isinstance(error, ModuleDisabled):
            await self.utils.respond(ctx, ResponseLevel.module_disabled, f'Module {type(self).meta.name} disabled!')
    
    async def cog_check(self, ctx: commands.Context):
        
        await self.manager.initialized.wait()
        await self.initialized.wait()
        if await get_setting(ctx.guild.id, 'enabled_modules') & self.meta.flag:
            return True
        else:
            raise ModuleDisabled()
    
    async def initialize(self):
        
        self.initialized.set()