try:
    # works if calling from an repo or an pip install -e installation
    from setuptools_scm import get_version
    __version__ = get_version()
except LookupError:
    try:
        # works if calling from other pip install methods
        from ._version import version as __version__
    except ImportError:
        # worst case scenario
        __version__ = '0.0.0'
