import http.client
import threading

import pytest

from printpipe.web import create_app, create_server


@pytest.mark.parametrize('host,origin,expected', [
    ('foreign.invalid:{port}', 'http://foreign.invalid:{port}', 403),
    ('127.0.0.1:{port}', 'http://foreign.invalid:{port}', 403),
    ('127.0.0.1:{port}', 'null', 403),
    ('127.0.0.1:{port}', None, 200),
    ('localhost:{port}', 'http://localhost:{port}', 200),
])
def test_prp17_http_validates_host_and_origin(tmp_path, host, origin, expected):
    server = create_server(create_app(runs_dir=tmp_path / 'runs'), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
    try:
        headers = {'Host': host.format(port=server.server_port)}
        if origin is not None:
            headers['Origin'] = origin.format(port=server.server_port)
        connection.request('GET', '/health', headers=headers)
        response = connection.getresponse()
        assert response.status == expected
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join()
