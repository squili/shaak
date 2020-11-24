# pylint: disable=unsubscriptable-object   # pylint/issues/3882

from typing import Union

from discord import TextChannel, VoiceChannel, CategoryChannel, StoreChannel, DMChannel, GroupChannel

GuildChannel = Union[TextChannel, VoiceChannel, CategoryChannel, StoreChannel]
PrivateChannel = Union[DMChannel, GroupChannel]
GeneralChannel = Union[GuildChannel, PrivateChannel]