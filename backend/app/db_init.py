from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import Role, User
from app.models.otp import MailboxAccount
from app.models.account import EmergentAccount, AccountConnection
from app.models.credit import CreditSnapshot
from app.models.project import Project
from app.models.job import BuildWorker
from app.core.security import hash_password
from app.config import settings


def init_db(db: Session, seed_demo: bool = False) -> None:
    # 1. Seed Roles
    roles_data = [
        ("ADMIN", "Full platform access and management privileges", "all:manage"),
        ("MANAGER", "Manage authorized accounts, projects, and jobs", "accounts:view,projects:manage,jobs:manage"),
        ("MEMBER", "View assigned accounts and submit authorized build requests", "accounts:view,jobs:submit"),
    ]

    for role_name, desc, perms in roles_data:
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            role = Role(name=role_name, description=desc, permissions=perms)
            db.add(role)
    db.commit()

    admin_role = db.query(Role).filter(Role.name == "ADMIN").first()

    # 2. Seed Initial Admin User if none exists
    admin_user = db.query(User).filter(User.email == settings.INITIAL_ADMIN_EMAIL).first()
    if not admin_user and admin_role:
        admin_user = User(
            email=settings.INITIAL_ADMIN_EMAIL,
            hashed_password=hash_password(settings.INITIAL_ADMIN_PASSWORD),
            full_name="Hub System Administrator",
            role_id=admin_role.id,
            is_active=True,
            is_verified=True,
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

    # 3. Seed demo accounts ONLY if explicitly requested (e.g. unit test suite)
    if seed_demo and db.query(EmergentAccount).count() == 0:
        demo_accounts = [
            EmergentAccount(
                account_identifier="EMG-PROD-01",
                account_name="Production Core Account",
                email="prod-core@company.org",
                organization="Enterprise Engineering",
                status="active",
                auth_type="oauth",
                connection_status="connected",
            ),
            EmergentAccount(
                account_identifier="EMG-DEV-02",
                account_name="Dev & Sandbox Account",
                email="dev-sandbox@company.org",
                organization="AI R&D Lab",
                status="active",
                auth_type="mcp",
                connection_status="connected",
            ),
            EmergentAccount(
                account_identifier="EMG-QA-03",
                account_name="Quality Assurance Account",
                email="qa-team@company.org",
                organization="QA Operations",
                status="active",
                auth_type="oauth",
                connection_status="disconnected",
            ),
        ]
        db.add_all(demo_accounts)
        db.commit()

        for acc in demo_accounts:
            snap = CreditSnapshot(
                account_id=acc.id,
                available_credits=1250.0000 if acc.connection_status == "connected" else 450.0000,
                consumed_credits=180.5000,
                total_allocated=2000.0000,
                balance_source="manual",
                is_estimate=False,
            )
            db.add(snap)
        db.commit()

    # 4. Seed MailboxAccount entry (with verified_access=False as mandated by security specification)
    if db.query(MailboxAccount).count() == 0:
        mailbox = MailboxAccount(
            email_address="auth-mailbox@internal.corp",
            provider="internal_mail_api",
            api_base_url=settings.EMAIL_API_BASE_URL,
            is_active=True,
            verified_access=False,  # Unverified until strict API authorization is confirmed
            notes="Configured internal Mail API endpoint. Pending security and API-key verification.",
        )
        db.add(mailbox)
        db.commit()

    # 5. Seed default build worker if empty
    if db.query(BuildWorker).count() == 0:
        worker = BuildWorker(
            worker_name="worker-default-01",
            status="ACTIVE",
            system_info='{"host": "hub-core-worker", "engine": "in-process-celery-compat"}',
            last_heartbeat_at=datetime.now(timezone.utc),
        )
        db.add(worker)
        db.commit()

    # 6. Seed demo project if empty
    if db.query(Project).count() == 0 and db.query(EmergentAccount).count() > 0:
        first_acc = db.query(EmergentAccount).first()
        admin = db.query(User).filter(User.email == settings.INITIAL_ADMIN_EMAIL).first()
        demo_proj = Project(
            account_id=first_acc.id,
            owner_user_id=admin.id if admin else None,
            project_name="Autonomous Agent Core",
            project_key="AGENT-CORE",
            description="Centralized autonomous agent runtime and evaluation suite.",
            status="ACTIVE",
            start_date=datetime.now(timezone.utc),
        )
        db.add(demo_proj)
        db.commit()


if __name__ == "__main__":
    db = SessionLocal()
    try:
        init_db(db)
        print("Database initialized successfully!")
    finally:
        db.close()
