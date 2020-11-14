import argparse
from shaak import start_bot, initialize_bot

def main():
    
    parser = argparse.ArgumentParser('shaak')
    parser.set_defaults(run=parser.print_help)
    command_subparsers = parser.add_subparsers()
    command_subparsers.add_parser('run').set_defaults(run=start_bot)
    command_subparsers.add_parser('init').set_defaults(run=initialize_bot)
    
    args = parser.parse_args()
    args.run()

if __name__ == '__main__':
    
    main()