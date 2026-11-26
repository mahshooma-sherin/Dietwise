import os
import tempfile

os.environ["DIETWISE_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.data_loader import get_store  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas import PlanRequest  # noqa: E402


@pytest.fixture(scope="session")
def store():
    return get_store()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def make_req(**kw):
    base = dict(budget=60, food_preference="non_vegetarian", nutrition_goal="balanced", days=4, people=2, seed=1)
    base.update(kw)
    return PlanRequest(**base)
