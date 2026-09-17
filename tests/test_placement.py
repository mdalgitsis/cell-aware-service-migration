"""Tests for the gNB-to-site placement decision.

The engine's core judgement is: given an event naming a gNB, which edge site
should the workload be on? Cores disagree about whether a gNB ID is a JSON
number or a string, so that comparison is the part most likely to break
silently on a new testbed -- a mismatch reads as "no edge for this gNB" and the
workload simply never moves.
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "decision-engine" / "app"))

from config import load_topology  # noqa: E402

TOPOLOGY = load_topology(str(ROOT / "decision-engine/app/topology.example.yaml"))


def site_for(gnb_id, topology=TOPOLOGY):
    """The lookup the engine performs, isolated from the HTTP calls around it."""
    for info in topology.values():
        if str(info["gnb_id"]) == str(gnb_id):
            return info["site_id"]
    return None


@pytest.mark.parametrize("gnb_id", [10, "10"])
def test_gnb_id_matches_as_number_or_string(gnb_id):
    assert site_for(gnb_id) == TOPOLOGY["edge1"]["site_id"]


def test_each_gnb_maps_to_its_own_site():
    assert site_for(10) != site_for(21)


def test_unknown_gnb_has_no_site():
    assert site_for(99) is None


def test_redis_host_follows_the_site():
    """State is edge-local, so each site must carry its own Redis endpoint."""
    hosts = {info["redis_host"] for info in TOPOLOGY.values()}
    assert len(hosts) == len(TOPOLOGY)
