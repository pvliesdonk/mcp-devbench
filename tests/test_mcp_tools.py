from __future__ import annotations
import types
import pytest
from mcp_devbench import runtime_docker


def test_ensure_default_creates_when_missing(monkeypatch):
    called = {"created": False, "started": False}

    class MockImages:
        def get(self, _):
            raise runtime_docker.NotFound("", "")
        def pull(self, _):
            return None

    class MockContainer:
        status = "running"
        def start(self):
            called["started"] = True

    class MockContainers:
        def get(self, _):
            raise Exception("not found")
        def create(self, **kwargs):
            called["created"] = True
            return MockContainer()

    class MockAPI:
        def create_host_config(self, **_):
            return {}

    class MockClient:
        images = MockImages()
        containers = MockContainers()
        api = MockAPI()

    monkeypatch.setattr(runtime_docker, "_docker_client", lambda: MockClient())
    info = runtime_docker.ensure_default_container()
    assert info["alias"]
    assert called["created"] is True


@pytest.mark.parametrize("policy", ["never", "if-missing", "always"])
def test_pull_policy(monkeypatch, policy):
    s = runtime_docker.settings
    old = s.default_image_pull
    s.default_image_pull = policy  # type: ignore[attr-defined]

    class Dummy:
        def get(self, _):
            raise runtime_docker.NotFound("", "")
        def pull(self, _):
            return None

    class MockClient:
        images = Dummy()
        containers = types.SimpleNamespace(get=lambda _id: (_ for _ in ()).throw(Exception("nope")))
        api = types.SimpleNamespace(create_host_config=lambda **_: {})

    monkeypatch.setattr(runtime_docker, "_docker_client", lambda: MockClient())

    runtime_docker.ensure_default_container()
    s.default_image_pull = old
