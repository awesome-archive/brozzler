# vim: set sw=4 et:

import surt
import json
import logging
import brozzler

class Site:
    logger = logging.getLogger(__module__ + "." + __qualname__)

    def __init__(self, seed, id=None, scope=None, proxy=None,
        ignore_robots=False, time_limit=None, extra_headers=None,
        enable_warcprox_features=False, reached_limit=None):
        self.seed = seed
        self.id = id
        self.proxy = proxy
        self.ignore_robots = ignore_robots
        self.enable_warcprox_features = bool(enable_warcprox_features)
        self.extra_headers = extra_headers
        self.time_limit = time_limit
        self.reached_limit = reached_limit

        self.scope = scope or {}
        if not "surt" in scope:
            self.scope["surt"] = surt.GoogleURLCanonicalizer.canonicalize(surt.handyurl.parse(seed)).getURLString(surt=True, trailing_comma=True)

    def __repr__(self):
        return """Site(id={},seed={},scope={},proxy={},enable_warcprox_features={},ignore_robots={},extra_headers={},reached_limit={})""".format(
                self.id, repr(self.seed), repr(self.scope),
                repr(self.proxy), self.enable_warcprox_features,
                self.ignore_robots, self.extra_headers, self.reached_limit)

    def note_seed_redirect(self, url):
        new_scope_surt = surt.GoogleURLCanonicalizer.canonicalize(surt.handyurl.parse(url)).getURLString(surt=True, trailing_comma=True)
        if not new_scope_surt.startswith(self.scope["surt"]):
            self.logger.info("changing site scope surt from {} to {}".format(self.scope["surt"], new_scope_surt))
            self.scope["surt"] = new_scope_surt

    def note_limit_reached(self, e):
        self.logger.info("reached_limit e=%s", e)
        assert isinstance(e, brozzler.ReachedLimit)
        if self.reached_limit and self.reached_limit != e.warcprox_meta["reached-limit"]:
            self.logger.warn("reached limit %s but site had already reached limit %s",
                    e.warcprox_meta["reached-limit"], self.reached_limit)
        else:
            self.reached_limit = e.warcprox_meta["reached-limit"]

    def is_in_scope(self, url):
        try:
            hurl = surt.handyurl.parse(url)

            # XXX doesn't belong here probably (where? worker ignores unknown schemes?)
            if hurl.scheme != "http" and hurl.scheme != "https":
                return False

            surtt = surt.GoogleURLCanonicalizer.canonicalize(hurl).getURLString(surt=True, trailing_comma=True)
            return surtt.startswith(self.scope["surt"])
        except:
            self.logger.warn("""problem parsing url "{}" """.format(url))
            return False

    def to_dict(self):
        d = dict(vars(self))
        for k in vars(self):
            if k.startswith("_"):
                del d[k]
        return d

    def to_json(self):
        return json.dumps(self.to_dict(), separators=(',', ':'))

class Page:
    def __init__(self, url, id=None, site_id=None, hops_from_seed=0, outlinks=None, redirect_url=None):
        self.id = id
        self.site_id = site_id
        self.url = url
        self.hops_from_seed = hops_from_seed
        self._canon_hurl = None
        self.outlinks = outlinks
        self.redirect_url = redirect_url

    def __repr__(self):
        return """Page(url={},site_id={},hops_from_seed={})""".format(
                repr(self.url), self.site_id, self.hops_from_seed)

    def note_redirect(self, url):
        self.redirect_url = url

    def calc_priority(self):
        priority = 0
        priority += max(0, 10 - self.hops_from_seed)
        priority += max(0, 6 - self.canon_url().count("/"))
        return priority

    def canon_url(self):
        if self._canon_hurl is None:
            self._canon_hurl = surt.handyurl.parse(self.url)
            surt.GoogleURLCanonicalizer.canonicalize(self._canon_hurl)
        return self._canon_hurl.geturl()

    def to_dict(self):
        d = dict(vars(self))

        for k in vars(self):
            if k.startswith("_"):
                del d[k]

        if self.outlinks is not None and not isinstance(self.outlinks, list):
            outlinks = []
            outlinks.extend(self.outlinks)
            d["outlinks"] = outlinks

        return d

    def to_json(self):
        return json.dumps(self.to_dict(), separators=(',', ':'))
