import asyncio

from discord.ext import commands

from shaak.consts import ModuleInfo, ResponseLevel
from shaak.custom_bot import CustomBot
from shaak.errors import ModuleDisabled

class BaseModule(commands.Cog):
    
    meta = ModuleInfo(
        name='base_module',
        settings=None
    )

    def __init__(self, bot: CustomBot):
        
        self.bot          = bot
        self.utils        = bot.get_cog('Utils')
        if self.utils == None:
            raise RuntimeError('Failed getting Utils cog')
        self.initialized = asyncio.Event()
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        
        if ctx.cog != self:
            return

        if isinstance(error, ModuleDisabled):
            await self.utils.respond(ctx, ResponseLevel.module_disabled, f'Module {type(self).meta.name} disabled!')
    
    async def cog_check(self, ctx: commands.Context):

        if ctx.guild is None:
            raise commands.NoPrivateMessage()

        await self.bot.manager_ready.wait()
        await self.initialized.wait()

        module_settings = await self.meta.settings.objects.get(guild__id=ctx.guild.id)
        if module_settings.enabled:
            return True
        else:
            raise ModuleDisabled()
    
    async def initialize(self):
        
        self.initialized.set()
