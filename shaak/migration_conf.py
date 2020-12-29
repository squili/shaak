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

# this file includes a reference to the config for aerich

from shaak.settings import app_settings

ORM_CONFIG = {
    'connections': {'default': app_settings.database_url},
    'apps': {
        'models': {
            'models': ['shaak.models', 'aerich.models'],
            'default_connection': 'default'
        }
    }
}