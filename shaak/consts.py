import enum, discord, dataclasses
from discord.ext import commands

class ResponseLevel(enum.Enum):
    success         = 0
    general_error   = 1
    internal_error  = 2
    forbidden       = 3
    module_disabled = 4

response_map = {
    ResponseLevel.success:         [ '✅', discord.Color(0x2ecc71) ],
    ResponseLevel.general_error:   [ '❌', discord.Color(0xd22513) ],
    ResponseLevel.forbidden:       [ '⛔', discord.Color(0xd22513) ],
    ResponseLevel.internal_error:  [ '‼️', discord.Color(0xd22513) ],
    ResponseLevel.module_disabled: [ '🚫', discord.Color(0xd22513) ]
}

@dataclasses.dataclass
class ModuleInfo:
    name:  str
    flag:  int

mention_none = discord.AllowedMentions(
    everyone=False,
    users=False,
    roles=False
)

settings_ignore = [
    'server_id',
    'enabled_modules',
    'ww_exemptions'
]