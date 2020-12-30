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

import time
from typing import Dict, Set, Optional

import discord
from discord.ext import commands
from tortoise.exceptions import DoesNotExist

from shaak.base_module import BaseModule
from shaak.consts      import ModuleInfo, ResponseLevel, MentionType
from shaak.checks      import has_privlidged_role_check
from shaak.helpers     import get_or_create, time_ms, link_to_message, mention2id, id2mention
from shaak.models      import UserWatchSettings, UserWatchWatch

class UserWatch(BaseModule):

    meta = ModuleInfo(
        name='user_watch',
        settings=UserWatchSettings
    )

    def __init__(self, *args, **kwargs):
        
        super().__init__(*args, **kwargs)

        self.last_report_time: Dict[int, Dict[int]] = {}
        self.user_watch_cache: Dict[int, Set[int]] = {}
        self.watch_cooldown_cache: Dict[int, int] = {}
    
    async def initialize(self):

        for guild in self.bot.guilds:
            self.last_report_time[guild.id] = {}
            self.user_watch_cache[guild.id] = set()
        
        for watch in await UserWatchWatch.all():
            if watch.guild_id not in self.user_watch_cache:
                continue
            self.user_watch_cache[watch.guild_id].add(watch.user_id)

        await super().initialize()
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):

        self.last_report_time[guild.id] = {}
        self.user_watch_cache[guild.id] = set()

    def is_user_watched(self, guild_id: int, user_id: int) -> bool:

        return user_id in get_or_create(self.user_watch_cache, guild_id, set())
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if self.is_user_watched(message.guild.id, message.author.id):

            module_settings = None
            if message.guild.id not in self.watch_cooldown_cache:
                module_settings = await UserWatchSettings.get(guild_id=message.guild.id)
                self.watch_cooldown_cache[message.guild.id] = module_settings.cooldown_time
            
            if time_ms() - get_or_create(self.last_report_time[message.guild.id], message.author.id, 0) > self.watch_cooldown_cache[message.guild.id]:
                
                if module_settings == None:
                    module_settings = await UserWatchSettings.get(guild_id=message.guild.id)
                
                log_channel = self.bot.get_channel(module_settings.log_channel)
                if log_channel != None:
        
                    embed = discord.Embed(
                        description=f'{message.content}\nJump to message: {link_to_message(message)}',
                        timestamp=message.created_at
                    )
                    embed.set_author(
                        name=f'Watched user {message.author.name}#{message.author.discriminator} sent a message!',
                        icon_url=message.author.avatar_url
                    )
                    embed.add_field(name='Channel', value=id2mention(message.channel.id, MentionType.channel))
                    embed.add_field(name='Author', value=id2mention(message.author.id, MentionType.user))

                    if len(message.attachments) > 0:
                        for attachment in message.attachments:
                            if attachment.height != None and attachment.width != None: # only images have these fields filled
                                embed.set_image(url=attachment.url or attachment.proxy_url)

                    await log_channel.send(embed=embed)
            
            self.last_report_time[message.guild.id][message.author.id] = time_ms()
    
    @commands.command(name='uw.log')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def uw_log(self, ctx: commands.Context, channel_reference: Optional[str] = None):

        if channel_reference:
            if channel_reference in ['clear', 'reset', 'disable']:
                await UserWatchSettings.filter(guild_id=ctx.guild.id).update(log_channel=None)
            else:
                try:
                    channel_id = int(channel_reference)
                except ValueError:
                    channel_id = mention2id(channel_reference, MentionType.channel)
                await UserWatchSettings.filter(guild_id=ctx.guild.id).update(log_channel=channel_id)
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            module_settings: UserWatchSettings = await UserWatchSettings.filter(guild_id=ctx.guild.id).only('log_channel').get()
            if module_settings.log_channel == None:
                response = 'No log channel set'
            else:
                response = id2mention(module_settings.log_channel, MentionType.channel)
            await self.utils.respond(ctx, ResponseLevel.success, response)
    
    @commands.command(name='uw.cooldown')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def uw_cooldown(self, ctx: commands.Context, cooldown: Optional[str] = None):

        if cooldown:
            if cooldown in ['clear', 'reset', 'disable']:
                await UserWatchSettings.filter(guild_id=ctx.guild.id).update(cooldown_time=900000)
            else:
                try:
                    cooldown_time = int(cooldown)
                except ValueError:
                    await self.utils.respond(ctx, ResponseLevel.general_error, 'Invalid cooldown')
                    return
                if cooldown_time > (2**32):
                    await self.utils.respond(ctx, ResponseLevel.general_error, 'Cooldown too long')
                    return
                await UserWatchSettings.filter(guild_id=ctx.guild.id).update(cooldown_time=cooldown_time)
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            module_settings: UserWatchSettings = await UserWatchSettings.filter(guild_id=ctx.guild.id).only('cooldown_time').get()
            await self.utils.respond(ctx, ResponseLevel.success, f'{module_settings.cooldown_time}ms')
    
    @commands.command(name='uw.watch')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def uw_watch(self, ctx: commands.Context, target_user: str):

        try:
            target_id = int(target_user)
        except ValueError:
            target_id = mention2id(target_user, MentionType.user)

        if target_id in get_or_create(self.user_watch_cache, ctx.guild.id, set()):
            await self.utils.respond(ctx, ResponseLevel.general_error, 'User already watched')
            return
        
        await UserWatchWatch.create(guild_id=ctx.guild.id, user_id=target_id)
        self.user_watch_cache[ctx.guild.id].add(target_id)
        self.last_report_time[ctx.guild.id][target_id] = 0

        await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command(name='uw.unwatch')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def uw_unwatch(self, ctx: commands.Context, target_user: str):

        try:
            target_id = int(target_user)
        except ValueError:
            target_id = mention2id(target_user, MentionType.user)

        await UserWatchWatch.filter(guild_id=ctx.guild.id, user_id=target_id).delete()
        try:
            self.user_watch_cache[ctx.guild.id].remove(target_id)
        except KeyError:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Watch not found')
        else:
            if target_id in self.last_report_time[ctx.guild.id]:
                del self.last_report_time[ctx.guild.id][target_id]
            await self.utils.respond(ctx, ResponseLevel.success)
    