import pytest

from labcheck.network import CampusNetwork, load_devices, load_plan


@pytest.fixture(scope="session")
def plan():
    return load_plan()


@pytest.fixture(scope="session")
def devices(plan):
    return load_devices(plan)


@pytest.fixture(scope="session")
def network(plan, devices):
    return CampusNetwork(plan, devices)


@pytest.fixture(scope="session")
def switches(plan, devices):
    return {d["name"]: devices[d["name"]] for d in plan["devices"] if d["model"].startswith("2960")}
