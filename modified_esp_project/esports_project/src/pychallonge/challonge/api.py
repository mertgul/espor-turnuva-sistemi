import decimal
import iso8601
try:
    # For Python 3.0 and later
    from urllib.parse import urlencode
    from urllib.request import Request, HTTPBasicAuthHandler, build_opener
    from urllib.error import HTTPError
except ImportError:
    # Fall back to Python 2's urllib2
    from urllib import urlencode
    from urllib2 import Request, HTTPBasicAuthHandler, build_opener, HTTPError
try:
    from xml.etree import cElementTree as ElementTree
except ImportError:
    from xml.etree import ElementTree


CHALLONGE_API_URL = "api.challonge.com/v1"

_credentials = {
    "user": None,
    "api_key": None,
}


class ChallongeException(Exception):
    pass


def set_credentials(username, api_key):
    """Set the challonge.com api credentials to use."""
    _credentials["user"] = username
    _credentials["api_key"] = api_key


def get_credentials():
    """Retrieve the challonge.com credentials set with set_credentials()."""
    return _credentials["user"], _credentials["api_key"]


def fetch(method, uri, params_prefix=None, **params):
    """Fetch the given uri and return the contents of the response."""
    params = urlencode(_prepare_params(params, params_prefix))
    binary_params = params.encode('ASCII')

    # build the HTTP request
    url = "https://%s/%s.xml" % (CHALLONGE_API_URL, uri)
    req = Request(url, binary_params)
    req.get_method = lambda: method

    # use basic authentication
    user, api_key = get_credentials()
    auth_handler = HTTPBasicAuthHandler()
    auth_handler.add_password(
        realm="Application",
        uri=req.get_full_url(),
        user=user,
        passwd=api_key
    )
    opener = build_opener(auth_handler)

    try:
        response = opener.open(req)
    except HTTPError as e:
        if e.code != 422:
            raise
        # wrap up application-level errors
        doc = ElementTree.parse(e).getroot()
        if doc.tag != "errors":
            raise
        errors = [e.text for e in doc]
        raise ChallongeException(*errors)

    return response


def fetch_and_parse(method, uri, params_prefix=None, **params):
    """Fetch the given uri and return the root Element of the response."""
    doc = ElementTree.parse(fetch(method, uri, params_prefix, **params))
    return _parse(doc.getroot())


def _parse(root):
    """Recursively convert an Element into python data types"""
    if root.tag == "nil-classes":
        return []
    elif root.get("type") == "array":
        return [_parse(child) for child in root]

    d = {}
    for child in root:
        type = child.get("type") or "string"

        if child.get("nil"):
            value = None
        elif type == "boolean":
            value = True if child.text.lower() == "true" else False
        elif type == "dateTime":
            value = iso8601.parse_date(child.text)
        elif type == "decimal":
            value = decimal.Decimal(child.text)
        elif type == "integer":
            value = int(child.text)
        else:
            value = child.text

        d[child.tag] = value
    return d


def _prepare_params(dirty_params, prefix=None):
    """Prepares parameters to be sent to challonge.com.

    The `prefix` can be used to convert parameters with keys that
    look like ("name", "url", "tournament_type") into something like
    ("tournament[name]", "tournament[url]", "tournament[tournament_type]"),
    which is how challonge.com expects parameters describing specific
    objects.

    """
    params = {}
    for k, v in dirty_params.items():
        if hasattr(v, "isoformat"):
            v = v.isoformat()
        elif isinstance(v, bool):
            # challonge.com only accepts lowercase true/false
            v = str(v).lower()

        if prefix:
            params["%s[%s]" % (prefix, k)] = v
        else:
            params[k] = v

    return params
