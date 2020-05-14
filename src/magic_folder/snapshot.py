# Copyright 2020 Least Authority TFA GmbH
# See COPYING for details.

"""
Functions and types that implement snapshots
"""
from __future__ import print_function

import time
import json

from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
)

from .common import (
    get_node_url,
)

from twisted.web.client import (
    Agent,
    readBody,
)

from twisted.web.http import (
    OK,
    CREATED,
)

from treq.client import (
    HTTPClient,
)

from hyperlink import (
    DecodedURL,
)

from .common import (
    bad_response,
)


# version of the snapshot scheme
SNAPSHOT_VERSION = 1

@inlineCallbacks
def tahoe_put_immutable(nodeurl, filepath, treq):
    """
    :param unicode nodeurl: The web endpoint of the Tahoe-LAFS client
        associated with the magic-folder client.
    :param unicode filepath: The file path that needs to be stored into
        the grid.
    :param HTTPClient treq: An ``HTTPCLient`` or similar object to use to
        make the queries.
    :return Deferred[unicode]: The readcap associated with the newly created
        unlinked file.
    """
    node_url = DecodedURL.from_text(unicode(nodeurl, 'utf-8'))
    url = node_url.child(
        u"uri",
    ).add(
        u"format",
        u"CHK",
    )

    # XXX: check whether we need to set any headers.
    put_uri = url.to_uri().to_text().encode("ascii")
    with open(str(filepath), "rb") as file:
        data = file.read()

    response = yield treq.put(put_uri, data)
    if response.code == OK or response.code == CREATED:
        result = yield readBody(response)
        returnValue(result)
    else:
        raise Exception("Error response PUT {} - {}".format(put_uri, response))

@inlineCallbacks
def tahoe_create_snapshot_dir(nodeurl, content, parents, timestamp, treq):
    """
    :param unicode content: readcap for the content.
    :param [unicode] parents: List of parent snapshot caps
    :param unicode author: readcap that represents the author pubkey
    :param integer timestamp: POSIX timestamp that represents the creation time
    :return Deferred[unicode]: The readcap associated with the newly created
        snapshot.
    """

    # dict that would be serialized to JSON
    body = \
    {
        u"content": [ "filenode", { u"ro_uri": content,
                                    u"metadata": { } } ],
        u"version": [ "filenode", { u"ro_uri": str(SNAPSHOT_VERSION),
                                    u"metadata": { } } ],
        u"timestamp": [ "filenode", { u"ro_uri": str(timestamp),
                                      u"metadata": { } } ],
    }

    if parents != []:
        body[u"parents"] = parents

    body_json = json.dumps(body)

    node_url = DecodedURL.from_text(unicode(nodeurl, 'utf-8'))

    # POST /uri?t=mkdir-immutable
    url = node_url.child(
        u"uri",
    ).add(
        u"t",
        u"mkdir-immutable"
    )

    post_uri = url.to_uri().to_text().encode("ascii")
    response = yield treq.post(post_uri, body_json)
    if response.code != OK:
        returnValue((yield bad_response(url, response)))

    result = yield readBody(response)
    returnValue(result)

@inlineCallbacks
def _store_file_immutable(nodeurl, filepath):

    from twisted.internet import reactor
    treq = HTTPClient(Agent(reactor))
    rocap = yield tahoe_put_immutable(nodeurl, filepath, treq)

    returnValue(rocap)

@inlineCallbacks
def snapshot_create(node_directory, filepath, parents):
    """
    Create a snapshot, given a file contents of a named file,
    parent snapshots, author's identity and signature.

    :param unicode filepath: The file path whose snapshot is being created

    :param [unicode] parents: List of parent snapshots of the current snapshot
        (read-caps of parent snapshots)

    :return Deferred[unicode]: Snapshot read-only cap is returned on success.
        Otherwise an appropriate exception is raised.
    """

    nodeurl = get_node_url(node_directory)

    # - store the file content and get the immutable cap (content)
    #     PUT /uri?format=CHK
    content_cap = yield _store_file_immutable(nodeurl, filepath)

    now = time.time()

    # - HTTP POST mkdir-immutable
    from twisted.internet import reactor
    treq = HTTPClient(Agent(reactor))
    snapshot_cap = yield tahoe_create_snapshot_dir(nodeurl,
                                                   content_cap,
                                                   parents,
                                                   now,
                                                   treq)

    returnValue(snapshot_cap)
