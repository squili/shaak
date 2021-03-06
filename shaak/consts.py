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

from dataclasses import dataclass
from datetime    import timedelta
from enum        import Enum
from typing      import Union

import discord
from discord.ext     import commands
from tortoise.models import Model

from shaak.helpers import (str2bool, bool2str, mention2id_validate, MentionType,
                           id2mention_validate, ensurebool, pass_value, RollingValues)

bu_invite_timeout = timedelta(days=3)

class ResponseLevel(Enum):
    success         = 0
    general_error   = 1
    internal_error  = 2
    forbidden       = 3
    module_disabled = 4

@dataclass
class ModuleInfo:
    name:     str
    settings: Model

@dataclass
class TaskInfo:
    name:      str
    wait_time: float

color_green = discord.Color(0x2ecc71)
color_red   = discord.Color(0xd22513)

response_map = {
    ResponseLevel.success:         [ '✅', color_green ],
    ResponseLevel.general_error:   [ '❌', color_red   ],
    ResponseLevel.forbidden:       [ '⛔', color_red   ],
    ResponseLevel.internal_error:  [ '‼️', color_red    ],
    ResponseLevel.module_disabled: [ '🚫', color_red   ]
}

# setting_name: (serialize, deserialize)
setting_structure = {
    'prefix':                                             (str, lambda x: f'`{x}`'),
    'verbosity':                                     (str2bool, bool2str),
    'auth_role':        (mention2id_validate(MentionType.role), id2mention_validate(MentionType.role)),
    'error_channel': (mention2id_validate(MentionType.channel), id2mention_validate(MentionType.channel))
}

class MatchType(Enum):
    contains = 0
    word     = 1
    regex    = 2

def str_to_match_type(stuff: str) -> MatchType:
    if stuff.startswith('_'):
        raise AttributeError(stuff)
    return getattr(MatchType, stuff)

def ww_ban_parse(stuff: Union[str, bool]) -> int:
    if stuff in [None, False]:
        return None
    if stuff == True:
        return 0
    num = int(stuff)
    if num < 0:
        return 0
    if num > 7:
        return 7
    return num

watch_setting_map = {
    'del': ensurebool,
    'cased': ensurebool,
    'type': str_to_match_type,
    'ping': pass_value,
    'ban': ww_ban_parse
}

mem_usage_stat = RollingValues()
