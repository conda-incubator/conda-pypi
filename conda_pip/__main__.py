import sys

from conda.cli.main import main_subshell

if __name__ == "__main__":
    sys.exit(main_subshell("pip", *sys.argv[1:]))
