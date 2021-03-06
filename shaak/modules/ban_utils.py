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

import asyncio
from datetime import datetime
from typing   import List, Optional, Tuple, Union

import discord
from discord.ext           import commands
from tortoise.exceptions   import DoesNotExist
from tortoise.transactions import in_transaction

from shaak.base_module import BaseModule
from shaak.checks      import has_privlidged_role_check
from shaak.consts      import ModuleInfo, ResponseLevel, color_red
from shaak.helpers     import (check_privildged, datetime_repr, str2bool, bool2str,
                               DiscardingQueue, multi_split, commas, getrange_s)
from shaak.models      import (BanUtilBanEvent, BanUtilCrossbanEvent, BanUtilInvite,
                               BanUtilSettings, BanUtilSubscription, BanUtilBlock)

class BanUtils(BaseModule):
    
    meta = ModuleInfo(
        name='ban_utils',
        settings=BanUtilSettings
    )
    
    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.report_locks: Union[int, asyncio.Lock] = {}
        self.massban_queue = DiscardingQueue(0x10)

    async def initialize(self):

        for guild in self.bot.guilds:
            self.report_locks[guild.id] = asyncio.Lock()

        self.massban_task = self.bot.loop.create_task(self.massban_loop())

        await super().initialize()
    
    async def close(self):

        await self.massban_queue.put(None)
        if self.massban_task:
            await self.massban_task
    
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

        target_user: Optional[discord.User] = await self.utils.aggressive_resolve_user(ban_event.target_id)
        if target_user == None:
            title = f'{ban_event.target_id} banned'
        else:
            icon_url = target_user.display_avatar.url
            title = f'{target_user.name}#{target_user.discriminator} ({ban_event.target_id}) banned'

        if ban_event.banner_id != None:
            banner_user: Optional[discord.User] = await self.utils.aggressive_resolve_user(ban_event.banner_id)
            if banner_user == None:
                title += f' by {ban_event.banner_id}'
            else:
                title += f' by {banner_user.name}#{banner_user.discriminator}'
                if icon_url == None:
                    icon_url = banner_user.avatar.url

        if icon_url == None:
            icon_url = guild.icon_url

        if ban_event.id == None:
            description_entries = [
                ( 'Reason', ban_event.ban_reason ),
                ( '???',                  'Closed' )
            ]
        else:
            description_entries = [
                ( 'Reason',                                                               ban_event.ban_reason ),
                ( '????', f'Reported on {datetime_repr(ban_event.reported)}' if ban_event.reported else 'Report' ),
                ( '????' if ban_event.banned else '????',                   'Unban' if ban_event.banned else 'Ban' ),
                ( '???',                                                                                 'Close')
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

        icon_url = source_guild.icon.url
        target_user: discord.User = await self.utils.aggressive_resolve_user(crossban_event.event.target_id)
        if target_user == None:
            title = f'{crossban_event.event.target_id} banned in {source_guild.name}'
        else:
            title = f'{target_user.name}#{target_user.discriminator} ({crossban_event.event.target_id}) banned in {source_guild.name}'
            if icon_url == None:
                icon_url = target_user.avatar.url

        if crossban_event.event.banner_id != None:
            banner_user: Optional[discord.User] = await self.utils.aggressive_resolve_user(crossban_event.event.banner_id)
            if banner_user == None:
                title += f' by {crossban_event.event.banner_id}'
            else:
                title += f' by {banner_user.name}#{banner_user.discriminator}'
                if icon_url == None:
                    icon_url = banner_user.avatar.url

        if crossban_event.id == None:
            description_entries = [
                ( 'Reason', crossban_event.event.ban_reason ),
                ( '???',                             'Closed' )
            ]
        else:
            description_entries = [
                ( 'Reason',                                                                crossban_event.event.ban_reason ),
                ( '????', f'Forwarded on {datetime_repr(crossban_event.reported)}' if crossban_event.reported else 'Forward' ),
                ( '????' if crossban_event.banned else '????',                     'Unban' if crossban_event.banned else 'Ban' ),
                ( '???',                                                                                             'Close')
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
            try:
                ban_event = await BanUtilBanEvent.get(guild_id=guild.id, target_id=user.id)
                if not ban_event.banned:
                    ban_event.banned = True
                    await ban_event.save()
                    await self.update_ban_message(ban_event)
                    return
            except DoesNotExist:
                try:
                    crossban_event = await BanUtilCrossbanEvent.get(guild_id=guild.id, event__target_id=user.id)
                    if not crossban_event.banned:
                        crossban_event.banned = True
                        await crossban_event.save()
                        await self.update_crossban_message(crossban_event)
                        return
                except DoesNotExist:
                    pass
            
            ban_user_id = None
            ban_reason = 'No reason given'
            while ban_user_id == None:
                async for log_entry in guild.audit_logs(limit=100, action=discord.AuditLogAction.ban):
                    if log_entry.target == user:
                        ban_user_id = log_entry.user.id
                        ban_reason = log_entry.reason
                        break
                await asyncio.sleep(0.1)
            
            module_settings: BanUtilSettings = await BanUtilSettings.get(guild_id=guild.id)

            log_channel = guild.get_channel(module_settings.domestic_log_channel)
            if log_channel == None:
                return

            new_message = await log_channel.send(
                embed=discord.Embed(
                    color=discord.Color(0xFFFFFF),
                    description='????'
                )
            )

            async with in_transaction():

                ban_event = await BanUtilBanEvent.create(
                    guild_id=guild.id,
                    message_id=new_message.id,
                    message_channel=module_settings.domestic_log_channel,
                    target_id=user.id,
                    banner_id=ban_user_id,
                    ban_reason=ban_reason
                )

                await self.update_ban_message(ban_event)

            await new_message.add_reaction('????')
            await new_message.add_reaction('????')
            await new_message.add_reaction('???')
        except Exception as e:
            await self.utils.log_background_error(guild, e)
    
    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: Union[discord.Member, discord.User]):

        try:
            try:
                ban_event = await BanUtilBanEvent.get(guild_id=guild.id, target_id=user.id)
                if ban_event.banned:
                    ban_event.banned = False
                    await ban_event.save()
                    await self.update_ban_message(ban_event)
            except DoesNotExist:
                try:
                    crossban_event = await BanUtilCrossbanEvent.get(guild_id=guild.id, event__target_id=user.id)
                    if crossban_event.banned:
                        crossban_event.banned = False
                        await crossban_event.save()
                        await self.update_crossban_message(crossban_event)
                except DoesNotExist:
                    return
        except Exception as e:
            await self.utils.log_background_error(guild, e)
    
    # we have to use the raw reaction event because rapptz hates me
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):

        try:
            if payload.user_id == self.bot.user.id \
                or payload.emoji.is_custom_emoji() \
                or payload.emoji.name not in ['????', '????', '????', '???', '???', '??????', '???']:
                return

            guild = self.bot.get_guild(payload.guild_id)
            channel = guild.get_channel(payload.channel_id)
            if channel is None:
                channel = guild.get_thread(payload.channel_id)
            try:
                message = await channel.fetch_message(payload.message_id)
            except discord.HTTPException as e:
                if e.code == 10008:
                    return
                else:
                    raise e
            user = await guild.fetch_member(payload.user_id)

            if message.author != self.bot.user or len(message.embeds) != 1:
                return
            
            if payload.emoji.name in ['???', '??????', '???']:
                # invite alerts

                try:
                    invite = await BanUtilInvite.filter(message_id=message.id).prefetch_related('from_guild', 'to_guild').get()
                except DoesNotExist:
                    await message.clear_reactions()
                    return
                
                action_msg = None
                
                if payload.emoji.name == '???':

                    action_msg = 'Accepted'

                    try:
                        await BanUtilSubscription.get(
                            from_guild_id=invite.from_guild.id,
                            to_guild_id=invite.to_guild.id
                        )
                    except DoesNotExist:
                        await BanUtilSubscription.create(
                            from_guild_id=invite.from_guild.id,
                            to_guild_id=invite.to_guild.id
                        )

                        foreign_settings = await BanUtilSettings.get(guild_id=invite.from_guild.id)
                        if foreign_settings.foreign_log_channel != None:
                            target_channel = self.bot.get_channel(foreign_settings.foreign_log_channel)
                            if target_channel == None:
                                foreign_settings.foreign_log_channel = None
                                await foreign_settings.save()
                            else:
                                try:
                                    await target_channel.send(embed=discord.Embed(
                                        color=discord.Color.green(),
                                        description=f'Subscription from {guild.name} ({guild.id})'
                                    ))
                                except discord.Forbidden:
                                    pass
                
                elif payload.emoji.name == '??????':

                    action_msg = 'Blocked'

                    try:
                        block = await BanUtilBlock.get(
                            guild_id=invite.to_guild.id,
                            blocked_id=invite.from_guild.id
                        )
                    except DoesNotExist:
                        await BanUtilBlock.create(
                            guild_id=invite.to_guild.id,
                            blocked_id=invite.from_guild.id
                        )

                elif payload.emoji.name == '???':

                    action_msg = 'Disabled'

                    await BanUtilSettings.filter(guild_id=invite.to_guild.id).update(receive_invite_alerts=False)

                await invite.delete()
                embed = message.embeds[0].copy()
                embed.description = action_msg
                await message.edit(embed=embed)
                await message.clear_reactions()

            else:
                # bans

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

                privilidged = await check_privildged(guild, guild.get_member(user.id))
                if privilidged:
                    ban_perms = True
                    crosspost_perms = True
                    delete_perms = True
                else:
                    permissions = channel.permissions_for(user)
                    ban_perms = permissions.ban_members
                    crosspost_perms = permissions.manage_guild
                    delete_perms = permissions.manage_guild
                
                if payload.emoji.name == '????' and crosspost_perms:
                    await message.add_reaction('????')

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
                                    if target_channel == None:
                                        # set channel not valid
                                        continue
                                    new_message = await target_channel.send(
                                        embed=discord.Embed(
                                            color=discord.Color(0xFFFFFF),
                                            description='????'
                                        )
                                    )

                                    new_event = await BanUtilCrossbanEvent.create(
                                        guild=subscriber.to_guild,
                                        event=ban_event,
                                        message_id=new_message.id,
                                        message_channel=module_settings.foreign_log_channel
                                    )

                                    await new_message.add_reaction('????')
                                    await new_message.add_reaction('????')
                                    await new_message.add_reaction('???')
                                    await self.update_crossban_message(new_event)

                        event.reported = datetime.now()
                        await event.save(update_fields=['reported'])

                    if is_ban_event:
                        await self.update_ban_message(event)
                    else:
                        await self.update_crossban_message(event)
                    await message.remove_reaction('????', self.bot.user)

                elif payload.emoji.name == '????' and event.banned and ban_perms:

                    if is_ban_event:
                        ban_event = event
                    else:
                        ban_event = event.event
                    try:
                        await guild.unban(discord.Object(ban_event.target_id), reason=f'BanUtils action by {user.id}')
                    except discord.HTTPException as e:
                        if e.code == 10026:
                            pass
                        else:
                            raise e
                    event.banned = False
                    await event.save()
                    await message.remove_reaction('????', self.bot.user)
                    await message.add_reaction('????')
                    if is_ban_event:
                        await self.update_ban_message(event)
                    else:
                        await self.update_crossban_message(event)
                
                elif payload.emoji.name == '????' and not event.banned and ban_perms:

                    if is_ban_event:
                        ban_event = event
                    else:
                        ban_event = event.event
                    await guild.ban(discord.Object(ban_event.target_id), reason=f'BanUtils action by {user.id}')
                    event.banned = True
                    await event.save()
                    await message.remove_reaction('????', self.bot.user)
                    await message.add_reaction('????')
                    if is_ban_event:
                        await self.update_ban_message(event)
                    else:
                        await self.update_crossban_message(event)
                
                elif payload.emoji.name == '???' and delete_perms:

                    await event.delete()
                    await message.clear_reactions()
                    event.id = None
                    if is_ban_event:
                        await self.update_ban_message(event)
                    else:
                        await self.update_crossban_message(event)
                
                else:
                    return
            
                await message.remove_reaction(payload.emoji, user)
        except Exception as e:
            await self.utils.log_background_error(guild, e)
        
    @commands.command('bu.invite')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_invite(self, ctx: commands.Context, target_guild_id: int):

        target_guild = self.bot.get_guild(target_guild_id)
        if target_guild == None:
            await self.utils.respond(ctx, ResponseLevel.general_error, f'Guild with id {target_guild_id} not found')
            return
        
        if target_guild_id == ctx.guild.id:
            await self.utils.respond(ctx, ResponseLevel.general_error, "That's you!")
            return

        try:
            await BanUtilSubscription.get(from_guild_id=ctx.guild.id, to_guild_id=target_guild_id)
        except DoesNotExist:
            try:
                await BanUtilInvite.get(from_guild_id=ctx.guild.id, to_guild_id=target_guild_id)
            except DoesNotExist:
                if await BanUtilBlock.filter(blocked_id=ctx.guild.id).exists():
                    await self.utils.respond(ctx, ResponseLevel.forbidden, 'You are blocked from inviting this guild')
                else:

                    message_id = None
                    foreign_settings = await BanUtilSettings.get(guild_id=target_guild_id)

                    if foreign_settings.receive_invite_alerts and foreign_settings.foreign_log_channel != None:
                        target_channel = target_guild.get_channel(foreign_settings.foreign_log_channel)
                        if target_channel != None:

                            new_message = await target_channel.send(embed=discord.Embed(
                                color=discord.Color.green(),
                                title=f'Invite from {ctx.guild.name} ({ctx.guild.id})',
                                description='\n'.join([
                                    'Accept with ???',
                                    'Block guild with ??????',
                                    'Disable alerts with ???'
                                ])
                            ))
                            await new_message.add_reaction('???')
                            await new_message.add_reaction('??????')
                            await new_message.add_reaction('???')
                            message_id = new_message.id
                            
                    await BanUtilInvite.create(
                        from_guild_id=ctx.guild.id,
                        to_guild_id=target_guild_id,
                        message_id=message_id
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

                foreign_settings = await BanUtilSettings.get(guild_id=source_guild_id)
                if foreign_settings.foreign_log_channel != None:
                    target_channel = self.bot.get_channel(foreign_settings.foreign_log_channel)
                    if target_channel != None:
                        await target_channel.send(embed=discord.Embed(
                            color=discord.Color.green(),
                            description=f'Subscription from {ctx.guild.name} ({ctx.guild.id})'
                        ))
                        
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

            foreign_settings = await BanUtilSettings.get(guild_id=target_guild_id)
            if foreign_settings.foreign_log_channel != None:
                target_channel = self.bot.get_channel(foreign_settings.foreign_log_channel)
                if target_channel != None:
                    await target_channel.send(embed=discord.Embed(
                        color=discord.Color.red(),
                        description=f'Kicked by {ctx.guild.name} ({ctx.guild.id})'
                    ))
    
    @commands.command('bu.foreign')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_foreign(self, ctx: commands.Context, log_channel: commands.TextChannelConverter):

        self.utils.ensure_guild_contains_channel(ctx.guild.id, log_channel.id)
        await BanUtilSettings.filter(guild_id=ctx.guild.id).update(foreign_log_channel=log_channel.id)
        await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command('bu.domestic')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_domestic(self, ctx: commands.Context, log_channel: commands.TextChannelConverter):

        await BanUtilSettings.filter(guild_id=ctx.guild.id).update(domestic_log_channel=log_channel.id)
        await self.utils.respond(ctx, ResponseLevel.success)
    
    @commands.command('bu.subscribers')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_subscribers(self, ctx: commands.Context):

        subscribers: List[BanUtilSubscription] = await BanUtilSubscription.filter(from_guild_id=ctx.guild.id).prefetch_related('to_guild').all()
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
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_subscriptions(self, ctx: commands.Context):

        subscriptions: List[BanUtilSubscription] = await BanUtilSubscription.filter(to_guild=ctx.guild.id).prefetch_related('from_guild').all()
        if len(subscriptions) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No subscriptions')
        else:
            entries = []
            for subscriber in subscriptions:
                guild = self.bot.get_guild(subscriber.from_guild.id)
                if guild == None:
                    entries.append(subscriber.from_guild.id)
                else:
                    entries.append(f'{guild.name} ({guild.id})')
            await self.utils.list_items(ctx, entries)
    
    @commands.command('bu.block')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_block(self, ctx: commands.Context, target_guild_id: int):

        target_guild = self.bot.get_guild(target_guild_id)
        if target_guild == None:
            await self.utils.respond(ctx, ResponseLevel.general_error, f'Guild with id {target_guild_id} not found')
            return

        try:
            block = await BanUtilBlock.get(
                guild_id=ctx.guild.id,
                blocked_id=target_guild_id
            )
        except DoesNotExist:
            await BanUtilBlock.create(
                guild_id=ctx.guild.id,
                blocked_id=target_guild_id
            )
            await self.utils.respond(ctx, ResponseLevel.success)
        else:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Guild already blocked')

    @commands.command('bu.unblock')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_unblock(self, ctx: commands.Context, target_guild_id: int):

        target_guild = self.bot.get_guild(target_guild_id)
        if target_guild == None:
            await self.utils.respond(ctx, ResponseLevel.general_error, f'Guild with id {target_guild_id} not found')
            return

        try:
            block = await BanUtilBlock.get(
                guild_id=ctx.guild.id,
                blocked_id=target_guild_id
            )
        except DoesNotExist:
            await self.utils.respond(ctx, ResponseLevel.general_error, 'Guild not blocked')
        else:
            await block.delete()
            await self.utils.respond(ctx, ResponseLevel.success)

    @commands.command('bu.blocked')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_blocks(self, ctx: commands.Context):

        blocks: List[BanUtilBlock] = await BanUtilBlock.filter(guild_id=ctx.guild.id).prefetch_related('blocked').all()
        if len(blocks) == 0:
            await self.utils.respond(ctx, ResponseLevel.success, 'No blocks')
        else:
            entries = []
            for block_entry in blocks:
                guild = self.bot.get_guild(block_entry.blocked.id)
                if guild == None:
                    entries.append(block_entry.blocked.id)
                else:
                    entries.append(f'{guild.name} ({guild.id})')
            await self.utils.list_items(ctx, entries)

    @commands.command('bu.alerts')
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def bu_alerts(self, ctx: commands.Context, new_value: Optional[str] = None):

        module_settings = await BanUtilSettings.get(guild_id=ctx.guild.id)
        if new_value == None:
            await self.utils.respond(ctx, ResponseLevel.success, bool2str(module_settings.receive_invite_alerts))
        else:
            bool_value = str2bool(new_value)
            if bool_value == None:
                await self.utils.respond(ctx, ResponseLevel.general_error, 'Hm?')
                return
            else:
                module_settings.receive_invite_alerts = bool_value
            await module_settings.save(update_fields=['receive_invite_alerts'])
            await self.utils.respond(ctx, ResponseLevel.success)
    
    async def massban_loop(self):

        await self.initialized.wait()

        while True:
            item = await self.massban_queue.get()
            if item == None:
                return
            try:
                await self.massban_inner(item)
            except Exception as e:
                await self.utils.log_background_error(item.guild, e)

    async def massban_inner(self, item):

        errors = []
        for (index, id) in enumerate(item.ids):
            try:
                await item.ctx.guild.ban(discord.Object(id))
            except Exception:
                errors.append(index+1)

        await item.condition.acquire()
        item.condition.notify()
        item.condition.release()
        
        if len(errors) > 0:
            await self.utils.respond(item.ctx, ResponseLevel.general_error, f'Failed banning {commas(getrange_s(errors))}')
        else:
            await self.utils.respond(item.ctx, ResponseLevel.success)

    @commands.command('massban')
    @commands.guild_only()
    @commands.check_any(commands.has_permissions(administrator=True), has_privlidged_role_check())
    async def massban(self, ctx: commands.Context, *ids: int):

        await ctx.message.add_reaction('????')

        ids = list(ids)

        for attachment in ctx.message.attachments:
            if attachment.content_type.startswith('text/plain') and attachment.size < (1024**2):
                file = await attachment.to_file()
                new = file.fp.read().decode('utf8')
                for entry in multi_split(new, [' ', '\t', '\n', '\r']):
                    try:
                        ids.append(int(entry))
                    except ValueError:
                        await self.respond(ctx, ResponseLevel.general_error, f'Failed parsing id {entry}')
                        return

        condition = asyncio.Condition()
        await condition.acquire()

        await self.massban_queue.put(MassbanItem(
            ctx,
            self.utils,
            ids,
            f'Massban by {ctx.author.id}',
            condition,
        ))

        position = len(self.massban_queue)

        if position > 3:
            await ctx.message.reply(f'You are position {position} in the queue')
        
        await condition.wait()
        await ctx.message.remove_reaction('????', self.bot.user)

class MassbanItem:

    def __init__(self, ctx: commands.Context, utils, ids: List[int], reason: str, condition: asyncio.Condition):
        self.ctx = ctx
        self.utils = utils
        self.ids = ids
        self.reason = reason
        self.condition = condition

    async def aclose(self):
        await self.utils.respond(self.ctx, ResponseLevel.general_error, 'Bot under too much pressure, cancelling...')
        await self.condition.acquire()
        await self.condition.notify_all()
