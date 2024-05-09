import json
import sys
from pathlib import Path

from conda.base.context import context
from conda.core.prefix_data import PrefixData
from conda.models.enums import PackageType

def post_command(command: str):
    if command != "list":
        return
    if "--explicit" not in sys.argv:
        return
    PrefixData._cache_.clear()
    pd = PrefixData(context.target_prefix, pip_interop_enabled=True)
    pd.load()
    to_print = []
    for record in pd.iter_records():
        if record.package_type != PackageType.VIRTUAL_PYTHON_WHEEL:
            continue
        ignore = False
        for path in record.files:
            path = Path(context.target_prefix, path)
            if "__editable__" in path.stem:
                ignore = True
                break
            if path.name == "direct_url.json":
                data = json.loads(path.read_text())
                if data.get("dir_info", {}).get("editable"):
                    ignore = True
                    break
        if ignore:
            continue

        if record.url:
            to_print.append(f"# pypi: {record.url}")
        else:
            to_print.append(f"# pypi: {record.name}=={record.version}")

    if to_print:
        print("# Following lines added by conda-pypi")
        print(*to_print, sep="\n")
