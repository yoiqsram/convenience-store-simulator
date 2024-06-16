from .cli import parse_args, init, run


if __name__ == '__main__':
    args = parse_args()

    command: str = args.command
    if command == 'init':
        init(args)
    elif command == 'run':
        run(args)
