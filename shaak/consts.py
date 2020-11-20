import dataclasses
from enum import Enum

import discord
from discord.ext import commands

from shaak.helpers import str2bool, bool2str, mention2id_validate, id2mention_validate, MentionType

class ResponseLevel(Enum):
    success         = 0
    general_error   = 1
    internal_error  = 2
    forbidden       = 3
    module_disabled = 4

@dataclasses.dataclass
class ModuleInfo:
    name:  str
    flag:  int

class PseudoId:
    
    def __init__(self, id: int):
        self.id = id

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
    'command_prefix':     (str, str),
    'verbose_errors':     (str2bool, bool2str),
    'authenticated_role': (mention2id_validate(MentionType.role), id2mention_validate(MentionType.role))
}