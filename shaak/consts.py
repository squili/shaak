'''
Shaak Discord moderation bot
Copyright (C) 2020 Squili

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
'''

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

import ormar
import discord
from discord.ext import commands

from shaak.helpers import str2bool, bool2str, mention2id_validate, id2mention_validate, MentionType, ensurebool, pass_value

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
    settings: ormar.Model

@dataclass
class TaskInfo:
    name:      str
    wait_time: float

@dataclass
class PseudoId:
    id: int

color_green = discord.Color(0x2ecc71)
color_red   = discord.Color(0xd22513)

response_map = {
    ResponseLevel.success:         [ '✅', color_green ],
    ResponseLevel.general_error:   [ '❌', color_red   ],
    ResponseLevel.forbidden:       [ '⛔', color_red   ],
    ResponseLevel.internal_error:  [ '‼️', color_red   ],
    ResponseLevel.module_disabled: [ '🚫', color_red   ]
}

# setting_name: (serialize, deserialize)
setting_structure = {
    'prefix':    (str, lambda x: f'`{x}`'),
    'verbosity': (str2bool, bool2str),
    'auth_role': (mention2id_validate(MentionType.role), id2mention_validate(MentionType.role))
}

class MatchType(Enum):
    regex = 0
    word = 1

def str_to_match_type(stuff: str) -> MatchType:
    if stuff.startswith('_'):
        raise AttributeError(stuff)
    return getattr(MatchType, stuff)

watch_setting_map = {
    'del': ensurebool,
    'cased': ensurebool,
    'type': str_to_match_type,
    'ping': pass_value
}