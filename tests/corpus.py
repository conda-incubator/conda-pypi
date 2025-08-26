#!/usr/bin/env python
"""
Database of pypi and conda metadata to check how well we can convert the
former to the latter.
"""

from __future__ import annotations

import json
import pprint
import sys
from itertools import groupby
from pathlib import Path

import pypi_simple.errors
import sqlalchemy
import urllib3

try:
    import compression.zstd as zstandard
except ImportError:
    import zstandard
from pypi_simple import NoMetadataError, PyPISimple
from sqlalchemy import (
    JSON,
    TEXT,
    TIMESTAMP,
    Column,
    Computed,
    ForeignKey,
    Integer,
    LargeBinary,
    Table,
    and_,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session

from conda_pypi.translate import (
    FileDistribution,
    pypi_to_conda_name,
    requires_to_conda,
)

HERE = Path(__file__).parent

TABLE_NAMES = {
    "about",
    "icon",
    "index_json",
    "post_install",
    "recipe",
    "run_exports",
}


class Base(DeclarativeBase):
    pass


metadata_obj = Base.metadata

# basically the conda-index schema
for table in TABLE_NAMES:
    if table == "icon":
        data_column = Column("icon_png", LargeBinary)
    else:
        data_column = Column(table, JSON)
    Table(table, metadata_obj, Column("path", TEXT, primary_key=True), data_column)

# store repodata.json
repodata = Table(
    "repodata",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("url", TEXT, nullable=False, unique=True),
    Column("channel_subdir", TEXT, nullable=False),
    Column("repodata_json", JSON, nullable=False),
    Column("timestamp", TIMESTAMP, server_default=func.now()),
)

repodata_packages = Table(
    "repodata_packages",
    metadata_obj,
    Column("repodata_id", Integer, ForeignKey("repodata.id"), primary_key=True),
    Column("package", TEXT, nullable=False, primary_key=True),
    Column("index_json", JSON, nullable=False),
    Column("timestamp", TIMESTAMP, server_default=func.now()),
    Column("name", TEXT, Computed("json_extract(index_json, '$.name')")),
    Column("version", TEXT, Computed("json_extract(index_json, '$.version')")),
)

# store pypi .metadata files
pypi_metadata = Table(
    "pypi_metadata",
    metadata_obj,
    Column("filename", TEXT, primary_key=True),
    Column("name", TEXT),
    Column("version", TEXT),
    Column("metadata", TEXT),
)


class Repodata(Base):
    __table__ = repodata


class RepodataPackages(Base):
    __table__ = repodata_packages

    repodata_id: Mapped[int]
    package: Mapped[str]
    index_json: Mapped[dict]
    timestamp: Mapped[str]
    name: Mapped[str]
    version: Mapped[str]


class PyMetadata(Base):
    __table__ = pypi_metadata

    filename: Mapped[str]
    name: Mapped[str]
    version: Mapped[str]
    metadata: Mapped[str]


def create_engine():
    return sqlalchemy.create_engine(f"sqlite:///{HERE}/pypi.db")


def default_channels(session):
    for u in "main/noarch", "main/linux-64":
        session.execute(
            repodata.insert().values(
                url=f"https://repo.anaconda.com/pkgs/{u}/repodata.json.zst",
                channel_subdir=u,
                repodata_json="{}",
            )
        )

    session.commit()


def create_session():
    engine = create_engine()
    Base.metadata.create_all(engine)
    session = Session(engine)
    return session


def main():
    session = create_session()
    http = urllib3.PoolManager()
    with session.begin():
        for id, url in session.execute(sqlalchemy.text("SELECT id, url FROM repodata")):
            resp = http.request("GET", url)
            data = resp.data
            print("Got", id, url)
            repodata_json = json.loads(zstandard.decompress(data))
            # delete from repodata_packages here
            for group in "packages", "packages.conda":
                for package, index_json in repodata_json.pop(group).items():
                    session.execute(
                        repodata_packages.insert().values(
                            repodata_id=id, package=package, index_json=index_json
                        )
                    )
            session.execute(
                repodata.update().where(repodata.c.id == id).values(repodata_json=repodata_json)
            )


def newest_conda_packages():
    session = create_session()
    depends_on_python = session.execute(
        sqlalchemy.text(
            """
        SELECT repodata_id, package,
            json_extract(index_json, '$.name') name,
            json_extract(index_json, '$.version') version,
            json_extract(index_json, '$.timestamp') timestamp
        FROM repodata_packages, json_each(index_json, '$.depends') dep
        WHERE (dep.value = 'python' OR dep.value LIKE 'python %')
        AND package NOT LIKE '\\_%'
        ORDER BY package
        """
        )
    )
    # timestamp sort avoids version parse errors
    newest_packages = []
    for name, packages in groupby(depends_on_python, lambda x: x.name):
        packages = sorted(packages, key=lambda x: x.timestamp or 0, reverse=True)
        print(name, packages[0].version)
        newest_packages.append(packages[0])

    print("Found", len(newest_packages))

    return newest_packages


def fetch_pypi_metadata():
    session = create_session()
    newest_packages = newest_conda_packages()
    for package in newest_packages:
        print("Package:", package.name)
        if package.name.startswith("_"):
            continue  # e.g. __anaconda_core_depends
        with PyPISimple() as client, session.begin():
            try:
                page = client.get_project_page(package.name)
            except pypi_simple.errors.NoSuchProjectError as e:
                print(package.name, e)
                continue
            # TODO code to skip already-fetched projects
            for pkg in page.packages:
                if pkg.version != package.version:
                    print(pkg.version, "!=", package.version)
                    continue
                if pkg.has_metadata is not None:
                    print("Has metadata?", pkg.has_metadata)
                    try:
                        src = client.get_package_metadata(pkg)
                    except NoMetadataError:
                        print(f"{pkg.filename}: No metadata available")
                    else:
                        print(pkg)
                        # avoid unique errors
                        session.execute(
                            pypi_metadata.delete().where(pypi_metadata.c.filename == pkg.filename)
                        )
                        session.execute(
                            pypi_metadata.insert().values(
                                filename=pkg.filename,
                                name=pkg.project,
                                version=pkg.version,
                                metadata=src,
                            )
                        )
                else:
                    print(f"{pkg.filename}: No metadata available")
                print()


def random_pypi(session, name=""):
    query = pypi_metadata.select().order_by(text("random()")).limit(1)
    if name:
        query = query.where(pypi_metadata.c.name == name)
    row = next(session.execute(query))

    return FileDistribution(row.metadata)  # type: ignore

    # also get conda package with same name and version


def matching_conda(session, name, version):
    """
    Conda package metadata from repodata.json to match pypi name, version
    """
    conda_name = pypi_to_conda_name(name)
    row = next(
        session.execute(
            repodata_packages.select().where(
                and_(
                    repodata_packages.c.name == conda_name,
                    repodata_packages.c.version == version,
                )
            )
        )
    )
    return row


if __name__ == "__main__":
    # main()
    # fetch_pypi_metadata()

    session = create_session()

    try:
        pypi_name = sys.argv[1]
    except IndexError:
        pypi_name = None
    p = random_pypi(session, pypi_name)

    print(p.name)
    print("Requires (Python):", "\n".join(p.requires or []))
    print(
        "\nRequires (Conda):",
        ", ".join(str(r) for r in list(requires_to_conda(p.requires))),
        "\n",
    )

    pprint.pprint(matching_conda(session, p.name, p.version).index_json)

    # e.g.
    # [
    #     "tox ; extra == 'dev'",
    #     "coverage ; extra == 'dev'",
    #     "lxml ; extra == 'dev'",
    #     "xmlschema (>=2.0.0) ; extra == 'dev'",
    #     "Sphinx ; extra == 'dev'",
    #     "memory-profiler ; extra == 'dev'",
    #     "memray ; extra == 'dev'",
    #     "flake8 ; extra == 'dev'",
    #     "mypy ; extra == 'dev'",
    #     "lxml-stubs ; extra == 'dev'",
    # ]

# One popular mapping between pypi, conda names
# https://github.com/regro/cf-graph-countyfair/blob/master/mappings/pypi/grayskull_pypi_mapping.json
