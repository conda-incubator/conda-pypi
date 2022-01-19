"""
conda subcommand for CLI
"""
import sys
from conda_pip.main import install


def main(*packages):

    conda, pypi = install(*packages)
    print("Available in conda:")
    for name, depset in conda.items():
        if len(depset) == 1:
            print(" -", next(iter(depset)))
        else:
            print(" -", name, "# choose most restrictive:", *depset)
    print("Not available in conda:")
    for name, depset in pypi.items():
        if len(depset) == 1:
            print(" -", next(iter(depset)))
        else:
            print(" -", name, "# choose most restrictive:", *depset)


if __name__ == "__main__":
    main(*sys.argv[1:])
