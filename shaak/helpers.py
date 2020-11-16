from typing import List

import discord

from shaak.consts import redis_prefix

def chunks(l, n):
    n = max(1, n)
    return [l[i:i+n] for i in range(0, len(l), n)]

def link_to_message(msg: discord.Message):
    return f'https://discord.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}'

def all_str(iterator):
    for item in iterator:
        yield str(item)

def redis_key(module_name, *args):

    tmp = [redis_prefix, module_name]
    tmp.extend(args)
    return ':'.join(all_str(tmp))