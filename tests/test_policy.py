"""Traffic policy checks: for each case in design/lab-plan.json
("policy_tests"), run the packet through R1's real ACLs (read from
configs/R1.txt) and, for SSH to a network device, through that device's
VTY access list. The expected result must match.

This models layer 3 policy only. The same cases are listed in
docs/VERIFICATION.md so they can be tested for real in Packet Tracer.
"""

import pytest

from labcheck.network import load_plan

POLICY_TESTS = load_plan()["policy_tests"]


def test_policy_ids_are_unique():
    ids = [case["id"] for case in POLICY_TESTS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("case", POLICY_TESTS, ids=[f"{c['id']} {c['desc']}" for c in POLICY_TESTS])
def test_policy(network, case):
    decision = network.evaluate_policy(case)
    explanation = "\n  ".join(decision.reasons)
    assert decision.action == case["expect"], f"{case['id']} {case['desc']}\n  {explanation}"


def test_policy_covers_every_acl_line(network):
    """Every permit/deny line in R1's ACLs must be the deciding line for at
    least one policy case on that packet's real path through R1, so no rule
    goes untested."""
    from labcheck.network import acl_entries

    used = set()
    for case in POLICY_TESTS:
        used.update(network.evaluate_policy(case).matched)

    unexercised = []
    for acl_name in network.router.named_acls:
        for entry in acl_entries(network.router, acl_name):
            if (acl_name, entry.text) not in used:
                unexercised.append(f"{acl_name}: {entry.text}")
    assert not unexercised, "ACL lines no policy case reaches:\n  " + "\n  ".join(unexercised)
