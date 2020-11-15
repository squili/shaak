import argparse

from shaak import initialize_bot

def bootstrap():

    from shaak.start import start_bot
    start_bot()

def main():
    
    parser = argparse.ArgumentParser('shaak')
    parser.set_defaults(run=parser.print_help)
    command_subparsers = parser.add_subparsers()
    command_subparsers.add_parser('run').set_defaults(run=bootstrap)
    command_subparsers.add_parser('init').set_defaults(run=initialize_bot)
    
    args = parser.parse_args()
    args.run()

if __name__ == '__main__':
    
    main()
