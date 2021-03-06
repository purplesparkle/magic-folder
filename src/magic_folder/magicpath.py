import re
import os.path

from allmydata.util.assertutil import precondition, _assert

def path2magic(path):
    return re.sub(u'[/@]',  lambda m: {u'/': u'@_', u'@': u'@@'}[m.group(0)], path)

def magic2path(path):
    return re.sub(u'@[_@]', lambda m: {u'@_': u'/', u'@@': u'@'}[m.group(0)], path)


IGNORE_SUFFIXES = [u'.backup', u'.tmp', u'.conflict']
IGNORE_PREFIXES = [u'.']

def should_ignore_file(path_u):
    precondition(isinstance(path_u, unicode), path_u=path_u)

    for suffix in IGNORE_SUFFIXES:
        if path_u.endswith(suffix):
            return True

    while path_u != u"":
        oldpath_u = path_u
        path_u, tail_u = os.path.split(path_u)
        if tail_u.startswith(u"."):
            return True
        if path_u == oldpath_u:
            return True  # the path was absolute
        _assert(len(path_u) < len(oldpath_u), path_u=path_u, oldpath_u=oldpath_u)

    return False

def mangle_path(p):
    """
    returns a unicode string given a FilePath (should be mangled
    according to .. whatever rules magic-folder already uses?)

    :param FilePath p: file path to be mangled

    :returns unicode: mangled path
    """
    # XXX why DO we "mangle paths"? Could we just put the
    # relative path for the name here instead? (that is,
    # relative to the magic-folder base).

    # how else to get the unicode version of this path?
    return path2magic(p.asTextMode(encoding="utf-8").path)
