import discord
from typing import List

def str2bool(msg: str):
    
    if msg.lower() in ['false', 'no', 'disable']:
        return False
    elif msg.lower() in ['true', 'yes', 'enable']:
        return True
    else:
        return None

def chunks(l, n):
    n = max(1, n)
    return [l[i:i+n] for i in range(0, len(l), n)]

def link_to_message(msg: discord.Message):
    return f'https://discord.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}'
