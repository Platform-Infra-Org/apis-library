"""Tests for GitClient's ssh_host construction."""

from tashtiot_apis_library.connectors.git.client import GitClient

BASE_URL = "https://bitbucket.example.com/rest/api/1.0"


def _client(**kwargs) -> GitClient:
    return GitClient(
        BASE_URL,
        "svc-account",
        "token",
        "PROJECT",
        "repo",
        **kwargs,
    )


def test_ssh_host_defaults_to_port_7995():
    client = _client()
    assert client.ssh_host == "bitbucket.example.com:7995"


def test_ssh_host_honours_ssh_port_override():
    client = _client(ssh_port=7999)
    assert client.ssh_host == "bitbucket.example.com:7999"
