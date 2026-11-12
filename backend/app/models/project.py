from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("emergent_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    project_name = Column(String(150), nullable=False)
    project_key = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="PLANNING", nullable=False)  # PLANNING, ACTIVE, ON_HOLD, COMPLETED, ARCHIVED
    start_date = Column(DateTime(timezone=True), nullable=True)
    expected_completion_date = Column(DateTime(timezone=True), nullable=True)
    tags = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    account = relationship("EmergentAccount", back_populates="projects")
    owner = relationship("User", foreign_keys=[owner_user_id], back_populates="owned_projects")
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    build_jobs = relationship("BuildJob", back_populates="project", cascade="all, delete-orphan")


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_in_project = Column(String(50), default="developer", nullable=False)  # lead, developer, reviewer, observer
    assigned_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    project = relationship("Project", back_populates="members")
    user = relationship("User", back_populates="project_memberships")
