#!/usr/bin/env python


from __future__ import annotations

import json

import packaging.requirements
from corpus import PyMetadata, create_session

from conda_pypi.translate import (
    CondaMetadata,
    FileDistribution,
)


def demo():
    session = create_session()
    metadata = session.query(PyMetadata).limit(1000)
    for m in metadata:
        dist = FileDistribution(m.metadata)
        try:
            meta = CondaMetadata.from_distribution(dist)
            index_json = meta.package_record.to_index_json()
            if len(index_json["depends"]) > 1:  # interesting
                print(json.dumps({m.filename: index_json}, indent=2, sort_keys=True))
        except packaging.requirements.InvalidRequirement as e:
            print(m.filename, e)


if __name__ == "__main__":
    demo()
