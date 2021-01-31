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

import asyncio
import json
import logging
from pathlib import Path

from tortoise import Tortoise

from shaak.models import GlobalSettings

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %H:%M:%S', level=logging.INFO)

def ask_user(msg: str, default_true: bool = True):
    return input(f'{msg} [{"Y" if default_true else "y"}/{"n" if default_true else "N"}] ').strip().lower()[0:] in (['y', ''] if default_true else ['y'])

async def init_db():

    from shaak.settings import app_settings
    
    print('Enter global settings (press enter for default)')
    default_prefix = input('Default prefix [-]: ').strip() or '-'
    default_verbosity = ask_user('Default verbosity', True)

    logging.info('Initializing database')
    await Tortoise.init(
        db_url=app_settings.database_url,
        modules={
            'models': ['shaak.models', 'aerich.models']
        }
    )
    conn = Tortoise.get_connection('default')
    resp = await conn.execute_query("select * from information_schema.tables where table_schema = 'public'")
    if resp[0] > 0:
        logging.info('Dropping tables')
    for table in resp[1]:
        await conn.execute_query(f"drop table {table['table_name']} cascade")
    logging.info('Generating schemas')
    await Tortoise.generate_schemas(safe=False)
    logging.info('Writing global settings')
    await GlobalSettings.create(
        default_prefix=default_prefix,
        default_verbosity=default_verbosity
    )
    await Tortoise.close_connections()

def initialize_bot():
    
    # initialize settings

    settings_path = Path('settings.json')
    if not settings_path.exists() or ask_user('Overwrite settings?', False):

        settings = {}
        setting_names = [
            [ 'token',        str ],
            [ 'database_url', str ],
            [ 'status',       str ],
            [ 'owner_id',     int ]
        ]

        try:
            for name in setting_names:
                settings[name[0]] = name[1](input(f'Enter {name[0]}: ').strip())
        except KeyboardInterrupt:
            return

        logging.info('Writing settings')
        with settings_path.open('w') as f:
            json.dump(settings, f, indent=4)

    else:
        with settings_path.open() as f:
            settings = json.load(f)

    # initialize database

    if ask_user('Overwrite DB?'):
        asyncio.run(init_db())
