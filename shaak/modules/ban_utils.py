import discord
from discord.ext import commands

from shaak.base_module import BaseModule
from shaak.consts import ModuleInfo, ResponseLevel
from shaak.database import redis

class BanUtils(BaseModule):
    
    meta = ModuleInfo(
        name='ban_utils',
        flag=0b01
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    async def initialize(self):
        await super().initialize()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        
        await self.initialized.wait()
        
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        
        await self.initialized.wait()
        await redis.delete(self.redis_key(guild.id, 'subs'))