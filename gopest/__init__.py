try:
    # Try to import the version from the _version.py file (created by setuptools_scm during a normal install)
    from ._version import version as __version__
except ImportError:
    # Fallback to dynamically fetching the version using setuptools_scm for editable installs
    from setuptools_scm import get_version
    __version__ = get_version()
