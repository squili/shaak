# pylint: disable=unsubscriptable-object   # pylint/issues/3637

import uuid
from typing import Union, Optional

import ormar
import discord
from discord.ext import commands

from shaak.base_module import BaseModule
from shaak.consts import ModuleInfo, ResponseLevel, color_red, PseudoId
from shaak.database import redis, BanEvent, Setting
from shaak.helpers import uuid2b64, b642uuid, id2mention, MentionType, check_privildged
from shaak.checks import has_privlidged_role

class BanUtils(BaseModule):
    
    meta = ModuleInfo(
        name='ban_utils',
        flag=0b01
    )
    
    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.extra_check(commands.has_permissions(administrator=True))
        self.extra_check(has_privlidged_role())
    
    async def initialize(self):
        await super().initialize()
    
    async def update_ban_message(self, ban_event: BanEvent):

        guild = self.bot.get_guild(ban_event.guild_id)
        channel = guild.get_channel(ban_event.message_channel)
        if channel == None:
            return
        try:
            message = await channel.fetch_message(ban_event.message_id)
        except (discord.NotFound, discord.Forbidden):
            return
        icon_url = None

        target_user = await self.utils.aggressive_resolve_user(ban_event.target_id)
        if target_user == None:
            title = f'{ban_event.target_id} banned'
        else:
            icon_url = target_user.avatar_url
            title = f'{target_user.name}#{target_user.discriminator} banned'

        if ban_event.banner_id != None:
            banner_user = await self.utils.aggressive_resolve_user(ban_event.banner_id)
            if banner_user == None:
                title += f' by {ban_event.banner_id}'
            else:
                title += f' by {banner_user.name}#{banner_user.discriminator}'
                if icon_url == None:
                    icon_url = banner_user.avatar_url

        if icon_url == None:
            icon_url = guild.icon_url
        
        description_entries = [
            ( 'Reason', ban_event.ban_reason                           ),
            ( '📣',     'Reported' if ban_event.reported else 'Report' ),
            ( '🔄',     'Unbanned' if ban_event.unbanned else 'Unban'  )
        ]

        embed = discord.Embed(
            color=color_red,
            description='\n'.join((f'{i[0]}: {i[1]}' for i in description_entries))
        )
        embed.set_author(name=title, icon_url=icon_url)
        embed.set_footer(text=uuid2b64(ban_event.id))
        await message.edit(embed=embed)
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: Union[discord.Member, discord.User]):

        ban_user_id = None
        async for log_entry in guild.audit_logs(limit=100, action=discord.AuditLogAction.ban):
            if log_entry.target == user:
                ban_user_id = log_entry.user.id
                ban_reason = log_entry.reason
                break
        else: # fallback; shouldn't happen, but it's better to have less functionality than none
            ban_entry = await guild.fetch_ban(user)
            ban_reason = ban_entry.reason
        
        server_settings: Setting = await Setting.objects.get(server_id=guild.id)
        if server_settings.log_channel == None:
            return
        
        new_message = await guild.get_channel(server_settings.log_channel).send(
            embed=discord.Embed(
                color=color_red,
                description='Processing ban...'
            )
        )

        ban_event = await BanEvent.objects.create(
            id=uuid.uuid4(),
            guild_id=guild.id,
            message_id=new_message.id,
            message_channel=server_settings.log_channel,
            target_id=user.id,
            banner_id=ban_user_id,
            ban_reason=ban_reason or 'No reason given'
        )

        await self.update_ban_message(ban_event)

        await new_message.add_reaction('📣')
        await new_message.add_reaction('🔄')

    # we have to use the raw reaction event because rapptz hates me
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        
        if payload.user_id == self.bot.user.id \
            or payload.emoji.is_custom_emoji() \
            or payload.emoji.name not in ['📣', '🔄']:
            return

        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        if message.author != self.bot.user or len(message.embeds) != 1:
            return
        
        embed = message.embeds[0]
        if embed.footer == None or embed.footer.text == None:
            return
        
        event_id = embed.footer.text
        try:
            ban_event = await BanEvent.objects.get(id=b642uuid(event_id))
        except (ValueError, ormar.NoMatch):
            return
        
        user = self.bot.get_user(payload.user_id)
        
        await message.remove_reaction(payload.emoji, user)
        privilidged = await check_privildged(guild, guild.get_member(user.id))
        if privilidged:
            ban_perms = True
            crosspost_perms = True
        else:
            permissions = user.permissions_in(channel)
            ban_perms = permissions.ban_members
            crosspost_perms = permissions.manage_guild

        if payload.emoji.name == '📣' and not ban_event.reported and crosspost_perms:

            # insert crosspost code here
            ban_event.reported = True
            await ban_event.update()
        elif payload.emoji.name == '🔄' and not ban_event.unbanned and ban_perms:

            try:
                await guild.unban(PseudoId(ban_event.target_id))
            except discord.HTTPException as e:
                if e.code == 10026:
                    pass
            ban_event.unbanned = True
            await ban_event.update()
        
        else:
            return
        
        await message.remove_reaction(payload.emoji, self.bot.user)
        await self.update_ban_message(ban_event)
        
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        
        await self.initialized.wait()

        # delete ban events
        await BanEvent.objects.delete(server_id=guild.id)

    # debug
    @commands.command('bu.reload')
    async def reload(self, ctx: commands.Context, event_id: str):

        ban_event = await BanEvent.objects.get(id=b642uuid(event_id))
        await self.update_ban_message(ban_event)