# pylint: disable=unsubscriptable-object   # pylint/issues/3882

import uuid
import re
import platform
from typing import Optional, List, Any, Tuple

import unpaddedbase64
import discord
from discord.ext import commands

from shaak.errors import InvalidId
from shaak.database import Setting

def chunks(lst: List[Any], size: int):
    size = max(1, size)
    return [lst[i:i+size] for i in range(0, len(lst), size)]

def link_to_message(msg: discord.Message):
    return f'https://discord.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}'

def all_str(iterator):
    for item in iterator:
        yield str(item)

def redis_key(module_name: str, *args: str):

    tmp = ['shaak', module_name]
    tmp.extend(args)
    return ':'.join(all_str(tmp))

def str2bool(msg: str) -> Optional[bool]:
    
    if msg.lower() in ['false', 'no', 'disable', 'off']:
        return False
    elif msg.lower() in ['true', 'yes', 'enable', 'on']:
        return True
    else:
        return None

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

def mention2id(mention: str, mention_type: MentionType) -> Optional[int]:

    try:
        return _mention2id(mention, mention_type)
    except ValueError:
        raise InvalidId()

regex_mention2id = re.compile(r'<((?:@!)|(?:@&)|(?:#))(\d+)>')
def _mention2id(mention: str, mention_type: MentionType) -> Optional[int]:

    if (match := regex_mention2id.match(mention)):
        if match.group(1) != mention_type:
            raise InvalidId()
        return int(match.group(2))
    return int(mention)

def id2mention_validate(mention_type: MentionType):
    def wrapped(id: int):
        return id2mention(id, mention_type)
    return wrapped

def id2mention(id: int, mention_type: MentionType) -> str:
    return f'<{mention_type}{id}>'

def uuid2b64(inp: uuid.UUID) -> str:
    return unpaddedbase64.encode_base64(inp.bytes, urlsafe=True)

def b642uuid(inp: str) -> uuid.UUID:
    return uuid.UUID(bytes=unpaddedbase64.decode_base64(inp))

async def check_privildged(guild: discord.Guild, member: discord.Member):

    server_settings: Setting = await Setting.objects.get(server_id=guild.id)

    if server_settings.authenticated_role == None:
        return None

    for role in member.roles:
        if role.id == server_settings.authenticated_role:
            return True
    else:
        return False
    
def bold_segments(source: str, segments: List[Tuple[int]]) -> str:

    processed = []
    for segment in segments:
        processed.extend(range(int(segment[0]), int(segment[1])))
    ranges = get_int_ranges(processed)
    offset = 0
    result = source
    for range_ in ranges:
        result = bold_segment(result, range_[0] + offset, range_[1] + offset + 1)
        offset += 4
    return result

def bold_segment(source: str, start: int, end: int) -> str:

    return source[:start] + '**' + source[start:end] + '**' + source[end:]

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