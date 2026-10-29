import os
os.environ["DATABASE_URL"] = "sqlite:///./test_dkl_chat.db"
os.environ["SECRET_KEY"] = "test-secret-that-is-long-enough-123"
os.environ["INVITE_CODES"] = "ALPHA,BETA"
from fastapi.testclient import TestClient
import pytest
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_db():
    app.state.limiter._storage.reset()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

