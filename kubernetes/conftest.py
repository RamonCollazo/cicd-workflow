"""Pytest configuration and fixtures for the Study Tracker e2e suite.

Fixture chain (session-scoped unless noted):

    cluster -> deployed_app -> api_url, web_url -> http -> tests
                                                   unique_tag (function-scoped) -> tests

CLI options:
    --no-cluster-setup   Assume cluster + app are already running. Fixtures
                         skip create/build/import/apply and just resolve URLs.
    --keep-cluster       Don't delete the cluster on session teardown.
    --cluster-name NAME  Override the default cluster name.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from lib import cluster as cluster_lib
from lib import service_url

logger = logging.getLogger(__name__)

KUBE_DIR = Path(__file__).resolve().parent
REPO_ROOT = KUBE_DIR.parent
NAMESPACE = "study-tracker"
API_DEPLOYMENT = "dev-study-tracker-api"
WEB_DEPLOYMENT = "dev-study-tracker-web"
API_SERVICE = "dev-study-tracker-api"
WEB_SERVICE = "dev-study-tracker-web"
API_IMAGE = "study-tracker-api:dev"
WEB_IMAGE = "study-tracker-web:dev"
KUSTOMIZE_PATH = KUBE_DIR / "manifests" / "dev"
K3D_CONFIG_PATH = KUBE_DIR / "k3d-config.yaml"
DEFAULT_CLUSTER = "study-tracker-cluster"
DEFAULT_TIMEOUT = 5  # seconds, applied per request


# --------------------------------------------------------------------- #
# CLI options
# --------------------------------------------------------------------- #


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--no-cluster-setup",
        action="store_true",
        default=False,
        help="Assume cluster and app are already deployed; skip create/build/apply.",
    )
    parser.addoption(
        "--keep-cluster",
        action="store_true",
        default=False,
        help="Don't delete the k3d cluster on session teardown.",
    )
    parser.addoption(
        "--cluster-name",
        action="store",
        default=DEFAULT_CLUSTER,
        help=f"k3d cluster name (default: {DEFAULT_CLUSTER}).",
    )


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #


class _TimeoutSession(requests.Session):
    """A requests Session that applies a default per-request timeout."""

    def __init__(self, default_timeout: float = DEFAULT_TIMEOUT) -> None:
        super().__init__()
        self._default_timeout = default_timeout

    def request(self, method, url, **kwargs):  # type: ignore[override]
        kwargs.setdefault("timeout", self._default_timeout)
        return super().request(method, url, **kwargs)


# --------------------------------------------------------------------- #
# Session-scoped fixtures
# --------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def cluster_name(request: pytest.FixtureRequest) -> str:
    return request.config.getoption("--cluster-name")


@pytest.fixture(scope="session")
def kube_context(cluster_name: str) -> str:
    """k3d names contexts as `k3d-<cluster-name>`."""
    return f"k3d-{cluster_name}"


@pytest.fixture(scope="session")
def cluster(
    request: pytest.FixtureRequest,
    cluster_name: str,
) -> Iterator[str]:
    """Ensure a k3d cluster exists for the test session.

    Behaviour:
        --no-cluster-setup  Don't create or delete; just yield the name.
        --keep-cluster      Create if missing, but don't delete on teardown.
        (default)           Create if missing, delete on teardown.
    """
    skip_setup = request.config.getoption("--no-cluster-setup")
    keep = request.config.getoption("--keep-cluster")

    created_here = False
    if skip_setup:
        if not cluster_lib.cluster_exists(cluster_name):
            pytest.exit(
                f"--no-cluster-setup given but cluster {cluster_name!r} does not exist",
                returncode=2,
            )
        logger.info("--no-cluster-setup: using existing cluster %r", cluster_name)
    elif cluster_lib.cluster_exists(cluster_name):
        logger.info("cluster %r already exists; reusing", cluster_name)
    else:
        cluster_lib.create_cluster(cluster_name, K3D_CONFIG_PATH)
        created_here = True

    yield cluster_name

    if not skip_setup and not keep and created_here:
        cluster_lib.delete_cluster(cluster_name)


@pytest.fixture(scope="session")
def deployed_app(
    request: pytest.FixtureRequest,
    cluster: str,
    kube_context: str,
) -> str:
    """Build images, import them into k3d, apply kustomize, wait for rollout.

    Skipped (no-op) when --no-cluster-setup is set.
    """
    if request.config.getoption("--no-cluster-setup"):
        logger.info("--no-cluster-setup: skipping build/import/apply")
        return cluster

    api_app = REPO_ROOT / "apps" / "study-tracker" / "api"
    web_app = REPO_ROOT / "apps" / "study-tracker" / "web"

    cluster_lib.build_image(API_IMAGE, api_app / "Dockerfile", api_app)
    cluster_lib.build_image(WEB_IMAGE, web_app / "Dockerfile", web_app)

    cluster_lib.import_image(API_IMAGE, cluster)
    cluster_lib.import_image(WEB_IMAGE, cluster)

    cluster_lib.apply_kustomize(KUSTOMIZE_PATH, kube_context)

    cluster_lib.wait_for_rollout(API_DEPLOYMENT, NAMESPACE, kube_context)
    cluster_lib.wait_for_rollout(WEB_DEPLOYMENT, NAMESPACE, kube_context)

    return cluster


@pytest.fixture(scope="session")
def api_url(deployed_app: str, kube_context: str) -> str:  # noqa: ARG001
    ip = service_url.wait_for_loadbalancer(API_SERVICE, NAMESPACE, kube_context)
    port = service_url.get_service_port(API_SERVICE, NAMESPACE, kube_context)
    url = f"http://{ip}:{port}"
    logger.info("api_url=%s", url)
    return url


@pytest.fixture(scope="session")
def web_url(deployed_app: str, kube_context: str) -> str:  # noqa: ARG001
    ip = service_url.wait_for_loadbalancer(WEB_SERVICE, NAMESPACE, kube_context)
    port = service_url.get_service_port(WEB_SERVICE, NAMESPACE, kube_context)
    url = f"http://{ip}:{port}"
    logger.info("web_url=%s", url)
    return url


@pytest.fixture(scope="session")
def http() -> Iterator[_TimeoutSession]:
    """A requests.Session with retry on transient GET failures + default timeout."""
    session = _TimeoutSession()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[502, 503, 504],
        allowed_methods=frozenset({"GET", "HEAD"}),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    try:
        yield session
    finally:
        session.close()


# --------------------------------------------------------------------- #
# Function-scoped fixtures
# --------------------------------------------------------------------- #


@pytest.fixture()
def unique_tag() -> str:
    """A short, unique tag per test, used to isolate state between runs."""
    return f"e2e-{uuid.uuid4().hex[:8]}"
