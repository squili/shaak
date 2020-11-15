import asyncio

from discord.ext import commands

from shaak.consts import ModuleInfo, ResponseLevel
from shaak.database import Setting
from shaak.helpers import redis_key
from shaak.custom_bot import CustomBot
from shaak.errors import ModuleDisabled

class BaseModule(commands.Cog):
    
    meta = ModuleInfo(
        name='base_module',
        flag=0b0
    )

    def __init__(self, bot: CustomBot):
        
        self.bot     = bot
        self.utils   = bot.get_cog('Utils')
        if self.utils == None:
            raise RuntimeError('Failed getting Utils cog')
        self.initialized = asyncio.Event()
    
    def redis_key(self, *args):
        return redis_key(self.meta.name, *args)
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        
        if isinstance(error, ModuleDisabled):
            await self.utils.respond(ctx, ResponseLevel.module_disabled, f'Module {type(self).meta.name} disabled!')
    
    async def cog_check(self, ctx: commands.Context):
        
        await self.bot.manager_ready.wait()
        await self.initialized.wait()

        server_settings: Setting = await Setting.objects.get(server_id=ctx.guild.id)
        if server_settings.enabled_modules & self.meta.flag:
            return True
        else:
            raise ModuleDisabled()
    
    async def initialize(self):
        
        self.initialized.set()
