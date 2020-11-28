'''
Shaak Discord moderation bot
Copyright (C) 2020 Squili

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
'''

import argparse
import asyncio

def bootstrap():

    from shaak.start import start_bot
    asyncio.run(start_bot())

def init():

    from shaak import initialize_bot
    initialize_bot()

def main():
    
    parser = argparse.ArgumentParser('shaak')
    parser.set_defaults(run=parser.print_help)
    parser.add_argument('--debug', help='Name of the logger to dump')
    parser.add_argument('--trace', help='Start tracemalloc', action='store_true')
    command_subparsers = parser.add_subparsers()
    command_subparsers.add_parser('init').set_defaults(run=init)
    command_subparsers.add_parser('run').set_defaults(run=bootstrap)
    args = parser.parse_args()

    if args.debug:
        import logging
        logger = logging.getLogger(args.debug)
        logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(filename='debug.log', encoding='utf8', mode='w')
        handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
        logger.addHandler(handler)
    
    if args.trace:
        import tracemalloc
        tracemalloc.start()

    args.run()

if __name__ == '__main__':
    
    main()
