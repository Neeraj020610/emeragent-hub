import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.db_init import init_db
from app.core.security import hash_password, create_access_token
from app.models.user import User, Role
from app.config import settings
from app.services.otp.redis_store import redis_otp_store

TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Keep track of seeded user IDs
user_ids = {}


@pytest.fixture(autouse=True)
def ensure_test_redis():
    redis_otp_store.enable_test_mode()
    yield
    redis_otp_store.enable_test_mode()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    redis_otp_store.enable_test_mode()
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    init_db(db, seed_demo=True)

    admin_user = db.query(User).filter(User.email == settings.INITIAL_ADMIN_EMAIL).first()
    manager_role = db.query(Role).filter(Role.name == "MANAGER").first()
    member_role = db.query(Role).filter(Role.name == "MEMBER").first()

    manager = User(
        email="manager@emergent-hub.com",
        hashed_password=hash_password("ManagerPass123!"),
        full_name="Hub Operations Manager",
        role_id=manager_role.id,
        is_active=True,
        is_verified=True,
    )
    member = User(
        email="member@emergent-hub.com",
        hashed_password=hash_password("MemberPass123!"),
        full_name="Hub Team Member",
        role_id=member_role.id,
        is_active=True,
        is_verified=True,
    )
    db.add_all([manager, member])
    db.commit()
    db.refresh(manager)
    db.refresh(member)

    user_ids["admin"] = admin_user.id
    user_ids["manager"] = manager.id
    user_ids["member"] = member.id
    db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_token():
    return create_access_token({"sub": str(user_ids.get("admin", 1)), "email": settings.INITIAL_ADMIN_EMAIL, "role": "ADMIN"})


@pytest.fixture
def manager_token():
    return create_access_token({"sub": str(user_ids.get("manager", 2)), "email": "manager@emergent-hub.com", "role": "MANAGER"})


@pytest.fixture
def member_token():
    return create_access_token({"sub": str(user_ids.get("member", 3)), "email": "member@emergent-hub.com", "role": "MEMBER"})
