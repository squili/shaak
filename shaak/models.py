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

from tortoise.models import Model
from tortoise        import fields

class ModuleSettingsMixin:
    enabled = fields.BooleanField (default=False)

class GlobalSettings(Model):
    id                = fields.SmallIntField (pk=True, generated=False, default=0) # single entry table
    default_prefix    = fields.TextField     ()
    default_verbosity = fields.BooleanField  ()

class Guild(Model):
    id = fields.BigIntField          (pk=True, generated=False)
    delete_at = fields.DatetimeField (null=True)

class GuildSettings(Model):
    guild         = fields.ForeignKeyField ('models.Guild', related_name='guild_settings')
    prefix        = fields.TextField       (null=True)
    verbosity     = fields.BooleanField    (null=True)
    auth_role     = fields.BigIntField     (null=True)
    error_channel = fields.BigIntField     (null=True)

class WordWatchSettings(Model, ModuleSettingsMixin):
    guild       = fields.ForeignKeyField ('models.Guild', related_name='word_watch_settings')
    log_channel = fields.BigIntField     (null=True)
    header      = fields.TextField       (null=True)

class WordWatchPingGroup(Model):
    guild = fields.ForeignKeyField ('models.Guild', related_name='word_watch_ping_groups')
    name  = fields.TextField       ()

class WordWatchPing(Model):
    group     = fields.ForeignKeyField ('models.WordWatchPingGroup', related_name='pings')
    ping_type = fields.CharField       (2)
    target_id = fields.BigIntField     ()

class WordWatchWatch(Model):
    guild       = fields.ForeignKeyField ('models.Guild', related_name='word_watch_watches')
    group       = fields.ForeignKeyField ('models.WordWatchPingGroup', related_name='watches', null=True, on_delete=fields.SET_NULL)
    pattern     = fields.TextField       ()
    match_type  = fields.IntField        ()
    auto_delete = fields.BooleanField    ()
    ignore_case = fields.BooleanField    ()

class WordWatchIgnore(Model):
    guild        = fields.ForeignKeyField ('models.Guild', related_name='word_watch_ignores')
    target_id    = fields.BigIntField     ()
    mention_type = fields.CharField       (2)

class PreviewSettings(Model, ModuleSettingsMixin):
    guild       = fields.ForeignKeyField ('models.Guild', related_name='preview_settings')
    log_channel = fields.BigIntField     (null=True)

class PreviewFilter(Model):
    guild      = fields.ForeignKeyField ('models.Guild', related_name='preview_filter')
    channel_id = fields.BigIntField     ()

class BanUtilSettings(Model, ModuleSettingsMixin):
    guild                 = fields.ForeignKeyField ('models.Guild', related_name='ban_util_settings')
    foreign_log_channel   = fields.BigIntField     (null=True)
    domestic_log_channel  = fields.BigIntField     (null=True)
    receive_invite_alerts = fields.BooleanField    (default=True)

class BanUtilBanEvent(Model):
    guild           = fields.ForeignKeyField ('models.Guild', related_name='ban_util_ban_event')
    message_id      = fields.BigIntField     ()
    message_channel = fields.BigIntField     ()
    target_id       = fields.BigIntField     ()
    banner_id       = fields.BigIntField     ()
    ban_reason      = fields.TextField       (null=True)
    timestamp       = fields.DatetimeField   (auto_now_add=True)
    banned          = fields.BooleanField    (default=True)
    reported        = fields.DatetimeField   (default=None, null=True)

class BanUtilCrossbanEvent(Model):
    guild           = fields.ForeignKeyField ('models.Guild', related_name='ban_util_crossban_event')
    event           = fields.ForeignKeyField ('models.BanUtilBanEvent', related_name='crossbans')
    message_id      = fields.BigIntField     ()
    message_channel = fields.BigIntField     ()
    timestamp       = fields.DatetimeField   (auto_now_add=True)
    banned          = fields.BooleanField    (default=False)
    reported        = fields.DatetimeField   (default=None, null=True)

class BanUtilInvite(Model):
    from_guild = fields.ForeignKeyField ('models.Guild', related_name='ban_utils_outgoing_invites')
    to_guild   = fields.ForeignKeyField ('models.Guild', related_name='ban_utils_incoming_invites')
    message_id = fields.BigIntField     (null=True)

class BanUtilSubscription(Model):
    from_guild = fields.ForeignKeyField ('models.Guild', related_name='ban_utils_subscribers')
    to_guild   = fields.ForeignKeyField ('models.Guild', related_name='ban_utils_subscriptions')

class BanUtilBlock(Model):
    guild   = fields.ForeignKeyField ('models.Guild', related_name='ban_util_blocks')
    blocked = fields.ForeignKeyField ('models.Guild', related_name='ban_util_blocked')

class UserWatchSettings(Model, ModuleSettingsMixin):
    guild         = fields.ForeignKeyField ('models.Guild', related_name='user_watch_settings')
    log_channel   = fields.BigIntField     (null=True)
    cooldown_time = fields.IntField        (default=900000)
    header        = fields.TextField       (null=True)

class UserWatchWatch(Model):
    guild   = fields.ForeignKeyField ('models.Guild', related_name='user_watch_watch')
    user_id = fields.BigIntField()
