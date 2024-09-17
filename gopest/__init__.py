try:
    # works if calling from an -e installation, or whenever from a git repo
    from setuptools_scm import get_version
    __version__ = get_version()
except LookupError:
    # works if calling from other pip install methods
    from ._version import version as __version__
