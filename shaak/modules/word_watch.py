import re

import discord
import ormar
from discord.ext import commands
from shaak.base_module import BaseModule
from shaak.checks import has_privlidged_role
from shaak.consts import ModuleInfo
from shaak.database import SusWord, Setting
from shaak.helpers import link_to_message
from shaak.utils import ResponseLevel, Utils

class WordWatch(BaseModule):
    
    meta = ModuleInfo(
        name='word_watch',
        flag=0b1
    )
    
    def __init__(self, *args, **kwargs):
        
        self.word_cache = {}
        
        super().__init__(*args, **kwargs)

        self.bot.add_on_error_hooks(self.after_invoke_hook)
    
    async def initialize(self):
        
        for guild in self.bot.guilds:
            self.word_cache[guild.id] = []
        
        for sus in await SusWord.objects.all():
            if sus.server_id not in self.word_cache:
                await sus.delete()
            else:
                self.word_cache[sus.server_id].append((sus.id, re.compile(sus.regex), sus.auto_delete))
        
        await super().initialize()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        
        await self.initialized.wait()
        
        if guild.id not in self.word_cache:
            self.word_cache[guild.id] = []
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        
        await self.initialized.wait()
        
        if guild.id in self.word_cache:
            for sus in self.word_cache[guild.id]:
                await sus.delete()
            del self.word_cache[guild.id]
    
    async def scan_message(self, message: discord.Message):
        
        await self.initialized.wait()

        server_settings: Setting = await Setting.objects.get(server_id=message.guild.id)
        if str(message.channel.id) in server_settings.ww_exemptions.split(','):
            return
        
        stop = False
        for sus in self.word_cache[message.guild.id]:
            if (match := sus[1].search(message.content)):
                if sus[2]:
                    await message.delete()
                    stop = True
                    
                log_channel_id = server_settings.ww_log_channel
                if log_channel_id == None:
                    return
                    
                log_channel = self.bot.get_channel(log_channel_id)
                if log_channel == None:
                    return
                
                message_embed = discord.Embed(
                    color=discord.Color(0xd22513),
                    description=f'{message.content}\n\n{link_to_message(message)}'
                )
                message_embed.set_author(
                    name=f'{message.author.name}#{message.author.discriminator} ({message.author.id}) triggered /{match.group(0)}/',
                    icon_url=message.author.avatar_url
                )
                await log_channel.send(embed=message_embed)
            if stop: break

    async def after_invoke_hook(self, ctx: commands.Context):

        await self.scan_message(ctx.message)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.author == self.bot.user:
            return

        server_prefix = await self.bot.command_prefix(self.bot, message)
        if not message.content.startswith(server_prefix):
            await self.scan_message(message)

    async def add_to_watch(self, server_id: int, regex: str, auto_delete: bool):

        added = await SusWord.objects.create(server_id=server_id, regex=regex, auto_delete=auto_delete)
        self.word_cache[server_id].append((added.id, re.compile(regex), auto_delete))

    @commands.command(name='ww.watch')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role())
    async def ww_watch(self, ctx: commands.Context, *regexes: str):

        for regex in regexes:
            await self.add_to_watch(ctx.guild.id, regex, False)
            await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command(name='ww.censor')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role())
    async def ww_censor(self, ctx: commands.Context, *regexes: str):

        for regex in regexes:
            await self.add_to_watch(ctx.guild.id, regex, True)
            await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command(name='ww.list')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role())
    async def ww_list(self, ctx: commands.Context):
        
        suses = self.word_cache[ctx.guild.id]
        if len(suses) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No words found')
            return
        
        await self.utils.list_items(ctx, [
            f'{sus[0]}: {sus[1].pattern}' for sus in suses
        ])
    
    @commands.command(name='ww.remove')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role())
    async def ww_remove(self, ctx: commands.Context, id: int):
    
        try:
            sus = await SusWord.objects.get(server_id=ctx.guild.id, id=id)
        except ormar.NoMatch:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Not found')
            return
            
        if sus.server_id == ctx.guild.id:
            await sus.delete()
            for index, item in enumerate(self.word_cache[ctx.guild.id]):
                if item[0] == id:
                    del self.word_cache[ctx.guild.id][index]
                    await self.utils.respond(ctx, ResponseLevel.success)
                    break
        else:
            await self.utils.respond(ctx, ResponseLevel.forbidden, 'You do not have permission to delete this word')
    
    @commands.command(name='ww.qremove')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role())
    async def ww_qremove(self, ctx: commands.Context, pattern: str):
    
        try:
            sus = await SusWord.objects.get(server_id=ctx.guild.id, regex=pattern)
        except ormar.NoMatch:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Not found')
            return
            
        if sus.server_id == ctx.guild.id:
            await sus.delete()
            for index, item in enumerate(self.word_cache[ctx.guild.id]):
                if item[1].pattern == pattern:
                    del self.word_cache[ctx.guild.id][index]
                    await self.utils.respond(ctx, ResponseLevel.success)
                    break
        else:
            await self.utils.respond(ctx, ResponseLevel.forbidden, 'You do not have permission to delete this word')

    @commands.command(name='ww.ignore')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role())
    async def ww_ignore(self, ctx: commands.Context, channel_id: str):
        
        server_settings: Setting = await Setting.objects.get(server_id=ctx.guild.id)
        exemptions = server_settings.ww_exemptions.split(',')
        exemptions = set([i for i in exemptions if i])
        exemptions.add(channel_id)
        await server_settings.update(ww_exemptions=','.join(exemptions))
        await self.utils.respond(ctx, ResponseLevel.success)

    @commands.command(name='ww.ignored')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role())
    async def ww_ignored(self, ctx: commands.Context):
        
        server_settings: Setting = await Setting.objects.get(server_id=ctx.guild.id)
        exemptions = server_settings.ww_exemptions.split(',')
        if len(exemptions) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No words found')
            return
        await self.utils.list_items(ctx, exemptions)
    
    @commands.command(name='ww.unignore')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role())
    async def ww_unignore(self, ctx: commands.Context, channel_id: str):
        
        server_settings: Setting = await Setting.objects.get(server_id=ctx.guild.id)
        exemptions = server_settings.ww_exemptions.split(',')
        exemptions = set((i for i in exemptions if i and i != channel_id))
        await server_settings.update(ww_exemptions=','.join(exemptions))
        await self.utils.respond(ctx, ResponseLevel.success)
