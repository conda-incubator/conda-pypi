from setuptools import setup, find_packages

setup(
    name="test-package-with-data",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    data_files=[
        ("share/test-package-with-data/data", ["src/test_package_with_data/data/test.txt"]),
        ("share/test-package-with-data", ["src/test_package_with_data/share/config.json"]),
    ],
)
