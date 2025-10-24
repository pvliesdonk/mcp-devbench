"""runtime_docker.py — Docker single-host runtime helpers (M0).

Responsibilities:
- Ensure a single warm default container exists and is running.
- Non-root by default (user 1000:1000); working dir /workspace.
- Respect DEFAULT_IMAGE_PULL policy (always|if-missing|never).
"""
from __future__ import annotations
import docker
from docker.errors import NotFound
from mcp_devbench.config import settings
from mcp_devbench.errors import TaxonomyError
from mcp_devbench.audit import audit
from mcp_devbench.state import upsert_container, find_by_alias


def _docker_client() -> docker.DockerClient:
    """Create a Docker client bound to DOCKER_HOST.

    M0 requirement: single-host runtime; no privileged/host access beyond socket.
    """
    return docker.DockerClient(base_url=settings.docker_host)


def _maybe_pull(cli: docker.DockerClient, image: str) -> None:
    """Ensure the image is available according to policy.

    - never: do nothing
    - if-missing: pull only if absent
    - always: always pull (may be slow)
    """
    policy = settings.default_image_pull
    if policy == "never":
        return
    try:
        if policy == "always":
            cli.images.pull(image)
        elif policy == "if-missing":
            try:
                cli.images.get(image)
            except NotFound:
                cli.images.pull(image)
        audit("image_available", image=image, policy=policy)
    except Exception as e:  # non-fatal
        audit("image_pull_warning", image=image, error=str(e))


def ensure_default_container() -> dict:
    """Ensure (create/start) the default container and return its info.

    Returns:
        Mapping with keys: id, alias, image, state ("running" or Docker status).

    Raises:
        TaxonomyError("Unavailable") if the container cannot be created.
    """
    alias = settings.default_alias
    cli = _docker_client()

    row = find_by_alias(alias)
    if row:
        try:
            c = cli.containers.get(row["id"])
            c.reload()
            if c.status != "running":
                c.start()
            audit("container_restored", alias=alias, id=row["id"])
            return {"id": row["id"], "alias": alias, "image": row["image"], "state": "running"}
        except Exception:
            audit("container_missing_recreate", alias=alias)

    _maybe_pull(cli, settings.default_image)

    try:
        created = cli.containers.create(
            image=settings.default_image,
            name=alias,
            tty=True,
            stdin_open=True,
            working_dir=settings.workspace_root,
            user="1000:1000",
            command=["bash", "-lc", "while :; do sleep 3600; done"],
            host_config=cli.api.create_host_config(auto_remove=False),
        )
        created.start()
        upsert_container(created.id, alias, settings.default_image, 1)
        audit("container_created", alias=alias, id=created.id, image=settings.default_image)
        return {"id": created.id, "alias": alias, "image": settings.default_image, "state": "running"}
    except Exception as e:  # pragma: no cover (network-specific paths)
        raise TaxonomyError("Unavailable", "failed to create default container", 503, {"err": str(e)})
