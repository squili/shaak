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

# pylint: disable=unsubscriptable-object   # pylint/issues/3882

import asyncio
import time
import logging
import platform
import re
from datetime import datetime
from typing   import Optional, List, Any, Tuple, Union, TypeVar

import discord

from shaak.errors import InvalidId
from shaak.models import GuildSettings

logger = logging.getLogger('shaak_helpers')

_T = TypeVar('T')

def chunks(lst: List[Any], size: int):
    size = max(1, size)
    return [lst[i:i+size] for i in range(0, len(lst), size)]

def link_to_message(msg: discord.Message):
    return f'https://discord.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}'

def all_str(iterator):
    for item in iterator:
        yield str(item)

def str2bool(msg: Union[str, bool]) -> Optional[bool]:

    if isinstance(msg, bool):
        return msg
    
    if msg.lower() in ['false', 'no', 'disable', 'off']:
        return False
    elif msg.lower() in ['true', 'yes', 'enable', 'on']:
        return True
    else:
        return None

def ensurebool(maybe_msg: Union[str, bool]) -> bool:
    if type(maybe_msg) == bool:
        return maybe_msg
    resp = str2bool(maybe_msg)
    if resp == None:
        raise ValueError(maybe_msg)
    return resp

def bool2str(value: bool, yes: str = 'on', no: str = 'off') -> str:
    if value:
        return yes
    return no

class MentionType:
    user    = '@!'
    channel = '#'
    role    = '@&'

def mention2id_validate(mention_type: MentionType):
    def wrapped(mention: str):
        return mention2id(mention, mention_type)
    return wrapped

def mention2id(mention: str, mention_type: Optional[MentionType] = None) -> Optional[int]:

    try:
        return _mention2id(mention, mention_type)
    except ValueError:
        raise InvalidId()

regex_mention2id = re.compile(r'<((?:@!)|(?:@&)|(?:#))(\d+)>')
def _mention2id(mention: str, mention_type: Optional[MentionType]) -> Optional[int]:

    if (match := regex_mention2id.match(mention)):
        if mention_type != None and match.group(1) != mention_type:
            raise InvalidId()
        return int(match.group(2))
    return int(mention)

def id2mention_validate(mention_type: MentionType):
    def wrapped(id: int):
        return id2mention(id, mention_type)
    return wrapped

def id2mention(id: int, mention_type: MentionType) -> str:
    return f'<{mention_type}{id}>'

async def check_privildged(guild: discord.Guild, member: discord.Member):

    guild_settings: GuildSettings = await GuildSettings.get(guild_id=guild.id)

    if guild_settings.auth_role == None:
        return None

    for role in member.roles:
        if role.id == guild_settings.auth_role:
            return True
    else:
        return False
    
def between_segments(source: str, segments: List[Tuple[int]], char: str = '`') -> str:

    processed = []
    for segment in segments:
        processed.extend(range(int(segment[0]), int(segment[1])))
    ranges = get_int_ranges(processed)
    offset = 0
    result = source
    for range_ in ranges:
        result = between_segment(result, range_[0] + offset, range_[1] + offset + 1, char)
        offset += len(char)*2
    return result

def between_segment(source: str, start: int, end: int, char: str = '`') -> str:

    return source[:start] + char + source[start:end] + char + source[end:]

def platform_info() -> str:

    return f'{platform.python_implementation()} v{platform.python_version()} on {platform.system()}'

def get_int_ranges(numbers: List[int]) -> List[int]:

    if len(numbers) == 0: return []
    ordered = sorted(numbers)
    ranges = []
    first = None
    previous = ordered.pop(0)
    for num in ordered:
        if num - previous == 1:
            if first == None:
                first = previous
        elif first != None:
            ranges.append((first, previous))
            first = None
        else:
            ranges.append((previous, previous))
        previous = num
    if first == None:
        ranges.append((previous, previous))
    else:
        ranges.append((first, previous))
    return ranges

def getrange_s(numbers: List[int]) -> List[str]:

    results = []
    for item in get_int_ranges(numbers):
        if item[0] == item[1]:
            results.append(str(item[0]))
        else:
            results.append(f'{item[0]}-{item[1]}')
    return results

def commas(values: List[Any]) -> str:

    if len(values) == 0: return ''
    if len(values) == 1: return str(values[0])
    if len(values) == 2: return f'{values[0]} and {values[1]}'
    values[-1] = f'and {values[-1]}'
    return ', '.join(values)

def pluralize(single: str, plural: str, length: int) -> str:
    if length == 1:
        return single
    return plural

def pass_value(value: _T) -> _T:
    return value

def resolve_mention(message: str) -> Optional[Tuple[MentionType, int]]:

    for potential_type in (MentionType.channel, MentionType.user, MentionType.role):
        if message.startswith('<' + potential_type):
            return potential_type, mention2id(message, potential_type)
    return None, None

def datetime_repr(dt: datetime) -> str:
    return dt.strftime('%d/%m/%y')

def possesivize(word: str) -> str:
    if word.endswith('s'):
        return word + "'"
    return word + "'s"

class DiscardingQueue:

    def __init__(self, max_size: int):
        self.max_size = max_size
        self._queue = asyncio.Queue(max_size)
    
    @property
    def get(self):
        return self._queue.get
    
    async def put(self, item):
        while self._queue.full():
            self._queue.get_nowait()
            logger.warn('queue discarding messages')
        return await self._queue.put(item)

def get_or_create(d, k, t):
    if k not in d:
        d[k] = t
    return d[k]

def time_ms():
    return round(time.time() * 1000)