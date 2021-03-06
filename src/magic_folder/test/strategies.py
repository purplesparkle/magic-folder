# Copyright 2020 The Magic-Folder Developers
# See COPYING for details.

"""
Hypothesis strategies useful for testing Magic Folder.
"""

from os.path import (
    join,
)

from uuid import (
    UUID,
)

from unicodedata import (
    normalize,
)

from base64 import (
    urlsafe_b64encode,
)

from nacl.signing import (
    SigningKey,
    VerifyKey,
)

from hypothesis.strategies import (
    just,
    one_of,
    sampled_from,
    booleans,
    characters,
    text,
    lists,
    builds,
    binary,
    integers,
    floats,
    fixed_dictionaries,
    dictionaries,
)

from twisted.python.filepath import (
    FilePath,
)

from allmydata.util import (
    base32,
)
from allmydata.util.progress import (
    PercentProgress,
)
from ..snapshot import (
    RemoteAuthor,
    LocalAuthor,
    RemoteSnapshot,
    LocalSnapshot,
)

# There are problems handling non-ASCII paths on platforms without UTF-8
# filesystem encoding.  Punt on them for now. :(
#
# https://github.com/LeastAuthority/magic-folder/issues/38
DOTLESS_SLASHLESS_SEGMENT_ALPHABET = characters(
    blacklist_categories=(
        # Exclude surrogates.  They're complicated.
        "Cs",
        # Exclude non-characters.  I don't know if they can appear in real
        # filesystems or not.  We might want to let them through if we can
        # make them work (they don't work as of this comment).
        "Cn",
    ),
    blacklist_characters=(u"\x00", u".", u"/"),
)
SEGMENT_ALPHABET = one_of(
    DOTLESS_SLASHLESS_SEGMENT_ALPHABET,
    just(u"."),
)

def _normalized(text):
    # In the future we should generate text using different normalizations and
    # denormalized.  The user is likely to be able to enter anything they
    # want, we should know what our behavior is going to be.
    #
    # https://github.com/LeastAuthority/magic-folder/issues/36
    return normalize("NFC", text)


def path_segments(alphabet=SEGMENT_ALPHABET):
    """
    Build unicode strings which are usable as individual segments in a
    filesystem path.
    """
    return text(
        alphabet=alphabet,
        min_size=1,
        # Path segments can typically be longer than this but when turned into
        # an absolute path, the longer the path segment the greater the risk
        # we run into a total path length limit.  We don't really know what we
        # can get away with here.  Even this value might lead to problems if
        # the test suite is operating on multiple path segments joined or
        # using these path segments relative to a very long path.
        #
        # openat(2), at least on POSIX, might someday help with this (deal
        # with long paths segment by segment).  Ideally something like
        # FilePath would abstract over that.  Also it's not available from the
        # stdlib on Python 2.x.
        max_size=32,
    ).filter(
        # Exclude aliases for current directory and parent directory.
        lambda segment: segment not in {u".", u".."},
    ).map(
        _normalized,
    )

def path_segments_without_dotfiles(path_segments=path_segments()):
    """
    Build unicode strings which are usable as individual segments in a
    filesystem path and which never start with a ``.``.
    """
    return builds(
        lambda a, b: a + b,
        DOTLESS_SLASHLESS_SEGMENT_ALPHABET,
        path_segments,
    )

def relative_paths(segments=path_segments()):
    """
    Build unicode strings which are usable as relative filesystem paths.
    """
    # There is PATH_MAX but it is a bit of a lie.  Set this arbitrarily to
    # limit computational complexity of the strategy.
    return lists(
        segments,
        min_size=1,
        max_size=8,
    ).map(
        lambda xs: join(*xs),
    )


def absolute_paths(relative_paths=relative_paths()):
    """
    Build unicode strings which are usable as absolute filesystem paths.
    """
    return relative_paths.map(
        lambda p: u"/" + p,
    )


def absolute_paths_utf8(relative_paths=relative_paths()):
    """
    Build byte strings which are valid utf-8 and are usable as absolute
    filesystem paths.
    """
    return relative_paths.map(
        lambda p: (u"/" + p).encode("utf-8"),
    )


def folder_names():
    """
    Build unicode strings which are usable as magic folder names.
    """
    return text(
        min_size=1,
    ).map(
        _normalized,
    )


def tahoe_lafs_chk_capabilities():
    """
    Build unicode strings which look like Tahoe-LAFS CHK capability strings.
    """
    return builds(
        lambda a, b, needed, extra, size: u"URI:CHK:{}:{}:{}:{}:{}".format(
            base32.b2a(a),
            base32.b2a(b),
            needed,
            # Total is how many you need plus how many more there might be.
            needed + extra,
            size,
        ),
        binary(min_size=16, max_size=16),
        binary(min_size=32, max_size=32),
        integers(min_value=1, max_value=128),
        integers(min_value=0, max_value=127),
        integers(min_value=56),
    )


def tahoe_lafs_dir_capabilities():
    """
    Build unicode strings which look like Tahoe-LAFS directory capability strings.
    """
    return builds(
        lambda a, b: u"URI:DIR2:{}:{}".format(base32.b2a(a), base32.b2a(b)),
        binary(min_size=16, max_size=16),
        binary(min_size=32, max_size=32),
    )


