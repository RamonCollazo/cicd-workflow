"""Subprocess helpers for k3d, kubectl, and docker.

All commands use list-form arguments (no shell=True, no cmd.split()) and
pass --context explicitly to kubectl so commands always target the
intended cluster. The cluster fixture is responsible for ensuring the
kubeconfig has a context entry for the cluster (see merge_kubeconfig).
Readiness uses `kubectl rollout status`, which blocks on the Deployment
object directly and avoids the `kubectl wait pods --all` race (no
resources at the instant of call).
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _run(
    cmd: list[str],
    *,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a command in list form. Always text mode, never shell."""
    logger.debug("running: %s", " ".join(cmd))
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=capture,
    )


def cluster_exists(name: str) -> bool:
    """Return True if a k3d cluster with this exact name exists."""
    result = _run(
        ["k3d", "cluster", "list", "-o", "json"],
        capture=True,
    )
    clusters = json.loads(result.stdout or "[]")
    return any(c.get("name") == name for c in clusters)


def create_cluster(name: str, config_path: Path) -> None:
    """Create a k3d cluster from the given config file."""
    logger.info("creating k3d cluster %r from %s", name, config_path)
    _run(["k3d", "cluster", "create", "--config", str(config_path)])


def delete_cluster(name: str) -> None:
    """Delete a k3d cluster. Idempotent — never raises if missing."""
    logger.info("deleting k3d cluster %r", name)
    _run(["k3d", "cluster", "delete", name], check=False)


def merge_kubeconfig(name: str) -> None:
    """Ensure ~/.kube/config has the context for this cluster.

    `k3d cluster create` merges the kubeconfig automatically, but when the
    cluster was created by a prior session and is being reused (or when the
    kubeconfig has been wiped between sessions), the context is missing and
    every kubectl --context call fails with "context does not exist".
    Call this after we know a cluster exists, before any kubectl invocation.
    """
    logger.info("merging kubeconfig for k3d cluster %r", name)
    _run(["k3d", "kubeconfig", "merge", name, "--kubeconfig-merge-default"])


def build_image(tag: str, dockerfile: Path, context: Path) -> None:
    """Build a Docker image."""
    logger.info("building image %s from %s", tag, dockerfile)
    _run(
        [
            "docker",
            "build",
            "-t",
            tag,
            "-f",
            str(dockerfile),
            str(context),
        ]
    )


def import_image(tag: str, cluster: str) -> None:
    """Load a local Docker image into a k3d cluster's nodes."""
    logger.info("importing image %s into k3d cluster %r", tag, cluster)
    _run(["k3d", "image", "import", tag, "-c", cluster])


def apply_kustomize(path: Path, context: str) -> None:
    """kubectl apply -k <path> --context <context>."""
    logger.info("applying kustomize at %s", path)
    _run(["kubectl", "--context", context, "apply", "-k", str(path)])


def wait_for_rollout(
    deployment: str,
    namespace: str,
    context: str,
    timeout: str = "120s",
) -> None:
    """Block until a Deployment finishes rolling out.

    Uses `kubectl rollout status` rather than `kubectl wait pods --all`,
    which races against pod creation and errors out with
    `no matching resources found` when invoked too soon after apply.
    """
    logger.info("waiting for rollout of deployment/%s in %s", deployment, namespace)
    _run(
        [
            "kubectl",
            "--context",
            context,
            "rollout",
            "status",
            f"deployment/{deployment}",
            "-n",
            namespace,
            f"--timeout={timeout}",
        ]
    )
