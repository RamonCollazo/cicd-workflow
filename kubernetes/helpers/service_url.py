"""Service URL discovery for LoadBalancer-type services.

Uses `kubectl wait --for=jsonpath=...` (kubectl ≥1.23) to block on the
external-IP being assigned, replacing the manual retry loop the legacy
e2e_test.py used.
"""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)


def _kubectl(args: list[str], context: str, capture: bool = True) -> str:
    """Run a kubectl command and return stdout (text mode)."""
    cmd = ["kubectl", "--context", context, *args]
    logger.debug("running: %s", " ".join(cmd))
    result = subprocess.run(cmd, check=True, text=True, capture_output=capture)
    return result.stdout


def wait_for_loadbalancer(
    name: str,
    namespace: str,
    context: str,
    timeout: str = "60s",
) -> str:
    """Wait for a LoadBalancer service to receive an external IP, then return it."""
    logger.info("waiting for LB external IP on svc/%s in %s", name, namespace)
    _kubectl(
        [
            "wait",
            "--for=jsonpath={.status.loadBalancer.ingress[0].ip}",
            f"service/{name}",
            "-n",
            namespace,
            f"--timeout={timeout}",
        ],
        context=context,
        capture=False,
    )
    ip = _kubectl(
        [
            "get",
            "svc",
            name,
            "-n",
            namespace,
            "-o",
            "jsonpath={.status.loadBalancer.ingress[0].ip}",
        ],
        context=context,
    ).strip()
    if not ip:
        raise RuntimeError(f"svc/{name} in {namespace} has no LoadBalancer IP after wait")
    return ip


def get_service_port(name: str, namespace: str, context: str) -> int:
    """Return the first declared port of a Service."""
    port = _kubectl(
        [
            "get",
            "svc",
            name,
            "-n",
            namespace,
            "-o",
            "jsonpath={.spec.ports[0].port}",
        ],
        context=context,
    ).strip()
    if not port:
        raise RuntimeError(f"svc/{name} in {namespace} has no port[0]")
    return int(port)
