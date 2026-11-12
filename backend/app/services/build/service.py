"""
Build and Project Management Service
Phase 4 Implementation for Emergent Central Hub

Coordinates:
- Project creation, access management, and member assignment
- Build job creation, prioritization, and idempotency protection
- Role-based access control (Admin, Manager, Member)
- Account execution permission and personal consent verification
- Queue dispatch, state transition enforcement, and history tracking
- Dashboard statistics with strict mock vs real provenance
"""
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.models.user import User
from app.models.account import EmergentAccount, AccountPermission, PersonalAccountConsent
from app.models.project import Project, ProjectMember
from app.models.job import BuildJob, JobAssignment, BuildJobHistory, BuildWorker
from app.schemas.job import (
    BuildJobCreate,
    BuildJobUpdate,
    BuildJobResponse,
    BuildJobDetailResponse,
    JobAssignmentResponse,
    BuildJobHistoryResponse,
    BuildDashboardStatsResponse,
)
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectDetailResponse,
    ProjectMemberResponse,
)
from app.services.build.state_machine import validate_transition, InvalidTransitionError
from app.services.build.queue import BuildExecutionQueue
from app.dependencies import record_audit

logger = logging.getLogger("emergent.build.service")


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class BuildService:
    def __init__(self, queue: Optional[BuildExecutionQueue] = None):
        self.queue = queue or BuildExecutionQueue()

    # -------------------------------------------------------------
    # 1. Permission and Access Verification Helpers
    # -------------------------------------------------------------
    def verify_account_execution_access(
        self,
        account: EmergentAccount,
        user: User,
        db: Session,
    ) -> None:
        """
        Ensures the user has permission to initiate a build against the given account.
        Enforces server-side consent for personal accounts.
        """
        is_admin = user.role and user.role.name.upper() in ("ADMIN", "SUPERADMIN")

        if account.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Emergent account '{account.account_name}' is currently {account.status}. Builds cannot be scheduled.",
            )

        if account.ownership_type == "PERSONAL":
            if account.owner_user_id == user.id:
                return  # Account owner has full access

            # Non-owner requires explicit server-side PersonalAccountConsent
            now = datetime.now(timezone.utc)
            consent = (
                db.query(PersonalAccountConsent)
                .filter(
                    PersonalAccountConsent.account_id == account.id,
                    PersonalAccountConsent.authorized_member_id == user.id,
                    PersonalAccountConsent.is_active == True,
                )
                .first()
            )
            consent_expires = ensure_utc(consent.expires_at) if consent else None
            if not consent or (consent_expires and consent_expires < now):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Access Denied: Account '{account.account_name}' is personal property. "
                        f"Explicit server-side owner consent is required before scheduling builds."
                    ),
                )
            return

        # Company-owned account
        if is_admin:
            return  # Admin has full company-owned access

        perm = (
            db.query(AccountPermission)
            .filter(
                AccountPermission.account_id == account.id,
                AccountPermission.user_id == user.id,
            )
            .first()
        )
        if perm is not None and not perm.can_execute:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: You do not have 'can_execute' permission for account '{account.account_name}'.",
            )

    def verify_project_access(
        self,
        project: Project,
        user: User,
        db: Session,
        require_manager: bool = False,
    ) -> None:
        """
        Enforces project access rules:
        - ADMIN has global access.
        - MANAGER has access if owner, project member, or manager role on company project.
        - MEMBER has access if registered in project_members, owner, or if open company project.
        """
        role_name = (user.role.name.upper() if user.role else "MEMBER")
        if role_name in ("ADMIN", "SUPERADMIN"):
            return

        if project.owner_user_id == user.id:
            return

        # Check membership in project_members
        membership = (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == user.id,
            )
            .first()
        )

        if require_manager:
            if role_name == "MANAGER" and (membership is not None or project.owner_user_id == user.id):
                return
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Manager permissions required for this project operation.",
            )

        if not membership and role_name != "MANAGER":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access Denied: You are not assigned to project '{project.project_name}'.",
            )

    # -------------------------------------------------------------
    # 2. Project Management Operations
    # -------------------------------------------------------------
    def list_projects(
        self,
        current_user: User,
        db: Session,
        account_id: Optional[int] = None,
        status_filter: Optional[str] = None,
    ) -> List[ProjectResponse]:
        role_name = (current_user.role.name.upper() if current_user.role else "MEMBER")
        query = db.query(Project)

        if account_id:
            query = query.filter(Project.account_id == account_id)
        if status_filter:
            query = query.filter(Project.status == status_filter.upper())

        # RBAC Filtering
        if role_name not in ("ADMIN", "SUPERADMIN"):
            # Members and Managers see projects where they are owner or member
            member_project_ids = [
                pm.project_id
                for pm in db.query(ProjectMember.project_id).filter(ProjectMember.user_id == current_user.id).all()
            ]
            query = query.filter(
                or_(
                    Project.owner_user_id == current_user.id,
                    Project.id.in_(member_project_ids),
                )
            )

        projects = query.order_by(Project.created_at.desc()).all()
        result = []
        for p in projects:
            total_b = db.query(BuildJob).filter(BuildJob.project_id == p.id).count()
            active_b = (
                db.query(BuildJob)
                .filter(
                    BuildJob.project_id == p.id,
                    BuildJob.job_status.in_(["QUEUED", "ASSIGNED", "STARTING", "RUNNING", "PAUSED"]),
                )
                .count()
            )
            resp = ProjectResponse.model_validate(p)
            resp.total_builds_count = total_b
            resp.active_builds_count = active_b
            if p.account:
                resp.account_name = p.account.account_name
            if p.owner:
                resp.owner_name = p.owner.full_name
            result.append(resp)
        return result

    def create_project(
        self,
        payload: ProjectCreate,
        current_user: User,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> ProjectDetailResponse:
        account = db.query(EmergentAccount).filter(EmergentAccount.id == payload.account_id).first()
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergent account not found.")

        # Check existing project_key uniqueness
        existing_key = db.query(Project).filter(Project.project_key == payload.project_key.upper()).first()
        if existing_key:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project key '{payload.project_key.upper()}' is already in use.",
            )

        project = Project(
            account_id=payload.account_id,
            owner_user_id=payload.owner_user_id or current_user.id,
            project_name=payload.project_name.strip(),
            project_key=payload.project_key.strip().upper(),
            description=payload.description,
            status=payload.status.upper() if payload.status else "PLANNING",
            start_date=payload.start_date,
            expected_completion_date=payload.expected_completion_date,
            tags=payload.tags,
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        # Add initial members if requested
        if payload.member_user_ids:
            for uid in payload.member_user_ids:
                if uid != project.owner_user_id:
                    member = ProjectMember(
                        project_id=project.id,
                        user_id=uid,
                        role_in_project="developer",
                    )
                    db.add(member)
            db.commit()

        record_audit(
            db=db,
            action="project_created",
            resource_type="project",
            resource_id=str(project.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"Created project '{project.project_name}' ({project.project_key})",
        )

        return self.get_project_details(project.id, current_user, db)

    def get_project_details(
        self,
        project_id: int,
        current_user: User,
        db: Session,
    ) -> ProjectDetailResponse:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        self.verify_project_access(project, current_user, db)

        members = db.query(ProjectMember).filter(ProjectMember.project_id == project.id).all()
        member_responses = []
        for m in members:
            mr = ProjectMemberResponse.model_validate(m)
            if m.user:
                mr.user_email = m.user.email
                mr.user_full_name = m.user.full_name
            member_responses.append(mr)

        total_b = db.query(BuildJob).filter(BuildJob.project_id == project.id).count()
        active_b = (
            db.query(BuildJob)
            .filter(
                BuildJob.project_id == project.id,
                BuildJob.job_status.in_(["QUEUED", "ASSIGNED", "STARTING", "RUNNING", "PAUSED"]),
            )
            .count()
        )

        resp = ProjectDetailResponse.model_validate(project)
        resp.members = member_responses
        resp.total_builds_count = total_b
        resp.active_builds_count = active_b
        if project.account:
            resp.account_name = project.account.account_name
        if project.owner:
            resp.owner_name = project.owner.full_name
        return resp

    def update_project(
        self,
        project_id: int,
        payload: ProjectUpdate,
        current_user: User,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> ProjectDetailResponse:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        self.verify_project_access(project, current_user, db, require_manager=True)

        if payload.project_name is not None:
            project.project_name = payload.project_name.strip()
        if payload.description is not None:
            project.description = payload.description
        if payload.status is not None:
            project.status = payload.status.upper()
        if payload.start_date is not None:
            project.start_date = payload.start_date
        if payload.expected_completion_date is not None:
            project.expected_completion_date = payload.expected_completion_date
        if payload.tags is not None:
            project.tags = payload.tags

        db.commit()
        db.refresh(project)

        record_audit(
            db=db,
            action="project_updated",
            resource_type="project",
            resource_id=str(project.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"Updated project settings for '{project.project_name}'",
        )
        return self.get_project_details(project.id, current_user, db)

    def add_project_member(
        self,
        project_id: int,
        user_id: int,
        role_in_project: str,
        current_user: User,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> ProjectMemberResponse:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        self.verify_project_access(project, current_user, db, require_manager=True)

        target_user = db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        existing = (
            db.query(ProjectMember)
            .filter(ProjectMember.project_id == project.id, ProjectMember.user_id == user_id)
            .first()
        )
        if existing:
            existing.role_in_project = role_in_project
            db.commit()
            db.refresh(existing)
            member = existing
        else:
            member = ProjectMember(
                project_id=project.id,
                user_id=user_id,
                role_in_project=role_in_project,
            )
            db.add(member)
            db.commit()
            db.refresh(member)

        record_audit(
            db=db,
            action="project_member_added",
            resource_type="project",
            resource_id=str(project.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"Assigned user {target_user.email} as '{role_in_project}' to project '{project.project_name}'",
        )

        resp = ProjectMemberResponse.model_validate(member)
        resp.user_email = target_user.email
        resp.user_full_name = target_user.full_name
        return resp

    def remove_project_member(
        self,
        project_id: int,
        user_id: int,
        current_user: User,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> None:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        self.verify_project_access(project, current_user, db, require_manager=True)

        member = (
            db.query(ProjectMember)
            .filter(ProjectMember.project_id == project.id, ProjectMember.user_id == user_id)
            .first()
        )
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User is not a member of this project.")

        db.delete(member)
        db.commit()

        record_audit(
            db=db,
            action="project_member_removed",
            resource_type="project",
            resource_id=str(project.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"Removed user #{user_id} from project '{project.project_name}'",
        )

    # -------------------------------------------------------------
    # 3. Build Manager & Job Lifecycle Operations
    # -------------------------------------------------------------
    def create_build_job(
        self,
        payload: BuildJobCreate,
        current_user: User,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> BuildJobDetailResponse:
        project = db.query(Project).filter(Project.id == payload.project_id).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        account = db.query(EmergentAccount).filter(EmergentAccount.id == payload.account_id).first()
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergent account not found.")

        # 1. Verify Project Access
        self.verify_project_access(project, current_user, db)

        # 2. Verify Account Execution Access & Owner Consent
        self.verify_account_execution_access(account, current_user, db)

        # 3. Idempotency Check: Prevent duplicate submissions
        if payload.idempotency_key:
            duplicate = (
                db.query(BuildJob)
                .filter(BuildJob.idempotency_key == payload.idempotency_key)
                .first()
            )
            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Duplicate build submission: A job with idempotency key '{payload.idempotency_key}' already exists (Job #{duplicate.id}).",
                )

        now = datetime.now(timezone.utc)
        initial_status = "QUEUED" if payload.auto_start else "DRAFT"
        ref_urls_json = json.dumps(payload.reference_urls) if payload.reference_urls else None
        attachments_json = json.dumps(payload.attachments_metadata) if payload.attachments_metadata else None

        job = BuildJob(
            project_id=project.id,
            account_id=account.id,
            initiated_by_user_id=current_user.id,
            title=payload.title.strip() if payload.title else f"Build for {project.project_name}",
            job_type=payload.job_type,
            job_status=initial_status,
            priority=payload.priority.upper() if payload.priority else "MEDIUM",
            requirements=payload.requirements,
            reference_urls=ref_urls_json,
            notes=payload.notes,
            attachments_metadata=attachments_json,
            expected_completion_date=payload.expected_completion_date,
            idempotency_key=payload.idempotency_key,
            execution_adapter="MOCK_EMERGENT",
            is_mock=True,
            credits_used=Decimal("0.0000"),
            request_payload=payload.request_payload,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Assign team member if requested or default to initiating user
        assigned_uid = payload.assigned_user_id or current_user.id
        assignment = JobAssignment(
            job_id=job.id,
            assigned_user_id=assigned_uid,
            role_in_job="operator",
        )
        db.add(assignment)

        # Record initial history
        self.queue.record_history(
            db=db,
            job_id=job.id,
            from_status=None,
            to_status=initial_status,
            worker_id="scheduler",
            message=f"Build job created in {initial_status} status by user #{current_user.id}",
        )
        db.commit()

        record_audit(
            db=db,
            action="build_job_created",
            resource_type="build_job",
            resource_id=str(job.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"Created build job #{job.id} '{job.title}' (Priority: {job.priority}, Status: {job.job_status})",
        )

        return self.get_build_job_details(job.id, current_user, db)

    def list_build_jobs(
        self,
        current_user: User,
        db: Session,
        project_id: Optional[int] = None,
        account_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        priority_filter: Optional[str] = None,
        assigned_user_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[BuildJobResponse]:
        role_name = (current_user.role.name.upper() if current_user.role else "MEMBER")
        query = db.query(BuildJob)

        if project_id:
            query = query.filter(BuildJob.project_id == project_id)
        if account_id:
            query = query.filter(BuildJob.account_id == account_id)
        if status_filter:
            query = query.filter(BuildJob.job_status == status_filter.upper())
        if priority_filter:
            query = query.filter(BuildJob.priority == priority_filter.upper())
        if assigned_user_id:
            query = query.join(BuildJob.assignments).filter(JobAssignment.assigned_user_id == assigned_user_id)

        # RBAC Isolation: Regular members see jobs for projects they belong to or jobs they initiated/are assigned to
        if role_name not in ("ADMIN", "SUPERADMIN"):
            user_project_ids = [
                pm.project_id
                for pm in db.query(ProjectMember.project_id).filter(ProjectMember.user_id == current_user.id).all()
            ]
            assigned_job_ids = [
                ja.job_id
                for ja in db.query(JobAssignment.job_id).filter(JobAssignment.assigned_user_id == current_user.id).all()
            ]
            query = query.filter(
                or_(
                    BuildJob.initiated_by_user_id == current_user.id,
                    BuildJob.id.in_(assigned_job_ids),
                    BuildJob.project_id.in_(user_project_ids),
                )
            )

        jobs = query.order_by(BuildJob.created_at.desc()).offset(offset).limit(limit).all()
        result = []
        for j in jobs:
            result.append(self._build_job_response(j, db))
        return result

    def get_build_job_details(
        self,
        job_id: int,
        current_user: User,
        db: Session,
    ) -> BuildJobDetailResponse:
        job = db.query(BuildJob).filter(BuildJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Build job not found.")

        # RBAC Check
        role_name = (current_user.role.name.upper() if current_user.role else "MEMBER")
        if role_name not in ("ADMIN", "SUPERADMIN"):
            project = db.query(Project).filter(Project.id == job.project_id).first()
            if project:
                self.verify_project_access(project, current_user, db)

        base_resp = self._build_job_response(job, db)
        histories = (
            db.query(BuildJobHistory)
            .filter(BuildJobHistory.job_id == job.id)
            .order_by(BuildJobHistory.created_at.asc())
            .all()
        )
        history_responses = [BuildJobHistoryResponse.model_validate(h) for h in histories]

        resp_dict = base_resp.model_dump()
        resp_dict["history"] = history_responses
        return BuildJobDetailResponse.model_validate(resp_dict)

    def start_job(
        self,
        job_id: int,
        current_user: User,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> BuildJobDetailResponse:
        """Transitions a DRAFT job to QUEUED."""
        job = db.query(BuildJob).filter(BuildJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Build job not found.")

        validate_transition(job.job_status, "QUEUED", job_id=job.id)
        old_status = job.job_status
        job.job_status = "QUEUED"
        job.updated_at = datetime.now(timezone.utc)

        self.queue.record_history(
            db=db,
            job_id=job.id,
            from_status=old_status,
            to_status="QUEUED",
            message=f"Job queued for execution by user #{current_user.id}",
        )
        db.commit()

        record_audit(
            db=db,
            action="build_job_queued",
            resource_type="build_job",
            resource_id=str(job.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"Queued build job #{job.id}",
        )
        return self.get_build_job_details(job.id, current_user, db)

    def pause_job(
        self,
        job_id: int,
        current_user: User,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> BuildJobDetailResponse:
        job = self.queue.pause_job(db=db, job_id=job_id, user_id=current_user.id)
        record_audit(
            db=db,
            action="build_job_paused",
            resource_type="build_job",
            resource_id=str(job.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"Paused build job #{job.id}",
        )
        return self.get_build_job_details(job.id, current_user, db)

    def resume_job(
        self,
        job_id: int,
        current_user: User,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> BuildJobDetailResponse:
        job = self.queue.resume_job(db=db, job_id=job_id, user_id=current_user.id)
        record_audit(
            db=db,
            action="build_job_resumed",
            resource_type="build_job",
            resource_id=str(job.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"Resumed build job #{job.id}",
        )
        return self.get_build_job_details(job.id, current_user, db)

    def cancel_job(
        self,
        job_id: int,
        current_user: User,
        db: Session,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> BuildJobDetailResponse:
        job = self.queue.cancel_job(db=db, job_id=job_id, user_id=current_user.id, reason=reason)
        record_audit(
            db=db,
            action="build_job_cancelled",
            resource_type="build_job",
            resource_id=str(job.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"Cancelled build job #{job.id}. Reason: {reason or 'User requested'}",
        )
        return self.get_build_job_details(job.id, current_user, db)

    def retry_job(
        self,
        job_id: int,
        current_user: User,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> BuildJobDetailResponse:
        job = self.queue.retry_job(db=db, job_id=job_id, user_id=current_user.id)
        record_audit(
            db=db,
            action="build_job_retried",
            resource_type="build_job",
            resource_id=str(job.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"Re-queued failed build job #{job.id}",
        )
        return self.get_build_job_details(job.id, current_user, db)

    # -------------------------------------------------------------
    # 4. Dashboard Metrics & Provenance Reporting
    # -------------------------------------------------------------
    def get_dashboard_stats(self, db: Session) -> BuildDashboardStatsResponse:
        total = db.query(BuildJob).count()
        draft = db.query(BuildJob).filter(BuildJob.job_status == "DRAFT").count()
        queued = db.query(BuildJob).filter(BuildJob.job_status == "QUEUED").count()
        running = db.query(BuildJob).filter(BuildJob.job_status.in_(["STARTING", "RUNNING"])).count()
        paused = db.query(BuildJob).filter(BuildJob.job_status == "PAUSED").count()
        completed = db.query(BuildJob).filter(BuildJob.job_status == "COMPLETED").count()
        failed = db.query(BuildJob).filter(BuildJob.job_status == "FAILED").count()
        cancelled = db.query(BuildJob).filter(BuildJob.job_status == "CANCELLED").count()

        # Calculate average duration of completed jobs
        completed_jobs = (
            db.query(BuildJob)
            .filter(BuildJob.job_status == "COMPLETED", BuildJob.started_at.isnot(None), BuildJob.completed_at.isnot(None))
            .all()
        )
        durations = []
        for j in completed_jobs:
            c_at = ensure_utc(j.completed_at)
            s_at = ensure_utc(j.started_at)
            if c_at and s_at:
                durations.append((c_at - s_at).total_seconds())
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        # Available workers count
        available_workers = db.query(BuildWorker).filter(BuildWorker.status.in_(["ACTIVE", "BUSY"])).count()
        if available_workers == 0:
            available_workers = 1  # Default built-in worker engine

        # Provenance counts
        mock_count = db.query(BuildJob).filter(BuildJob.is_mock == True).count()
        real_count = db.query(BuildJob).filter(BuildJob.is_mock == False).count()

        # Queue health heuristic
        if failed > 5 or queued > 25:
            queue_health = "DEGRADED"
        elif total == 0 or (queued == 0 and running == 0):
            queue_health = "IDLE"
        else:
            queue_health = "HEALTHY"

        return BuildDashboardStatsResponse(
            total_builds=total,
            draft_builds=draft,
            queued_builds=queued,
            running_builds=running,
            paused_builds=paused,
            completed_builds=completed,
            failed_builds=failed,
            cancelled_builds=cancelled,
            avg_execution_time_seconds=round(avg_duration, 1),
            queue_health=queue_health,
            available_workers=available_workers,
            failed_job_alerts=failed,
            mock_execution_count=mock_count,
            real_execution_count=real_count,
            execution_enabled=False,  # Explicitly disclaims real Emergent execution
        )

    # -------------------------------------------------------------
    # 5. Helper Serializer
    # -------------------------------------------------------------
    def _build_job_response(self, job: BuildJob, db: Session) -> BuildJobResponse:
        assignments = db.query(JobAssignment).filter(JobAssignment.job_id == job.id).all()
        assignment_responses = []
        assigned_user_name = None
        for a in assignments:
            ar = JobAssignmentResponse.model_validate(a)
            if a.user:
                ar.assigned_user_email = a.user.email
                ar.assigned_user_name = a.user.full_name
                if not assigned_user_name:
                    assigned_user_name = a.user.full_name
            assignment_responses.append(ar)

        ref_urls = None
        if job.reference_urls:
            try:
                ref_urls = json.loads(job.reference_urls) if job.reference_urls.startswith("[") else [job.reference_urls]
            except Exception:
                ref_urls = [job.reference_urls]

        attachments = None
        if job.attachments_metadata:
            try:
                attachments = json.loads(job.attachments_metadata) if job.attachments_metadata.startswith("[") else []
            except Exception:
                attachments = []

        duration = None
        j_started = ensure_utc(job.started_at)
        j_completed = ensure_utc(job.completed_at)
        if j_started and j_completed:
            duration = (j_completed - j_started).total_seconds()

        resp = BuildJobResponse(
            id=job.id,
            project_id=job.project_id,
            project_name=job.project.project_name if job.project else None,
            project_key=job.project.project_key if job.project else None,
            account_id=job.account_id,
            account_name=job.account.account_name if job.account else None,
            account_email=job.account.email if job.account else None,
            initiated_by_user_id=job.initiated_by_user_id,
            initiator_name=job.initiated_by.full_name if job.initiated_by else None,
            title=job.title,
            job_type=job.job_type,
            job_status=job.job_status,
            priority=job.priority,
            requirements=job.requirements,
            reference_urls=ref_urls,
            notes=job.notes,
            attachments_metadata=attachments,
            expected_completion_date=job.expected_completion_date,
            idempotency_key=job.idempotency_key,
            worker_id=job.worker_id,
            last_heartbeat_at=job.last_heartbeat_at,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            timeout_seconds=job.timeout_seconds,
            execution_adapter=job.execution_adapter,
            is_mock=job.is_mock,
            started_at=job.started_at,
            paused_at=job.paused_at,
            cancelled_at=job.cancelled_at,
            completed_at=job.completed_at,
            credits_used=job.credits_used,
            request_payload=job.request_payload,
            result_summary=job.result_summary,
            result_metadata=job.result_metadata,
            error_details=job.error_details,
            created_at=job.created_at,
            updated_at=job.updated_at,
            assignments=assignment_responses,
            assigned_user_name=assigned_user_name,
            duration_seconds=duration,
        )
        return resp
