# pylint: disable=unsubscriptable-object   # pylint/issues/3882

import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Optional, Union

import discord
from discord.ext import commands
from tortoise.exceptions import DoesNotExist
from tortoise.transactions import in_transaction

from shaak.base_module import BaseModule
from shaak.checks import has_privlidged_role_check
from shaak.consts import (ModuleInfo, ResponseLevel, bu_invite_timeout,
                          color_red, PseudoId)
from shaak.helpers import MentionType, check_privildged, id2mention, datetime_repr
from shaak.models import (BanUtilBanEvent, BanUtilCrossbanEvent, BanUtilInvite,
                          BanUtilSettings, BanUtilSubscription, GuildSettings)

class BanUtils(BaseModule):
    
    meta = ModuleInfo(
        name='ban_utils',
        settings=BanUtilSettings
    )
    
    def __init__(self, *args, **kwargs):

        self.report_locks: Union[int, asyncio.Lock] = {}

        super().__init__(*args, **kwargs)

    async def initialize(self):

        for guild in self.bot.guilds:
            self.report_locks[guild.id] = asyncio.Lock()

        await super().initialize()
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):

        if guild.id not in self.report_locks:
            self.report_locks[guild.id] = asyncio.Lock()

    @commands.Cog.listener()
    async def on_guild_leave(self, guild: discord.Guild):

        if guild.id in self.report_locks:
            await self.report_locks[guild.id].aquire()
            del self.report_locks[guild.id]

    async def update_ban_message(self, ban_event: BanUtilBanEvent):

        await ban_event.fetch_related('guild')

        guild = self.bot.get_guild(ban_event.guild.id)
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
            ( 'Reason',                                                              ban_event.ban_reason ),
            ( '📣', f'Reported on {datetime_repr(ban_event.reported)}' if ban_event.reported else 'Report' ),
            ( '🔄' if ban_event.banned else '🔨',                   'Unban' if ban_event.banned else 'Ban' )
        ]

        embed = discord.Embed(
            color=color_red,
            description='\n'.join((f'{i[0]}: {i[1]}' for i in description_entries))
        )
        embed.set_author(name=title, icon_url=icon_url)
        await message.edit(embed=embed)
    
    async def update_crossban_message(self, crossban_event: BanUtilCrossbanEvent):

        await crossban_event.fetch_related('event', 'guild')
        await crossban_event.event.fetch_related('guild')

        source_guild = self.bot.get_guild(crossban_event.event.guild.id)
        guild = self.bot.get_guild(crossban_event.guild.id)
        channel = guild.get_channel(crossban_event.message_channel)
        if channel == None:
            return
        try:
            message = await channel.fetch_message(crossban_event.message_id)
        except (discord.NotFound, discord.Forbidden):
            return

        icon_url = source_guild.icon_url
        target_user = await self.utils.aggressive_resolve_user(crossban_event.event.target_id)
        if target_user == None:
            title = f'{crossban_event.event.target_id} banned in {source_guild.name}'
        else:
            title = f'{target_user.name}#{target_user.discriminator} banned in {source_guild.name}'
            if icon_url == None:
                icon_url = target_user.avatar_url

        if crossban_event.event.banner_id != None:
            banner_user = await self.utils.aggressive_resolve_user(crossban_event.event.banner_id)
            if banner_user == None:
                title += f' by {crossban_event.event.banner_id}'
            else:
                title += f' by {banner_user.name}#{banner_user.discriminator}'
                if icon_url == None:
                    icon_url = banner_user.avatar_url
        
        description_entries = [
            ( 'Reason',                                                          crossban_event.event.ban_reason ),
            ( '📣', f'Forwarded on {datetime_repr(crossban_event.reported)}' if crossban_event.reported else 'Forward' ),
            ( '🔄' if crossban_event.banned else '🔨',                'Unban' if crossban_event.banned else 'Ban' )
        ]

        embed = discord.Embed(
            color=color_red,
            description='\n'.join((f'{i[0]}: {i[1]}' for i in description_entries))
        )
        embed.set_author(name=title, icon_url=icon_url)
        await message.edit(embed=embed)
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: Union[discord.Member, discord.User]):

        if await BanUtilBanEvent.filter(guild_id=guild.id, target_id=user.id).exists():
            return

        if await BanUtilCrossbanEvent.filter(guild_id=guild.id, event__target_id=user.id).exists():
            return

        ban_user_id = None
        async for log_entry in guild.audit_logs(limit=100, action=discord.AuditLogAction.ban):
            if log_entry.target == user:
                ban_user_id = log_entry.user.id
                ban_reason = log_entry.reason
                break
        else: # fallback; shouldn't happen, but it's better to have less functionality than none
            ban_entry = await guild.fetch_ban(user)
            ban_reason = ban_entry.reason
        
        module_settings: BanUtilSettings = await BanUtilSettings.get(guild_id=guild.id)

        log_channel = guild.get_channel(module_settings.domestic_log_channel)
        if log_channel == None:
            return

        new_message = await log_channel.send(
            embed=discord.Embed(
                color=discord.Color(0xFFFFFF),
                description='📨'
            )
        )

        async with in_transaction():

            ban_event = await BanUtilBanEvent.create(
                guild_id=guild.id,
                message_id=new_message.id,
                message_channel=module_settings.domestic_log_channel,
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
            or payload.emoji.name not in ['📣', '🔄', '🔨']:
            return

        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        if message.author != self.bot.user or len(message.embeds) != 1:
            return
        
        # we reuse the same code for both event types. get ready for a mess!
        try:
            event = await BanUtilBanEvent.get(message_id=message.id)
        except DoesNotExist:
            try:
                event = await BanUtilCrossbanEvent.get(message_id=message.id).prefetch_related('event')
            except DoesNotExist:
                await message.clear_reactions()
                return
            else:
                is_ban_event = False
        else:
            is_ban_event = True

        user = self.bot.get_user(payload.user_id)
        
        privilidged = await check_privildged(guild, guild.get_member(user.id))
        if privilidged:
            ban_perms = True
            crosspost_perms = True
        else:
            permissions = user.permissions_in(channel)
            ban_perms = permissions.ban_members
            crosspost_perms = permissions.manage_guild

        if payload.emoji.name == '📣' and crosspost_perms:
            await message.add_reaction('📨')

            async with self.report_locks[guild.id]:
                if is_ban_event:
                    ban_event = event
                else:
                    ban_event = event.event

                subscribed: List[BanUtilSubscription] = await BanUtilSubscription.filter(from_guild_id=guild.id).prefetch_related('to_guild').all()
                for subscriber in subscribed:
                    existing_mirrors = await BanUtilCrossbanEvent.filter(event=ban_event, guild=subscriber.to_guild).exists()
                    if not existing_mirrors:
                        module_settings: BanUtilSettings = await BanUtilSettings.get(guild=subscriber.to_guild)
                        if module_settings.foreign_log_channel:

                            target_channel = self.bot.get_channel(module_settings.foreign_log_channel)
                            new_message = await target_channel.send(
                                embed=discord.Embed(
                                    color=discord.Color(0xFFFFFF),
                                    description='📨'
                                )
                            )

                            new_event = await BanUtilCrossbanEvent.create(
                                guild=subscriber.to_guild,
                                event=ban_event,
                                message_id=new_message.id,
                                message_channel=module_settings.foreign_log_channel
                            )

                            await new_message.add_reaction('📣')
                            await new_message.add_reaction('🔨')
                            await self.update_crossban_message(new_event)

                event.reported = datetime.now()
                await event.save(update_fields=['reported'])

            await message.remove_reaction('📨', self.bot.user)
        elif payload.emoji.name == '🔄' and event.banned and ban_perms:

            if is_ban_event:
                ban_event = event
            else:
                ban_event = event.event
            try:
                await guild.unban(PseudoId(ban_event.target_id), reason=f'BanUtils action by {user.id}')
            except discord.HTTPException as e:
                if e.code == 10026:
                    pass
            event.banned = False
            await event.save(update_fields=['banned'])
            await message.remove_reaction(payload.emoji, self.bot.user)
            await message.add_reaction('🔨')
        
        elif payload.emoji.name == '🔨' and not event.banned and ban_perms:

            if is_ban_event:
                ban_event = event
            else:
                ban_event = event.event
            try:
                await guild.ban(PseudoId(ban_event.target_id), reason=f'BanUtils action by {user.id}')
            except discord.HTTPException as e:
                if e.code == 10026:
                    pass
            event.banned = True
            await event.save(update_fields=['banned'])
            await message.remove_reaction(payload.emoji, self.bot.user)
            await message.add_reaction('🔄')
        
        else:
            return
        
        await message.remove_reaction(payload.emoji, user)
        if is_ban_event:
            await self.update_ban_message(event)
        else:
            await self.update_crossban_message(event)
    
    @commands.command('bu.invite')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_invite(self, ctx: commands.Context, target_guild_id: int):

        try:
            await BanUtilSubscription.get(from_guild_id=ctx.guild.id, to_guild_id=target_guild_id)
        except DoesNotExist:
            try:
                await BanUtilInvite.get(from_guild_id=ctx.guild.id, to_guild_id=target_guild_id)
            except DoesNotExist:
                await BanUtilInvite.create(
                    from_guild_id=ctx.guild.id,
                    to_guild_id=target_guild_id
                )
                await self.utils.respond(ctx, ResponseLevel.success)
            else:
                await self.utils.respond(ctx, ResponseLevel.general_error, 'Guild already invited')
        else:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Guild already subscribed')
    
    @commands.command('bu.subscribe')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_subscribe(self, ctx: commands.Context, source_guild_id: int):

        try:
            await BanUtilSubscription.get(
                from_guild_id=source_guild_id,
                to_guild_id=ctx.guild.id
            )
        except DoesNotExist:
            try:
                invite = await BanUtilInvite.get(
                    from_guild_id=source_guild_id,
                    to_guild_id=ctx.guild.id
                )
            except DoesNotExist:
                await self.utils.respond(ctx, ResponseLevel.forbidden, 'That guild has not invited this guild')
            else:
                await invite.delete()
                await BanUtilSubscription.create(
                    from_guild_id=source_guild_id,
                    to_guild_id=ctx.guild.id
                )
                await self.utils.respond(ctx, ResponseLevel.success)
                module_settings: BanUtilSettings = await BanUtilSettings.get(guild_id=ctx.guild.id)
                if module_settings.foreign_log_channel == None:
                    await self.utils.respond(ctx, ResponseLevel.general_error,
                        "WARNING: No foreign event channel set, so you won't receive events from this server!")
        else:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Already subscribed to that guild')
    
    @commands.command('bu.unsubscribe')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_unsubscribe(self, ctx: commands.Context, source_guild_id: int):

        try:
            subscription = await BanUtilSubscription.get(
                from_guild_id=source_guild_id,
                to_guild_id=ctx.guild.id
            )
        except DoesNotExist:
            await self.utils.respond(ctx, ResponseLevel.general_error, f'Not subscribed to guild {source_guild_id}')
        else:
            await subscription.delete()
            await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command('bu.kick')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_kick(self, ctx: commands.Context, target_guild_id: int):

        try:
            subscription = await BanUtilSubscription.get(
                from_guild_id=ctx.guild.id,
                to_guild_id=target_guild_id
            )
        except DoesNotExist:
            try:
                invite = await BanUtilInvite.get(
                    from_guild_id=ctx.guild.id,
                    to_guild_id=target_guild_id
                )
            except DoesNotExist:
                await self.utils.respond(ctx, ResponseLevel.general_error, 'Guild not subscribed or invited')
            else:
                await invite.delete()
                await self.utils.respond(ctx, ResponseLevel.success)
        else:
            await subscription.delete()
            await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command('bu.foreign')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_foreign(self, ctx: commands.Context, log_channel: commands.TextChannelConverter):

        await BanUtilSettings.filter(guild_id=ctx.guild.id).update(foreign_log_channel=log_channel.id)
        await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command('bu.domestic')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_domestic(self, ctx: commands.Context, log_channel: commands.TextChannelConverter):

        await BanUtilSettings.filter(guild_id=ctx.guild.id).update(domestic_log_channel=log_channel.id)
        await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command('bu.subscribers')
    async def bu_subscribers(self, ctx: commands.Context):

        subscribers: List[BanUtilSubscription] = await BanUtilSubscription.filter(from_guild_id=ctx.guild.id).all()
        if len(subscribers) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No subscribers')
        else:
            entries = []
            for subscriber in subscribers:
                guild = self.bot.get_guild(subscriber.to_guild.id)
                if guild == None:
                    entries.append(subscriber.to_guild.id)
                else:
                    entries.append(f'{guild.name} ({guild.id})')
            await self.utils.list_items(ctx, entries)
    
    @commands.command('bu.subscriptions')
    async def bu_subscriptions(self, ctx: commands.Context):

        subscriptions: List[BanUtilSubscription] = await BanUtilSubscription.filter(to_guild=ctx.guild.id).all()
        if len(subscriptions) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No subscriptions')
        else:
            entries = []
            for subscriber in subscriptions:
                guild = self.bot.get_guild(subscriber.to_guild.id)
                if guild == None:
                    entries.append(subscriber.to_guild.id)
                else:
                    entries.append(f'{guild.name} ({guild.id})')
            await self.utils.list_items(ctx, entries)

    # debug
    @commands.command('bu.reload')
    async def reload(self, ctx: commands.Context, message_id: int):

        try:
            ban_event = await BanUtilBanEvent.get(message_id=message_id)
        except DoesNotExist:
            try:
                crossban_event = await BanUtilCrossbanEvent.get(message_id=message_id)
            except DoesNotExist:
                print('uh oh')
            else:
                await self.update_crossban_message(crossban_event)
        else:
            await self.update_ban_message(ban_event)
