# pylint: disable=unsubscriptable-object   # pylint/issues/3882

import time
from datetime import datetime, timedelta
from typing import Union, Optional, List

import ormar
import discord
from discord.ext import commands

from shaak.base_module import BaseModule
from shaak.consts import ModuleInfo, ResponseLevel, color_red
from shaak.helpers import id2mention, MentionType, check_privildged
from shaak.checks import has_privlidged_role_check
from shaak.consts import bu_invite_timeout
from shaak.models import BanUtilSettings

class BanUtils(BaseModule):
    
    meta = ModuleInfo(
        name='ban_utils',
        settings=BanUtilSettings
    )
    
    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

    async def initialize(self):
        await super().initialize()
    
    async def update_ban_message(self, ban_event: None):

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
            ( 'Reason',                                            ban_event.ban_reason ),
            ( '📣',                       'Reported' if ban_event.reported else 'Report' ),
            ( '🔄' if ban_event.banned else '🔨', 'Unban' if ban_event.banned else 'Ban' )
        ]

        embed = discord.Embed(
            color=color_red,
            description='\n'.join((f'{i[0]}: {i[1]}' for i in description_entries))
        )
        embed.set_author(name=title, icon_url=icon_url)
        await message.edit(embed=embed)
    
    async def update_crossban_message(self, crossban_event: None):

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
            ( 'Reason',                                            crossban_event.event.ban_reason ),
            ( '📣',                          'Forwarded' if crossban_event.reported else 'Forward' ),
            ( '🔄' if crossban_event.banned else '🔨', 'Unban' if crossban_event.banned else 'Ban' )
        ]

        embed = discord.Embed(
            color=color_red,
            description='\n'.join((f'{i[0]}: {i[1]}' for i in description_entries))
        )
        embed.set_author(name=title, icon_url=icon_url)
        await message.edit(embed=embed)
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: Union[discord.Member, discord.User]):

        try:
            await BUEvent.objects.get(guild__id=guild.id, target_id=user.id)
        except ormar.NoMatch:
            pass
        else:
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
        
        module_settings: BUSetting = await BUSetting.objects.get(guild__id=guild.id)

        log_channel = guild.get_channel(module_settings.domestic_events_channel)
        if log_channel == None:
            return

        new_message = await log_channel.send(
            embed=discord.Embed(
                color=discord.Color(0xFFFFFF),
                description='📨'
            )
        )

        ban_event = await BUEvent.objects.create(
            guild=DBGuild(id=guild.id),
            message_id=new_message.id,
            message_channel=module_settings.domestic_events_channel,
            target_id=user.id,
            banner_id=ban_user_id,
            ban_reason=ban_reason or 'No reason given',
            timestamp=datetime.now()
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
            event = await BUEvent.objects.get(message_id=message.id)
        except ormar.NoMatch:
            try:
                event = await BUMirror.objects.get(message_id=message.id)
            except ormar.NoMatch:
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

        if payload.emoji.name == '📣' and not event.reported and crosspost_perms:
            await message.add_reaction('📨')
            if is_ban_event:
                ban_event = event
            else:
                ban_event = event.event

            subscribed: List[BUSubscriber] = await BUSubscriber.objects.filter(producer_guild__id=guild.id).select_related('consumer_guild').all()
            for subscriber in subscribed:
                existing_mirrors = await BUMirror.objects.filter(event=ban_event, guild=subscriber.consumer_guild).count()
                if existing_mirrors == 0:
                    module_settings: BUSetting = await BUSetting.objects.get(guild=subscriber.consumer_guild)
                    if module_settings.foreign_events_channel:

                        target_channel = self.bot.get_channel(module_settings.foreign_events_channel)
                        new_message = await target_channel.send(
                            embed=discord.Embed(
                                color=discord.Color(0xFFFFFF),
                                description='📨'
                            )
                        )

                        new_event = await BUMirror(
                            guild=DBGuild(id=guild.id),
                            event=ban_event,
                            message_id=new_message.id,
                            message_channel=module_settings.foreign_events_channel
                        )

                        await new_message.add_reaction('📣')
                        await new_message.add_reaction('🔨')
                        await self.update_crossban_message(new_event)

            if is_ban_event:
                ban_event.reported = True
                await ban_event.update()

            await message.remove_reaction('📨', self.bot.user)
        elif payload.emoji.name == '🔄' and event.banned and ban_perms:

            if is_ban_event:
                ban_event = event
            else:
                ban_event = event.event
            try:
                await guild.unban(PseudoId(event.target_id))
            except discord.HTTPException as e:
                if e.code == 10026:
                    pass
            event.banned = False
            await event.update()
            await message.add_reaction('🔨')
        
        elif payload.emoji.name == '🔨' and not event.banned and ban_perms:

            if is_ban_event:
                ban_event = event
            else:
                ban_event = event.event
            try:
                await guild.ban(PseudoId(ban_event.target_id))
            except discord.HTTPException as e:
                if e.code == 10026:
                    pass
            event.banned = True
            await event.update()
            await message.add_reaction('🔄')
        
        else:
            return
        
        await message.remove_reaction(payload.emoji, user)
        await message.remove_reaction(payload.emoji, self.bot.user)
        if is_ban_event:
            await self.update_ban_message(event)
        else:
            await self.update_crossban_message(event)
    
    @commands.command('bu.invite')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_invite(self, ctx: commands.Context, target_guild_id: int):

        raise NotImplementedError()

        try:
            await BUSubscriber.objects.get(producer_guild__id=ctx.guild.id, consumer_guild=target_guild_id)
        except ormar.NoMatch:
            try:
                await BUInvite.objects.get(from_guild=ctx.guild.id, to_guild=target_guild_id)
            except ormar.NoMatch:
                await BUInvite.objects.create(
                    from_guild=DBGuild(id=ctx.guild.id),
                    to_guild=target_guild_id
                )
                await self.utils.respond(ctx, ResponseLevel.success)
            else:
                await self.utils.respond(ctx, ResponseLevel.general_error, 'Guild already invited')
        else:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Guild already subscribed')
    
    @commands.command('bu.subscribe')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_subscribe(self, ctx: commands.Context, source_guild_id: int):

        raise NotImplementedError()

        try:
            await BUSubscriber.objects.get(
                producer_guild__id=source_guild_id,
                consumer_guild__id=ctx.guild.id
            )
        except ormar.NoMatch:
            try:
                invite = await BUInvite.objects.get(
                    from_guild__id=source_guild_id,
                    to_guild=ctx.guild.id
                )
            except ormar.NoMatch:
                await self.utils.respond(ctx, ResponseLevel.forbidden, 'That guild has not invited this guild')
            else:
                await invite.delete()
                await BUSubscriber.objects.create(
                    producer_guild=DBGuild(id=source_guild_id),
                    consumer_guild=DBGuild(id=ctx.guild.id)
                )
                await self.utils.respond(ctx, ResponseLevel.success)
                module_settings: BUSetting = await BUSetting.objects.get(guild__id=ctx.guild.id)
                if module_settings.foreign_events_channel == None:
                    await self.utils.respond(ctx, ResponseLevel.general_error,
                        "WARNING: No foreign event channel set, so you won't receive events from this server!")
        else:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Already subscribed to that guild')
    
    @commands.command('bu.unsubscribe')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_unsubscribe(self, ctx: commands.Context, source_guild_id: int):

        raise NotImplementedError()

        try:
            subscription = await BUSubscriber.objects.get(
                producer_guild__id=source_guild_id,
                consumer_guild__id=ctx.guild.id
            )
        except ormar.NoMatch:
            await self.utils.respond(ctx, ResponseLevel.general_error, f'Not subscribed to guild {source_guild_id}')
        else:
            await subscription.delete()
            await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command('bu.kick')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_kick(self, ctx: commands.Context, target_guild_id: int):

        raise NotImplementedError()

        try:
            subscription = await BUSubscriber.objects.get(
                producer_guild__id=ctx.guild.id,
                consumer_guild__id=target_guild_id
            )
        except ormar.NoMatch:
            try:
                invite = await BUInvite.objects.get(
                    from_guild__id=ctx.guild.id,
                    to_guild=target_guild_id
                )
            except ormar.NoMatch:
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

        raise NotImplementedError()

        await BUSetting.objects.filter(guild=DBGuild(id=ctx.guild.id)).update(foreign_events_channel=log_channel.id)
        await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command('bu.domestic')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_domestic(self, ctx: commands.Context, log_channel: commands.TextChannelConverter):

        raise NotImplementedError()

        await BUSetting.objects.filter(guild=DBGuild(id=ctx.guild.id)).update(domestic_events_channel=log_channel.id)
        await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command('bu.subscribers')
    async def bu_subscribers(self, ctx: commands.Context):

        raise NotImplementedError()

        subscribers: List[BUSubscriber] = await BUSubscriber.objects.filter(producer_guild=DBGuild(id=ctx.guild.id)).all()
        if len(subscribers) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No subscribers')
        else:
            entries = []
            for subscriber in subscribers:
                # subscriber = await BUSubscriber.objects.select_related('consumer_guild').get(id=subscriber.id)
                guild = self.bot.get_guild(subscriber.consumer_guild.id)
                if guild == None:
                    entries.append(subscriber.consumer_guild.id)
                else:
                    entries.append(f'{guild.name} ({guild.id})')
            await self.utils.list_items(ctx, entries)
    
    @commands.command('bu.subscriptions')
    async def bu_subscriptions(self, ctx: commands.Context):

        raise NotImplementedError()

        subscriptions: List[BUSubscriber] = await BUSubscriber.objects.filter(consumer_guild=DBGuild(id=ctx.guild.id))\
                                                    .select_related('producer_guild').all()
        if len(subscriptions) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No subscriptions')
        else:
            entries = []
            for subscriber in subscriptions:
                guild = self.bot.get_guild(subscriber.producer_guild.id)
                if guild == None:
                    entries.append(subscriber.producer_guild.id)
                else:
                    entries.append(f'{guild.name} ({guild.id})')
            await self.utils.list_items(ctx, entries)

    # debug
    @commands.command('bu.reload')
    async def reload(self, ctx: commands.Context, message_id: int):

        raise NotImplementedError()

        try:
            ban_event = await BUEvent.objects.get(message_id=message_id)
        except ormar.NoMatch:
            try:
                crossban_event = await BUMirror.objects.get(message_id=message_id)
            except ormar.NoMatch:
                print('uh oh')
            else:
                await self.update_crossban_message(crossban_event)
        else:
            await self.update_ban_message(ban_event)