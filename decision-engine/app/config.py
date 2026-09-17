"""Configuration for the Decision Engine.

Secrets and endpoints come from the environment. The gNB-to-edge mapping comes
from a YAML topology file, because it changes with every testbed.
"""

import os
from dataclasses import dataclass

import yaml

REQUIRED = object()


def _env(name, default=REQUIRED):
    value = os.getenv(name)
    if value:
        return value
    if default is REQUIRED:
        raise RuntimeError(f"{name} is not set. See README.md for the required environment.")
    return default


@dataclass(frozen=True)
class Settings:
    orchestrator_host: str
    orchestrator_user: str
    orchestrator_password: str
    orchestrator_org: str
    supi_of_interest: str
    service_name: str
    listen_port: int
    poll_interval: float
    migration_timeout: float
    request_timeout: float
    in_sync_status: str
    migration_log_path: str
    topology_path: str


def load_settings() -> Settings:
    return Settings(
        orchestrator_host=_env("ORCHESTRATOR_HOST"),
        orchestrator_user=_env("ORCHESTRATOR_USER"),
        orchestrator_password=_env("ORCHESTRATOR_PASSWORD"),
        orchestrator_org=_env("ORCHESTRATOR_ORG"),
        supi_of_interest=_env("SUPI_OF_INTEREST"),
        service_name=_env("SERVICE_NAME", "kserve_model"),
        listen_port=int(_env("LISTEN_PORT", "8880")),
        poll_interval=float(_env("POLL_INTERVAL_SECONDS", "0.5")),
        migration_timeout=float(_env("MIGRATION_TIMEOUT_SECONDS", "300")),
        request_timeout=float(_env("REQUEST_TIMEOUT_SECONDS", "30")),
        in_sync_status=_env("IN_SYNC_STATUS", "OKTOSTATUS_IN_SYNC"),
        migration_log_path=_env("MIGRATION_LOG_PATH", "/app/data/migration_times.json"),
        topology_path=_env("TOPOLOGY_PATH", "/app/config/topology.yaml"),
    )


def load_topology(path: str = None) -> dict:
    """Load the gNB-to-edge-site mapping.

    Returns a dict keyed by edge name, each entry carrying the UPF name, the
    gNB ID served by that edge, the tracking area, the orchestrator site ID
    the workload must be pinned to, and the edge-local Redis endpoint.
    """
    path = path or load_settings().topology_path
    with open(path) as handle:
        topology = yaml.safe_load(handle)

    edges = topology.get("edges")
    if not edges:
        raise ValueError(f"No 'edges' defined in {path}")

    required_keys = {"upf", "gnb_id", "tai", "site_id", "redis_host"}
    for name, entry in edges.items():
        missing = required_keys - set(entry)
        if missing:
            raise ValueError(f"Edge '{name}' in {path} is missing: {sorted(missing)}")

    return edges
