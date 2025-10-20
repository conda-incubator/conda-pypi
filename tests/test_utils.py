"""Tests for the utils module."""

from __future__ import annotations

import pytest
from conda_pypi.utils import pypi_spec_variants


@pytest.mark.parametrize(
    "input_spec,expected_count",
    [
        ("setuptools-scm", 2),
        ("setuptools_scm", 2),
        ("numpy", 1),
        ("setuptools-scm>=1.0", 3),
        ("a-b_c", 3),
    ],
)
def test_pypi_spec_variants_generates_correct_count(input_spec: str, expected_count: int):
    """Test that pypi_spec_variants generates the expected number of variants."""
    variants = list(pypi_spec_variants(input_spec))
    assert len(variants) == expected_count
    assert len(variants) == len(set(variants))


def test_pypi_spec_variants_preserves_original():
    """Test that the original specification is always the first variant."""
    assert list(pypi_spec_variants("setuptools-scm"))[0] == "setuptools-scm"
    assert list(pypi_spec_variants("setuptools_scm"))[0] == "setuptools_scm"


def test_pypi_spec_variants_creates_name_variants():
    """Test that pypi_spec_variants creates hyphen/underscore variants."""
    variants = list(pypi_spec_variants("setuptools-scm"))
    assert "setuptools-scm" in variants
    assert "setuptools_scm" in variants
