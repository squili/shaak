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

import re
from typing import Optional

import discord
from discord.ext         import commands
from tortoise.exceptions import DoesNotExist

from shaak.base_module import BaseModule
from shaak.checks      import has_privlidged_role_check
from shaak.consts      import ModuleInfo, ResponseLevel
from shaak.errors      import InvalidId
from shaak.helpers     import MentionType, mention2id, id2mention, pluralize, commas
from shaak.models      import PreviewSettings, PreviewFilter, Guild

message_link_regex = re.compile(r'https://(?:\w+\.)?discord(?:app)?.com/channels/\d+/\d+/\d+')

class Previews(BaseModule):
    
    meta = ModuleInfo(
        name='previews',
        settings=PreviewSettings
    )

    async def send_message_preview(self, target_channel: discord.TextChannel, link: str,
                                   checking_user: discord.User, source_guild: discord.Guild) -> int:

        try:
            parts = link.split('/')
            guild_id = int(parts[-3])
            channel_id = int(parts[-2])
            message_id = int(parts[-1])
        except (IndexError, ValueError):
            return 1

        guild = self.bot.get_guild(guild_id)
        if guild == None:
            return 2
        
        if not checking_user in guild.members:
            return 3

        channel = guild.get_channel(channel_id)
        if channel == None:
            return 4
        
        try:
            message = await channel.fetch_message(message_id)
        except (discord.NotFound, discord.Forbidden):
            return 5
        
        embed = discord.Embed(
            description=message.content,
            timestamp=message.created_at
        )
        embed.set_author(
            name=message.author.name + '#' + message.author.discriminator,
            icon_url=message.author.avatar_url
        )
        embed.add_field(name='Channel', value=id2mention(channel_id, MentionType.channel))
        embed.add_field(name='Author', value=id2mention(message.author.id, MentionType.user))
        if source_guild.id != guild.id:
            embed.add_field(name='Guild', value=f'{guild.name} ({guild.id})')

        await target_channel.send(embed=embed)
        if len(message.embeds) > 0:
            for embed in message.embeds:
                await target_channel.send(embed=embed)
        if len(message.attachments) > 0:
            files = []
            for attachment in message.attachments:
                if attachment.size <= 8_388_119:
                    files.append(await attachment.to_file())
            if len(files) > 0:
                await target_channel.send(files=files)
        return 0

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        
        try:
            matches = message_link_regex.findall(message.content)
            if matches:
                if not await PreviewFilter.filter(channel_id=message.channel.id).exists():
                    return

                module_settings: PreviewSettings = await PreviewSettings.get(guild_id=message.guild.id)
                log_channel = None
                if module_settings.log_channel:
                    log_channel = self.bot.get_channel(module_settings.log_channel)
                
                for match in matches:
                    await self.send_message_preview(log_channel or message.channel, match, message.author, message.guild)
        except Exception as e:
            await self.utils.log_background_error(item.guild, e)
    
    @commands.command('pv.view')
    async def pv_view(self, ctx: commands.Context, link: str):

        err = await self.send_message_preview(ctx.channel, link, ctx.author, ctx.guild)
        if   err == 1:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Malformed message link')
        elif err == 2:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Guild not found')
        elif err == 3:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'You are not in that guild')
        elif err == 4:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Channel not found')
        elif err == 5:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Message not found')
    
    @commands.command('pv.add')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def pv_add(self, ctx: commands.Context, *channels: str):

        channel_ids = set()
        malformed = 0
        for channel_reference in channels:
            try:
                channel_id = int(channel_reference)
            except ValueError:
                try:
                    channel_id = mention2id(channel_reference, MentionType.channel)
                except InvalidId:
                    malformed += 1
                    continue
            channel_ids.add(channel_id)

        additions = 0
        duplicates = 0
        for channel_id in channel_ids:
            try:
                await PreviewFilter.get(guild_id=ctx.guild.id, channel_id=channel_id)
            except DoesNotExist:
                await PreviewFilter.create(guild_id=ctx.guild.id, channel_id=channel_id)
                additions += 1
            else:
                duplicates += 1
        
        if duplicates or malformed:
            message_parts = []
            if additions:
                message_parts.append(f'added {additions} new channel{pluralize("", "s", additions)}')
            if malformed:
                message_parts.append(f'skipped {malformed} malformed channel{pluralize("", "s", malformed)}')
            if duplicates:
                message_parts.append(f'ignored {duplicates} duplicate channel{pluralize("", "s", duplicates)}')
            await self.utils.respond(ctx, ResponseLevel.success, commas(message_parts).capitalize() + '.')
        else:
            await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command('pv.remove')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def pv_remove(self, ctx: commands.Context, *channels: str):

        channel_ids = set()
        malformed = 0
        for channel_reference in channels:
            try:
                channel_id = int(channel_reference)
            except ValueError:
                try:
                    channel_id = mention2id(channel_reference, MentionType.channel)
                except InvalidId:
                    malformed += 1
                    continue
            channel_ids.add(channel_id)
        
        db_guild = await Guild.get(id=ctx.guild.id)

        deletions = 0
        nonexistant = 0
        for channel_id in channel_ids:
            try:
                await PreviewFilter.filter(guild=db_guild, channel_id=channel_id).delete()
            except DoesNotExist:
                nonexistant += 1
            else:
                deletions += 1
        
        if nonexistant or malformed:
            message_parts = []
            if deletions:
                message_parts.append(f'removed {deletions} channel{pluralize("", "s", deletions)}')
            if malformed:
                message_parts.append(f'ignored {malformed} malformed channel{pluralize("", "s", malformed)}')
            if nonexistant:
                message_parts.append(f'skipped {nonexistant} nonexistant channel{pluralize("", "s", nonexistant)}')
            await self.utils.respond(ctx, ResponseLevel.success, commas(message_parts).capitalize() + '.')
        else:
            await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command('pv.list')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def pv_list(self, ctx: commands.Context):

        filters = await PreviewFilter.filter(guild_id=ctx.guild.id).only('channel_id').all()
        if len(filters) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No channels found')
            return
        
        await self.utils.list_items(ctx, [
            id2mention(channel.channel_id, MentionType.channel) for channel in filters
        ])
    
    @commands.command(name='pv.log')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def pv_log(self, ctx: commands.Context, channel_reference: Optional[str] = None):

        if channel_reference:
            if channel_reference in ['clear', 'reset', 'disable']:
                await PreviewSettings.filter(guild_id=ctx.guild.id).update(log_channel=None)
            else:
                try:
                    channel_id = int(channel_reference)
                except ValueError:
                    channel_id = mention2id(channel_reference, MentionType.channel)
                await PreviewSettings.filter(guild_id=ctx.guild.id).update(log_channel=channel_id)
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            module_settings: PreviewSettings = await PreviewSettings.filter(guild_id=ctx.guild.id).only('log_channel').get()
            if module_settings.log_channel == None:
                response = 'No log channel set'
            else:
                response = id2mention(module_settings.log_channel, MentionType.channel)
            await self.utils.respond(ctx, ResponseLevel.success, response)