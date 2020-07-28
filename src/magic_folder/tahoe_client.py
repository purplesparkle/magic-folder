# Copyright 2020 Least Authority TFA GmbH
# See COPYING for details.

import json

from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
)

from twisted.web.http import (
    OK,
    CREATED,
)

from hyperlink import (
    DecodedURL,
)

from treq.client import (
    HTTPClient,
)

import attr


def _request(http_client, method, url, **kwargs):
    """
    Issue a request with the given parameters.

    :param HTTPClient http_client: The HTTP client to use.

    :param bytes method: The HTTP request method.

    :param DecodedURL url: The HTTP request path.

    :param **kwargs: Any additional keyword arguments to pass along to
        ``HTTPClient``.
    """
    return http_client.request(
        method,
        url.to_uri().to_text().encode("ascii"),
        **kwargs
    )


@attr.s(frozen=True)
class TahoeAPIError(Exception):
    """
    A Tahoe-LAFS HTTP API returned a failure code.
    """
    code = attr.ib()
    body = attr.ib()

    def __repr__(self):
        return "<TahoeAPIError code={} body={!r}>".format(
            self.code,
            self.body,
        )

    def __str__(self):
        return repr(self)


@inlineCallbacks
def _get_content_check_code(acceptable_codes, res):
    """
    Check that the given response's code is acceptable and read the response
    body.

    :raise TahoeAPIError: If the response code is not acceptable.

    :return Deferred[bytes]: If the response code is acceptable, a Deferred
        which fires with the response body.
    """
    body = yield res.content()
    if res.code not in acceptable_codes:
        raise TahoeAPIError(res.code, body)
    returnValue(body)


@attr.s
class TahoeClient(object):
    """
    An object that knows how to call a particular tahoe client's
    WebAPI.

    :ivar DecodedURL url: The root of the Tahoe-LAFS client node's HTTP API.

    :ivar HTTPClient http_client: The client to use to make HTTP requests.
    """

    url = attr.ib(validator=attr.validators.instance_of(DecodedURL))
    http_client = attr.ib(validator=attr.validators.instance_of(HTTPClient))

    @inlineCallbacks
    def create_immutable_directory(self, directory_data):
        """
        Creates a new immutable directory in Tahoe.

        :param directory_data: a dict contain JSON-able data in a
            shape suitable for the `/uri?t=mkdir-immutable` Tahoe
            API. See
            https://tahoe-lafs.readthedocs.io/en/tahoe-lafs-1.12.1/frontends/webapi.html#creating-a-new-directory

        :returns: a capability-string
        """
        post_uri = self.url.replace(
            path=(u"uri",),
            query=[(u"t", u"mkdir-immutable")],
        )
        res = yield _request(
            self.http_client,
            b"POST",
            post_uri,
            data=json.dumps(directory_data),
        )
        capability_string = yield _get_content_check_code({OK, CREATED}, res)
        returnValue(
            capability_string.strip()
        )

    @inlineCallbacks
    def create_immutable(self, producer):
        """
        Creates a new immutable in Tahoe.

        :param producer: can take anything that treq's data= method to
            treq.request allows which is currently: str, file-like or
            IBodyProducer. See
            https://treq.readthedocs.io/en/release-20.3.0/api.html#treq.request

        :return Deferred[bytes]: A Deferred which fires with the capability
            string for the new immutable object.
        """
        put_uri = self.url.child(u"uri")
        res = yield _request(
            self.http_client,
            b"PUT",
            put_uri,
            data=producer,
        )
        capability_string = yield _get_content_check_code({CREATED}, res)
        returnValue(
            capability_string.strip()
        )

    @inlineCallbacks
    def create_mutable_directory(self):
        """
        Create a new mutable directory in Tahoe.

        :return Deferred[bytes]: The write capability string for the new
            directory.
        """
        post_uri = self.url.replace(
            path=(u"uri",),
            query=[(u"t", u"mkdir")],
        )
        response = yield _request(
            self.http_client,
            b"POST",
            post_uri,
        )
        # Response code should probably be CREATED but it seems to be OK
        # instead.  Not sure if this is the real Tahoe-LAFS behavior or an
        # artifact of the test double.
        capability_string = yield _get_content_check_code({OK, CREATED}, response)
        returnValue(capability_string)

    @inlineCallbacks
    def download_capability(self, cap):
        """
        Retrieve the raw data for a capability from Tahoe

        :param cap: a capability-string

        :returns: bytes
        """
        get_uri = self.url.replace(
            path=(u"uri",),
            query=[(u"uri", cap.decode("ascii"))],
        )
        res = yield _request(
            self.http_client,
            b"GET",
            get_uri,
        )
        data = yield _get_content_check_code({OK}, res)
        returnValue(data)

    @inlineCallbacks
    def stream_capability(self, cap, filelike):
        """
        Retrieve the raw data for a capability from Tahoe

        :param cap: a capability-string

        :param filelike: a writable file object. `.write` will be
            called on it an arbitrary number of times, but no other
            methods (that is, it won't be closed).

        :returns: Deferred that fires with `None`
        """
        get_uri = self.url.replace(
            path=(u"uri",),
            query=[(u"uri", cap.decode("ascii"))],
        )
        res = yield self.http_client.get(get_uri.to_text())
        if res.code != OK:
            raise TahoeAPIError(res.code, None)
        yield res.collect(filelike.write)


def create_tahoe_client(url, http_client):
    """
    Create a new TahoeClient instance that is speaking to a particular
    Tahoe node.

    :param DecodedURL url: the base URL of the Tahoe instance

    :param http_client: a Treq HTTP client

    :returns: a TahoeClient instance
    """
    return TahoeClient(
        url=url,
        http_client=http_client,
    )
