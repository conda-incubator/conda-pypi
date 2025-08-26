from typing import Iterable

from conda.plugins.types import InstallerBase

from .main import run_pip_install

class PipInstaller(InstallerBase):
    def install(self, prefix, specs, *args, **kwargs) -> Iterable[str]:
        """Install packages into an environment"""
        run_pip_install(
            prefix=prefix,
            args=specs,
        )

    def dry_run(self, prefix, specs, *args, **kwargs) -> Iterable[str]:
        """Do a dry run of the environment install"""
        run_pip_install(
            prefix=prefix,
            args=specs,
            dry_run=True,
        )
