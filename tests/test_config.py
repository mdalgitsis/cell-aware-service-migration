"""Tests for the Decision Engine's configuration loading.

These cover the two ways a deployment goes wrong quietly: starting with a
missing setting and falling back to something plausible, and loading a
topology table that is missing a field the placement logic will later need.
"""

import pathlib
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "decision-engine" / "app"))

from config import load_settings, load_topology  # noqa: E402

COMPLETE_ENV = {
    "ORCHESTRATOR_HOST": "orchestrator.example.com",
    "ORCHESTRATOR_USER": "you@example.com",
    "ORCHESTRATOR_PASSWORD": "not-a-real-password",
    "ORCHESTRATOR_ORG": "00000000-0000-0000-0000-000000000000",
    "SUPI_OF_INTEREST": "001010000000000",
}


@pytest.fixture
def env(monkeypatch):
    for key, value in COMPLETE_ENV.items():
        monkeypatch.setenv(key, value)
    return monkeypatch


def test_settings_load_from_environment(env):
    settings = load_settings()
    assert settings.orchestrator_host == "orchestrator.example.com"
    assert settings.supi_of_interest == "001010000000000"
    # Unset optional settings fall back to documented defaults.
    assert settings.listen_port == 8880
    assert settings.service_name == "kserve_model"


@pytest.mark.parametrize("missing", sorted(COMPLETE_ENV))
def test_required_settings_have_no_default(env, missing):
    """Every required setting must fail loudly rather than be guessed."""
    env.delenv(missing)
    with pytest.raises(RuntimeError, match=missing):
        load_settings()


def test_empty_string_is_treated_as_unset(env):
    env.setenv("ORCHESTRATOR_PASSWORD", "")
    with pytest.raises(RuntimeError, match="ORCHESTRATOR_PASSWORD"):
        load_settings()


def test_example_topology_is_valid():
    edges = load_topology(str(ROOT / "decision-engine/app/topology.example.yaml"))
    assert set(edges) == {"edge1", "edge2"}
    assert edges["edge2"]["gnb_id"] == 21


def test_chart_default_topology_matches_the_schema(tmp_path):
    """The chart ships its own topology; it must satisfy the same loader."""
    values = yaml.safe_load((ROOT / "charts/decision-engine/values.yaml").read_text())
    path = tmp_path / "topology.yaml"
    path.write_text(yaml.safe_dump({"edges": values["topology"]["edges"]}))
    assert load_topology(str(path))


def test_incomplete_edge_is_rejected(tmp_path):
    path = tmp_path / "topology.yaml"
    path.write_text(yaml.safe_dump({"edges": {"edge1": {"upf": "upf1", "gnb_id": 10}}}))
    with pytest.raises(ValueError, match="site_id"):
        load_topology(str(path))


def test_empty_topology_is_rejected(tmp_path):
    path = tmp_path / "topology.yaml"
    path.write_text(yaml.safe_dump({"edges": {}}))
    with pytest.raises(ValueError, match="No 'edges'"):
        load_topology(str(path))
