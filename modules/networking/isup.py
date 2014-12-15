import urllib

from tools.web import getJSON

def isup(url):
    """Determine if the given URL is up or not

    Argument:
    url -- the URL to check
    """

    o = urllib.parse.urlparse(url, "http")
    if o.netloc == "":
        o = urllib.parse.urlparse("http://" + url)
    if o.netloc != "":
        isup = getJSON("http://isitup.org/%s.json" % o.netloc)
        if "status_code" in isup and isup["status_code"] == 1:
            return isup["response_time"]

    return None
