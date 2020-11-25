import argparse

def bootstrap():

    from shaak.start import start_bot
    start_bot()

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
