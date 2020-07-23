from __future__ import print_function

import attr
import os

from hypothesis import (
    given,
)
from hypothesis.strategies import (
    binary,
    lists,
)

from twisted.python.filepath import (
    FilePath,
)

from twisted.internet import defer

from testtools.matchers import (
    Equals,
    Always,
    HasLength,
    MatchesStructure,
)
from testtools.twistedsupport import (
    succeeded,
)
from testtools import (
    ExpectedException,
)

from eliot import (
    Message,
)

from magic_folder.magic_folder import (
    LocalSnapshotService,
    LocalSnapshotCreator,
)
from magic_folder.snapshot import (
    create_local_author,
)
from magic_folder.magicpath import (
    path2magic,
)
from .. import magicfolderdb

from .common import (
    SyncTestCase,
)
from .strategies import (
    path_segments,
)

@attr.s
class MemorySnapshotCreator(object):
    processed = attr.ib(default=attr.Factory(list))

    def process_item(self, path):
        Message.log(
            message_type=u"memory-snapshot-creator:process_item",
            path=path.asTextMode("utf-8").path,
        )
        self.processed.append(path)
        return defer.succeed(None)


class LocalSnapshotTests(SyncTestCase):

    def setUp(self):
        super(LocalSnapshotTests, self).setUp()
        self.db = magicfolderdb.get_magicfolderdb(":memory:", create_version=(magicfolderdb.SCHEMA_v1, 1))
        self.author = create_local_author("alice")

        self.stash_dir = self.mktemp()
        os.mkdir(self.stash_dir)

        magic_path_dirname = self.mktemp()
        os.mkdir(magic_path_dirname)

        self.magic_path = FilePath(magic_path_dirname)
        self._snapshot_creator = MemorySnapshotCreator()

        self.snapshot_service = LocalSnapshotService(
            magic_path=self.magic_path,
            snapshot_creator=self._snapshot_creator,
        )


    def setup_example(self):
        """
        Hypothesis-invoked hook to create per-example state.
        Reset the database before running each test.
        """
        self.db._clear_snapshot_table()

    def test_add_single_file(self):
        foo = self.magic_path.child("foo")
        content = u"foo"
        with foo.open("w") as f:
            f.write(content)

        self.snapshot_service.startService()
        d = self.snapshot_service.add_file(foo)

        self.assertThat(
            d,
            succeeded(Always()),
        )

        foo_magicname = path2magic(foo.asTextMode().path)
        self.assertThat(self._snapshot_creator.processed, Equals([foo]))

        # we should have processed one snapshot upload
        # def handler(result):
        #     print("handler called")
        #     self.assertThat(self.db.snapshots, HasLength(1))

        #     foo_magicname = path2magic(foo.asTextMode().path)
        #     stored_snapshot = self.db.get_local_snapshot(foo_magicname, self.author)
        #     stored_content = stored_snapshot._get_synchronous_content()

        #     self.assertThat(stored_content, Equals(content))
        #     self.assertThat(stored_snapshot.parents_local, HasLength(0))

        # d.addCallback(handler)

        
    # @given(lists(path_segments().map(lambda p: p.encode("utf-8")), unique=True),
    #        lists(binary(), unique=True))
    # def test_add_multiple_files(self, filenames, contents):
    #     files = []
    #     for (filename, content) in zip(filenames, contents):
    #         file = self.magic_path.child(filename)
    #         with file.open("wb") as f:
    #             f.write(content)
    #         files.append(file)

    #     self.snapshot_service.startService()

    #     dList = []
    #     for file in files:
    #         result_d = yield self.snapshot_service.add_file(file)
    #         dList.append(result_d)

    #     # make a DeferredList out of dList and check if they are all done.
    #     d = defer.DeferredList(dList)

    #     def result_handler(dlist):
    #         self.assertThat(
    #             self.snapshot_service.stopService(),
    #             succeeded(Always())
    #         )

    #         self.assertThat(self.db.get_all_localsnapshot_paths(), HasLength(len(files)))
    #         for (file, content) in zip(files, contents):
    #             mangled_filename = path2magic(file.asTextMode(encoding="utf-8").path)
    #             stored_snapshot = self.db.get_local_snapshot(mangled_filename, self.author)
    #             stored_content = stored_snapshot._get_synchronous_content()
    #             self.assertThat(stored_content, Equals(content))
    #             self.assertThat(stored_snapshot.parents_local, HasLength(0))

    #     d.addCallback(result_handler)

    # @given(content=binary())
    # def test_add_file_failures(self, content):
    #     foo = self.magic_path.child("foo")
    #     with foo.open("wb") as f:
    #         f.write(content)

    #     self.snapshot_service.startService()

    #     # try adding a string that represents the path
    #     with ExpectedException(TypeError,
    #                            "argument must be a FilePath"):
    #         self.snapshot_service.add_file(foo.path)

    #     # try adding a directory
    #     tmpdir = FilePath(self.mktemp())
    #     bar_dir = self.magic_path.child(tmpdir.basename())
    #     bar_dir.makedirs()

    #     with ExpectedException(ValueError,
    #                            "expected a file"):
    #         self.snapshot_service.add_file(bar_dir)


    #     # try adding a file outside the magic folder directory
    #     tmpfile = FilePath(self.mktemp())
    #     with tmpfile.open("wb") as f:
    #         f.write(content)

    #     with ExpectedException(ValueError,
    #                            "The path being added .*"):
    #         self.snapshot_service.add_file(tmpfile)

    #     self.assertThat(
    #         self.snapshot_service.stopService(),
    #         succeeded(Always())
    #     )

    # @given(content1=binary(min_size=1),
    #        content2=binary(min_size=1),
    #        filename=path_segments().map(lambda p: p.encode("utf-8")),
    # )
    # def test_add_a_file_twice(self, filename, content1, content2):
    #     foo = self.magic_path.child(filename)
    #     with foo.open("wb") as f:
    #         f.write(content1)

    #     self.snapshot_service.startService()
    #     self.snapshot_service.add_file(foo)

    #     foo_magicname = path2magic(foo.asTextMode('utf-8').path)
    #     stored_snapshot1 = self.db.get_local_snapshot(foo_magicname, self.author)

    #     with foo.open("wb") as f:
    #         f.write(content2)

    #     # it should use the previous localsnapshot as its parent.
    #     self.snapshot_service.add_file(foo)
    #     stored_snapshot2 = self.db.get_local_snapshot(foo_magicname, self.author)

    #     self.assertThat(
    #         self.snapshot_service.stopService(),
    #         succeeded(Always())
    #     )

    #     self.assertThat(stored_snapshot2.parents_local[0],
    #                     MatchesStructure(
    #                         content_path=Equals(stored_snapshot1.content_path)
    #                     )
    #     )
