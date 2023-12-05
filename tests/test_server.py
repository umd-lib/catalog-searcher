from multiprocessing import Process

import psutil
import pytest
import requests
from click.testing import CliRunner

from catalog_searcher.server import run


class ServerProcess(Process):
    def run(self) -> None:
        runner = CliRunner()
        # listen on all IPv4 addresses ("0.0.0.0"), using a random port (":0")
        runner.invoke(run, ('--listen', '0.0.0.0:0'))

    @property
    def port(self):
        return find_port(self.pid)


def find_port(pid: int) -> int | None:
    """Find the port number that the process with the given PID is listening on. If
    there is no suitable port found, returns None. If there is more than one port,
    returns the first one."""
    process = psutil.Process(pid)
    # get the listening connections; this is similar to running `lsof -iTCP -sTCP:LISTEN`
    connections = [conn for conn in process.connections() if conn.status == psutil.CONN_LISTEN]
    if len(connections) == 0:
        return None
    # assume it is the first listening connection
    return connections[0].laddr.port


@pytest.fixture
def server():
    process = ServerProcess()
    process.start()
    # wait for the server to start up
    while process.port is None:
        process.join(0.1)

    yield process

    # clean up after ourselves
    process.kill()


def test_root(server):
    response = requests.get(f'http://localhost:{server.port}/')
    assert response.json() == {'status': 'ok'}


def test_ping(server):
    response = requests.get(f'http://localhost:{server.port}/ping')
    assert response.json() == {'status': 'ok'}


@pytest.mark.skip(reason='mocking external URL via httpretty is not currently functioning')
def test_search(shared_datadir, register_search_url, server):
    register_search_url(body=(shared_datadir / 'alma_response.xml').read_text())
    response = requests.get(f'http://localhost:{server.port}/search', params={'q': 'maryland'})
    
    assert response.ok
