from tortoise.models import Model
from tortoise import fields

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
    guild     = fields.ForeignKeyField ('models.Guild', related_name='guild_settings')
    prefix    = fields.TextField       (null=True)
    verbosity = fields.BooleanField    (null=True)
    auth_role = fields.BigIntField     (null=True)

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
    group       = fields.ForeignKeyField ('models.WordWatchPingGroup', related_name='watches', null=True, on_delete='SET NULL')
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
    guild                = fields.ForeignKeyField ('models.Guild', related_name='ban_util_settings')
    foreign_log_channel  = fields.BigIntField     (null=True)
    domestic_log_channel = fields.BigIntField     (null=True)

class BanUtilBanEvent(Model):
    guild           = fields.ForeignKeyField ('models.Guild', related_name='ban_util_ban_event')
    message_id      = fields.BigIntField     ()
    message_channel = fields.BigIntField     ()
    target_id       = fields.BigIntField     ()
    banner_id       = fields.BigIntField     (null=True)
    ban_reason      = fields.TextField       ()
    timestamp       = fields.DatetimeField   (auto_now_add=True)
    banned          = fields.BooleanField    (default=True)
    reported        = fields.DatetimeField   (default=None, null=True)

class BanUtilCrossbanEvent(Model):
    guild           = fields.ForeignKeyField ('models.Guild', related_name='ban_util_crossban_event')
    event           = fields.ForeignKeyField ('models.BanUtilBanEvent', related_name='crossbans')
    message_id      = fields.BigIntField     ()
    message_channel = fields.BigIntField     ()
    banned          = fields.BooleanField    (default=False)
    reported        = fields.DatetimeField   (default=None, null=True)

class BanUtilInvite(Model):
    from_guild = fields.ForeignKeyField ('models.Guild', related_name='ban_utils_outgoing_invites')
    to_guild   = fields.ForeignKeyField ('models.Guild', related_name='ban_utils_incoming_invites')

class BanUtilSubscription(Model):
    from_guild = fields.ForeignKeyField ('models.Guild', related_name='ban_utils_subscribers')
    to_guild   = fields.ForeignKeyField ('models.Guild', related_name='ban_utils_subscriptions')
