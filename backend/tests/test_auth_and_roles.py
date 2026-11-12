def test_admin_login_success(client):
    payload = {
        "email": "admin@emergent-hub.com",
        "password": "EmergentAdmin2026!",
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "ADMIN"
    assert data["email"] == "admin@emergent-hub.com"


def test_login_invalid_password(client):
    payload = {
        "email": "admin@emergent-hub.com",
        "password": "WrongPassword123!",
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_auth_me_authenticated(client, admin_token):
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "admin@emergent-hub.com"


def test_unauthenticated_request_rejected(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "token is missing" in response.json()["detail"].lower()


def test_role_permission_enforcement_member_forbidden(client, member_token):
    # Member attempts to create a user (ADMIN-only endpoint)
    payload = {
        "email": "intruder@emergent-hub.com",
        "password": "Password123!",
        "full_name": "Intruder User",
        "role_id": 3,
    }
    response = client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


def test_admin_can_create_user(client, admin_token):
    payload = {
        "email": "engineer.new@emergent-hub.com",
        "password": "SecurePassword2026!",
        "full_name": "New AI Engineer",
        "role_id": 3,
        "is_active": True,
    }
    response = client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "engineer.new@emergent-hub.com"


def test_api_validation_invalid_email(client, admin_token):
    payload = {
        "email": "not-an-email-address",
        "password": "Password123!",
        "full_name": "Invalid Email User",
        "role_id": 3,
    }
    response = client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 422  # Pydantic validation error
