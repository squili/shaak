# pylint: disable=unsubscriptable-object   # pylint/issues/3637

import uuid
import re
import platform
from typing import Optional

import unpaddedbase64
import discord
from discord.ext import commands

from shaak.errors import InvalidId
from shaak.database import Setting

def chunks(l, n):
    n = max(1, n)
    return [l[i:i+n] for i in range(0, len(l), n)]

def link_to_message(msg: discord.Message):
    return f'https://discord.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}'

def all_str(iterator):
    for item in iterator:
        yield str(item)

def redis_key(module_name, *args):

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
    
def bold_segment(source, start, end):

    return source[:start] + '**' + source[start:end] + '**' + source[end:]

def platform_info() -> str:

    return f'{platform.python_implementation()} v{platform.python_version()} on {platform.system()}'