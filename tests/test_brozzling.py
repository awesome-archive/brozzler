#!/usr/bin/env python
'''
test_brozzling.py - XXX explain

Copyright (C) 2016 Internet Archive

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''

import pytest
import brozzler
import logging
import os
import http.server
import threading
import argparse
import urllib
import json

args = argparse.Namespace()
args.log_level = logging.INFO
brozzler.cli._configure_logging(args)

WARCPROX_META_420 = {
    'stats': {
        'test_limits_bucket': {
            'total': {'urls': 0, 'wire_bytes': 0},
            'new': {'urls': 0, 'wire_bytes': 0},
            'revisit': {'urls': 0, 'wire_bytes': 0},
            'bucket': 'test_limits_bucket'
        }
    },
    'reached-limit': {'test_limits_bucket/total/urls': 0}
}

@pytest.fixture(scope='module')
def httpd(request):
    class RequestHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/420':
                self.send_response(420, 'Reached limit')
                self.send_header('Connection', 'close')
                self.send_header('Warcprox-Meta', json.dumps(WARCPROX_META_420))
                payload = b'request rejected by warcprox: reached limit test_limits_bucket/total/urls=0\n'
                self.send_header('Content-Type', 'text/plain;charset=utf-8')
                self.send_header('Content-Length', len(payload))
                self.end_headers()
                self.wfile.write(payload)
            else:
                super().do_GET()

    # SimpleHTTPRequestHandler always uses CWD so we have to chdir
    os.chdir(os.path.join(os.path.dirname(__file__), 'htdocs'))

    httpd = http.server.HTTPServer(('localhost', 0), RequestHandler)
    httpd_thread = threading.Thread(name='httpd', target=httpd.serve_forever)
    httpd_thread.start()

    def fin():
        httpd.shutdown()
        httpd.server_close()
        httpd_thread.join()
    request.addfinalizer(fin)

    return httpd

def test_httpd(httpd):
    '''
    Tests that our http server is working as expected, and that two fetches
    of the same url return the same payload, proving it can be used to test
    deduplication.
    '''
    payload1 = content2 = None
    url = 'http://localhost:%s/site1/file1.txt' % httpd.server_port
    with urllib.request.urlopen(url) as response:
        assert response.status == 200
        payload1 = response.read()
        assert payload1

    with urllib.request.urlopen(url) as response:
        assert response.status == 200
        payload2 = response.read()
        assert payload2

    assert payload1 == payload2

    url = 'http://localhost:%s/420' % httpd.server_port
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(url)
    assert excinfo.value.getcode() == 420

def test_aw_snap_hes_dead_jim():
    chrome_exe = brozzler.suggest_default_chrome_exe()
    with brozzler.Browser(chrome_exe=chrome_exe) as browser:
        with pytest.raises(brozzler.BrowsingException):
            browser.browse_page('chrome://crash')

def test_on_response(httpd):
    response_urls = []
    def on_response(msg):
        response_urls.append(msg['params']['response']['url'])

    chrome_exe = brozzler.suggest_default_chrome_exe()
    url = 'http://localhost:%s/site3/page.html' % httpd.server_port
    with brozzler.Browser(chrome_exe=chrome_exe) as browser:
        browser.browse_page(url, on_response=on_response)
        browser.browse_page(url)
    assert response_urls[0] == 'http://localhost:%s/site3/page.html' % httpd.server_port
    assert response_urls[1] == 'http://localhost:%s/site3/brozzler.svg' % httpd.server_port
    assert response_urls[2] == 'http://localhost:%s/favicon.ico' % httpd.server_port

def test_420(httpd):
    chrome_exe = brozzler.suggest_default_chrome_exe()
    url = 'http://localhost:%s/420' % httpd.server_port
    with brozzler.Browser(chrome_exe=chrome_exe) as browser:
        with pytest.raises(brozzler.ReachedLimit) as excinfo:
            browser.browse_page(url)
        assert excinfo.value.warcprox_meta == WARCPROX_META_420
