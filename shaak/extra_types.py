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

from typing import Union

from discord import TextChannel, VoiceChannel, CategoryChannel, StoreChannel, DMChannel, GroupChannel

GuildChannel = Union[TextChannel, VoiceChannel, CategoryChannel, StoreChannel]
PrivateChannel = Union[DMChannel, GroupChannel]
GeneralChannel = Union[GuildChannel, PrivateChannel]