"""
Run metadata, dependency translation on a collection of packages; see which fail, succeed.
"""

import pytest
from conda.models.match_spec import MatchSpec
from packaging.requirements import InvalidRequirement

from conda_pupa.translate import CondaMetadata, FileDistribution, conda_to_requires

# XXX different pythonpath under pytest
skip = False
try:
    import corpus
except ImportError:
    try:
        from . import corpus
    except ImportError:
        skip = True

# Example package we can't convert, if we try to "pip install" the same.

# WARNING: Ignoring version 5.0.5 of celery since it has invalid metadata:
# Requested celery==5.0.5 from https://files.pythonhosted.org/packages/95/79/d73247b42082076bb32c828e3361cda2604ee523aa3bfe972bdfabffc6d0/celery-5.0.5-py3-none-any.whl has invalid metadata: Expected matching RIGHT_PARENTHESIS for LEFT_PARENTHESIS, after version specifier
#     pytz (>dev)
#          ~^
# Please use pip<24.1 if you need to use this version.


@pytest.mark.skipif(skip, reason="corpus not available")
def test_many_from_distribution():
    session = corpus.create_session()
    names = set()
    versions = set()
    for row in session.query(corpus.PyMetadata):
        try:
            CondaMetadata.from_distribution(
                FileDistribution(row.metadata)
            ).package_record
            names.add(row.name)
            versions.add((row.name, row.version))
        except Exception as e:
            print(
                "Couldn't convert %s %s (%s)" % (row.name, row.version, row.filename), e
            )

    print(
        f"Converted {len(names)} distinct names and {len(versions)} distinct (name, version)"
    )


@pytest.mark.skipif(skip, reason="corpus not available")
def test_conda_deps_to_pypi():
    session = corpus.create_session()
    failed = []
    success = 0
    for row in session.query(corpus.RepodataPackages):
        for conda_requires in row.index_json["depends"]:
            try:
                converted = conda_to_requires(MatchSpec(conda_requires))
                assert converted
                success += 1
            except InvalidRequirement:
                if len(conda_requires.split()) != 3:
                    # most of these are specs with a build number "h5py 3.11.0 py310hbe37b52_0"

                    # packaging.requirements.Requirement does not allow _ as the
                    # start of a package, used in conda virtual packages
                    # '__win', '__linux' and in some metapacages

                    # Doesn't like version numbers ending in arbitrary letters like jpeg >=9e,<10a
                    # (Some of those conda packages won't depend on Python; omit from pypa requirements)
                    print(
                        f"Could not convert {conda_requires} from {row.index_json['name']} to pypi form"
                    )
                failed.append(conda_requires)

    print(
        f"Converted {success} and failed {len(failed)} conda to pypi dependency specifiers."
    )


if __name__ == "__main__":
    test_many_from_distribution()