def tahoe_lafs_immutable_dir_capabilities():
    """
    Build unicode strings which look like Tahoe-LAFS immutable directory
    capability strings.
    """
    return tahoe_lafs_chk_capabilities().map(
        lambda chkcap: chkcap.replace(u":CHK:", u":DIR2-CHK:"),
    )

def tahoe_lafs_readonly_dir_capabilities():
    """
    Build unicode strings which look like Tahoe-LAFS read-only directory
    capability strings.
    """
    return tahoe_lafs_dir_capabilities().map(
        lambda chkcap: chkcap.replace(u":DIR2:", u":DIR2-RO:"),
    )


def tokens():
    """
    Build byte strings which are usable as Tahoe-LAFS web API authentication
    tokens.
    """
    return binary(
        min_size=32,
        max_size=32,
    ).map(
        urlsafe_b64encode,
    )


def filenodes():
    """
    Build JSON-compatible descriptions of Tahoe-LAFS filenode metadata.
    """
    return fixed_dictionaries({
        # CHK capabilities are only read-only.
        "ro_uri": tahoe_lafs_chk_capabilities(),
        "size": integers(min_value=0),
        "format": just(u"CHK"),
        "metadata": fixed_dictionaries({
            "version": integers(min_value=0),
            "deleted": booleans(),
            "tahoe": fixed_dictionaries({
                "linkmotime": integers(min_value=0, max_value=2 ** 31 - 1),
                "linkcrtime": integers(min_value=0, max_value=2 ** 31 - 1),
            }),
        }),
    })



def progresses():
    """
    Build ``PercentProgress`` instances.
    """
    def a_progress(progress, total_size):
        p = PercentProgress(total_size)
        p.set_progress(progress)
        return p

    return builds(
        a_progress,
        floats(
            min_value=0.0,
            max_value=100.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        integers(min_value=0),
    )


def magic_folder_filenames():
    return text(min_size=1)


author_names = text

def signing_keys():
    """
    Build ``SigningKey`` instances.
    """
    return binary(min_size=32, max_size=32).map(SigningKey)


def verify_keys():
    """
    Build ``VerifyKey`` instances.
    """
    return binary(min_size=32, max_size=32).map(VerifyKey)


def local_authors(names=author_names(), signing_keys=signing_keys()):
    """
    Build ``LocalAuthor`` instances.
    """
    return builds(
        LocalAuthor,
        name=names,
        signing_key=signing_keys,
    )


def remote_authors(names=author_names(), verify_keys=verify_keys()):
    """
    Build ``RemoteAuthor`` instances.
    """
    return builds(
        RemoteAuthor,
        name=names,
        verify_key=verify_keys,
    )


def port_numbers():
    """
    Build ``int`` port numbers in a valid range for TCP.
    """
    return integers(min_value=1, max_value=2 ** 16 - 1)


def interfaces():
    """
    Build ``unicode`` strings that might represent an interface string in a
    Twisted string endpoint description.
    """
    return sampled_from([
        u"127.0.0.1",
        u"10.0.0.1",
        u"0.0.0.0",
        # Pick an uncommon address from the documentation range
        # https://en.wikipedia.org/wiki/Reserved_IP_addresses
        u"192.0.2.123",
    ])


def unique_value_dictionaries(keys, values, min_size=None, max_size=None):
    """
    Build dictionaries with keys drawn from ``keys`` and values drawn from
    ``values``.  No value will appear more than once.

    :param int min_size: The fewest number of items in the resulting
        dictionaries.

    :param int max_size: The greatest number of items in the resulting
        dictionaries.
    """
    return lists(
        keys,
        unique=True,
        min_size=min_size,
        max_size=max_size,
    ).flatmap(
        lambda keys: lists(
            values,
            unique=True,
            min_size=len(keys),
            max_size=len(keys),
        ).map(
            lambda values: dict(zip(keys, values)),
        ),
    )


def remote_snapshots(names=path_segments(), authors=remote_authors()):
    """
    Build ``RemoteSnapshot`` instances.
    """
    return builds(
        RemoteSnapshot,
        name=names,
        author=authors,
        metadata=dictionaries(text(), text()),
        capability=tahoe_lafs_immutable_dir_capabilities(),
        parents_raw=lists(tahoe_lafs_immutable_dir_capabilities()),
        content_cap=tahoe_lafs_chk_capabilities(),
    )


def uuids():
    """
    Build ``uuid.UUID`` instances.
    """
    return binary(
        min_size=16,
        max_size=16,
    ).map(lambda bs: UUID(bytes=bs))


def local_snapshots():
    """
    Build ``LocalSnapshot`` instances.

    Currently this builds snapshots with no local parents.
    """
    return builds(
        LocalSnapshot,
        name=relative_paths(),
        author=local_authors(),
        metadata=dictionaries(text(), text()),
        content_path=absolute_paths().map(FilePath),
        parents_local=just([]),
        parents_remote=lists(tahoe_lafs_immutable_dir_capabilities()),
        identifier=uuids(),
    )
