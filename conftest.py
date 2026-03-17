# conftest.py - pytest/Django test configuration
# Patches removed APIs for Python 3.12 compatibility with older libraries (PyConfigure).
import inspect
import collections
import collections.abc

if not hasattr(inspect, 'getargspec'):
    inspect.getargspec = inspect.getfullargspec

if not hasattr(collections, 'MutableMapping'):
    collections.MutableMapping = collections.abc.MutableMapping
if not hasattr(collections, 'Mapping'):
    collections.Mapping = collections.abc.Mapping
