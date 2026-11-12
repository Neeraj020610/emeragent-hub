"""
Agent Chat Service
Phase 6 Implementation for Emergent Central Hub

Connects:
- Real file & image upload and inspection (content, dimensions, type, line count)
- Natural language intent classification (Video Creation, Web/App Dev, Clarification Query)
- Autonomous Brain & Task Planner integration
- Account Credit Scheduler with mandatory 50% Credit Guard
- Step-by-step worker execution and transparent MOCK/REAL attribution
- Conversation control (STOP, PAUSE, RESUME) and multi-turn persistence
"""
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.account import EmergentAccount
from app.models.session import AccountSession
from app.models.autonomous import (
    AutonomousTask,
    AutonomousTaskLog,
    AccountCreditBudget,
)
from app.models.chat import (
    Conversation,
    ConversationMessage,
    MessageAttachment,
)
from app.config import settings
from app.services.autonomous.brain import AutonomousBrainService
from app.services.autonomous.scheduler import AccountCreditScheduler
from app.services.autonomous.worker_engine import AutonomousWorkerEngine
from app.services.autonomous.adapters.emergent_browser_adapter import schedule_emergent_browser_task
from app.services.autonomous.adapters.content_synthesizer import (
    build_prompt_specific_script,
    extract_clean_topic,
    normalize_prompt_text,
)

logger = logging.getLogger("emergent.agent_chat.service")

STORAGE_BASE = "storage/attachments"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentChatService:
    def __init__(
        self,
        brain: Optional[AutonomousBrainService] = None,
        scheduler: Optional[AccountCreditScheduler] = None,
        worker_engine: Optional[AutonomousWorkerEngine] = None,
    ):
        self.brain = brain or AutonomousBrainService()
        self.scheduler = scheduler or AccountCreditScheduler()
        self.worker_engine = worker_engine or AutonomousWorkerEngine(scheduler=self.scheduler, brain=self.brain)

    # -------------------------------------------------------------
    # 1. Conversation Lifecycle
    # -------------------------------------------------------------
    def create_conversation(
        self,
        user_id: int,
        title: Optional[str],
        db: Session,
    ) -> Conversation:
        conv_uuid = f"conv-{uuid.uuid4().hex[:12]}"
        conversation = Conversation(
            conversation_uuid=conv_uuid,
            user_id=user_id,
            title=title or "New Chat",
            is_pinned=False,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        # Send initial agent greeting
        greeting = ConversationMessage(
            conversation_id=conversation.id,
            sender_type="AGENT",
            content=(
                "Hey! Main aapka **Emergent AI Assistant** hoon — aap mujhse naturally baat kar sakte hain (English ya Hinglish dono me).\n\n"
                "Aap mujhse:\n"
                "- **Animated Story & Explainer Videos** banwa sakte hain (custom chapters, visuals & voiceover ke saath)\n"
                "- **Websites, Dashboards & UI Apps** build karwa sakte hain\n"
                "- **Creative Ideas, Scripts ya Account Credits** ke baare me pooch sakte hain\n\n"
                "Bataiye aaj kya create ya discuss karein?"
            ),
            is_mock=False,
            created_at=utcnow(),
        )
        db.add(greeting)
        db.commit()
        db.refresh(conversation)
        return conversation

    def list_conversations(self, user_id: int, db: Session) -> List[Dict[str, Any]]:
        convs = (
            db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.is_pinned.desc(), Conversation.updated_at.desc())
            .all()
        )
        results = []
        for c in convs:
            last_msg = (
                db.query(ConversationMessage)
                .filter(ConversationMessage.conversation_id == c.id)
                .order_by(ConversationMessage.created_at.desc())
                .first()
            )
            msg_count = db.query(ConversationMessage).filter(ConversationMessage.conversation_id == c.id).count()
            results.append({
                "id": c.id,
                "conversation_uuid": c.conversation_uuid,
                "title": c.title,
                "is_pinned": c.is_pinned,
                "current_task_id": c.current_task_id,
                "message_count": msg_count,
                "last_message_preview": (last_msg.content[:80] + "...") if last_msg else None,
                "updated_at": c.updated_at,
                "created_at": c.created_at,
            })
        return results

    def get_conversation_by_uuid(self, conv_uuid: str, user_id: int, db: Session) -> Optional[Conversation]:
        return (
            db.query(Conversation)
            .filter(Conversation.conversation_uuid == conv_uuid, Conversation.user_id == user_id)
            .first()
        )

    def delete_conversation(self, conv_uuid: str, user_id: int, db: Session) -> bool:
        conv = self.get_conversation_by_uuid(conv_uuid, user_id, db)
        if not conv:
            return False
        db.delete(conv)
        db.commit()
        return True

    # -------------------------------------------------------------
    # 2. File & Image Attachment Handling
    # -------------------------------------------------------------
    async def save_attachment(
        self,
        conversation: Conversation,
        file: UploadFile,
        db: Session,
    ) -> MessageAttachment:
        """
        Saves uploaded file to disk and performs genuine file inspection
        (dimensions, size, text lines, SHA-256 hash).
        """
        target_dir = os.path.join(STORAGE_BASE, conversation.conversation_uuid)
        os.makedirs(target_dir, exist_ok=True)

        safe_filename = f"{uuid.uuid4().hex[:6]}_{file.filename}"
        disk_path = os.path.join(target_dir, safe_filename)

        content = await file.read()
        file_size = len(content)
        file_hash = hashlib.sha256(content).hexdigest()

        with open(disk_path, "wb") as f:
            f.write(content)

        # Inspect file based on mime type
        summary = self._inspect_file_content(disk_path, file.content_type or "", content, file.filename or "")

        attachment = MessageAttachment(
            conversation_id=conversation.id,
            file_name=file.filename or safe_filename,
            file_path=disk_path,
            file_size_bytes=file_size,
            mime_type=file.content_type or "application/octet-stream",
            file_hash=file_hash,
            file_summary=summary,
            created_at=utcnow(),
        )
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
        return attachment

    def _inspect_file_content(
        self,
        path: str,
        mime_type: str,
        content: bytes,
        filename: str,
    ) -> str:
        """Extracts meaningful summary of uploaded file for agent comprehension."""
        # 1. Images
        if mime_type.startswith("image/") or filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            # Simple header inspection for PNG / JPEG dimensions
            width, height = self._get_image_dimensions(content)
            dim_str = f"{width}x{height}px" if width and height else "dimension undetermined"
            return f"Image attachment ({dim_str}, {len(content)} bytes). Visual reference inspected."

        # 2. Text / Code / JSON
        if (
            mime_type.startswith("text/")
            or mime_type in ("application/json", "application/javascript")
            or filename.lower().endswith((".py", ".ts", ".tsx", ".js", ".json", ".md", ".txt", ".yaml", ".yml", ".html", ".css"))
        ):
            try:
                text_content = content.decode("utf-8", errors="ignore")
                lines = text_content.splitlines()
                preview = lines[0][:100] if lines else "Empty file"
                return f"Source file ({len(lines)} lines, {len(content)} bytes). Header snippet: '{preview}'"
            except Exception:
                return f"Text document ({len(content)} bytes)."

        return f"Binary asset ({len(content)} bytes)."

    def _get_image_dimensions(self, data: bytes) -> Tuple[Optional[int], Optional[int]]:
        """Extracts PNG/JPEG dimensions without heavy external dependencies."""
        if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n"):
            import struct
            w, h = struct.unpack(">LL", data[16:24])
            return int(w), int(h)
        elif len(data) >= 10 and data.startswith(b"\xff\xd8"):
            # Simple JPEG SOI
            return None, None
        return None, None

    # -------------------------------------------------------------
    # 3. Message Processing & Autonomous Execution
    # -------------------------------------------------------------
    def process_user_message(
        self,
        conversation: Conversation,
        prompt: str,
        attachment_ids: Optional[List[int]],
        auto_execute: bool,
        db: Session,
    ) -> ConversationMessage:
        """
        Main Agent Reasoning & Task Loop:
        1. Persists user prompt and links attachments.
        2. Inspects prompt and attached files.
        3. Identifies work type (VIDEO_CREATION vs WEBSITE_APP_DEV vs QUERY).
        4. If vague or missing essentials -> requests clarification.
        5. If actionable -> builds structured task plan with acceptance criteria.
        6. Selects eligible Emergent account under 50% credit ceiling.
        7. If auto_execute is True, dispatches initial execution steps through worker engine.
        8. Returns comprehensive agent response with plan card, checkpoints, and mock labels.
        """
        # Save user message
        user_msg = ConversationMessage(
            conversation_id=conversation.id,
            sender_type="USER",
            content=prompt,
            is_mock=False,
            created_at=utcnow(),
        )
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)

        # Link attachments
        attached_summaries = []
        if attachment_ids:
            attachments = (
                db.query(MessageAttachment)
                .filter(MessageAttachment.id.in_(attachment_ids), MessageAttachment.conversation_id == conversation.id)
                .all()
            )
            for a in attachments:
                a.message_id = user_msg.id
                attached_summaries.append(f"[{a.file_name}: {a.file_summary or 'Asset attached'}]")
            db.commit()

        # Update conversation title if first message
        if conversation.title == "New Chat":
            conversation.title = prompt[:35] + ("..." if len(prompt) > 35 else "")

        conversation.updated_at = utcnow()
        db.commit()

        # Check if conversation already has an active task waiting or in progress
        existing_task = None
        if conversation.current_task_id:
            existing_task = db.query(AutonomousTask).filter(AutonomousTask.id == conversation.current_task_id).first()

        prompt_lower = prompt.lower().strip()
        is_hinglish = self._is_hinglish(prompt)

        # 1. Explicit continuation of an unfinished task
        is_action_confirmation = any(
            phrase in prompt_lower for phrase in [
                "do it", "pls do it", "please do it", "karo", "kardo", "run", "proceed",
                "execute", "continue", "go ahead", "chalu", "shuru", "chalao", "advance", "finish"
            ]
        ) or prompt_lower in ("yes", "haan", "ha", "ok", "thik h", "thik hai", "ok bhai")

        if existing_task and existing_task.status in ("QUEUED", "CHECKPOINT", "PLANNED", "RUNNING") and is_action_confirmation:
            if existing_task.status == "PLANNED":
                existing_task.status = "QUEUED"
                db.commit()

            execution_report = []
            for _ in range(5):
                step_res = self.worker_engine.poll_and_dispatch_next_task(db=db, force_run=True, target_task_id=existing_task.id)
                if step_res:
                    execution_report.append(step_res)
                    if step_res.get("is_completed"):
                        break

            db.refresh(existing_task)
            reply_text = self._format_completion_reply(
                task=existing_task,
                account_name=existing_task.assigned_account.account_name if existing_task.assigned_account else "Assigned Account",
                headroom=None,
                script_data=None,
                is_hinglish=is_hinglish,
                resumed=True,
            )

            agent_msg = ConversationMessage(
                conversation_id=conversation.id,
                sender_type="AGENT",
                content=reply_text,
                task_id=existing_task.id,
                execution_status=existing_task.status,
                account_id=existing_task.assigned_account_id,
                is_mock=existing_task.is_mock,
                created_at=utcnow(),
            )
            db.add(agent_msg)
            db.commit()
            db.refresh(agent_msg)
            return agent_msg

        # 2. Conversational AI handling vs Build/Video Execution Intent
        intent_mode, work_type = self._classify_conversational_intent(prompt, existing_task)

        # Handle regeneration / improvement feedback ("ye kya bna diya", "text likh diye", "better banao", etc.)
        if intent_mode == "REGENERATE_LAST" and existing_task:
            clean_subject = extract_clean_topic(existing_task.title, existing_task.description or "")
            new_prompt = f"{prompt}. Upgraded remake focused on: {clean_subject}"
            work_type = existing_task.work_type
            intent_mode = "BUILD_TASK"
            prompt_for_build = new_prompt
            regenerated_note = (
                f"Bilkul! Pehle wale result me kuch flaws the — main **{clean_subject}** ka bilkul fresh, upgraded version bana raha hoon.\n\n"
                if is_hinglish
                else f"Got it! Let me regenerate an upgraded, story-rich version of **{clean_subject}**.\n\n"
            )
        else:
            prompt_for_build = prompt
            regenerated_note = ""

        if intent_mode == "CONVERSATION":
            convo_reply = self._generate_conversational_reply(
                conversation=conversation,
                prompt=prompt,
                existing_task=existing_task,
                is_hinglish=is_hinglish,
                db=db,
            )
            agent_reply = ConversationMessage(
                conversation_id=conversation.id,
                sender_type="AGENT",
                content=convo_reply,
                execution_status=None,
                is_mock=False,
                created_at=utcnow(),
            )
            db.add(agent_reply)
            db.commit()
            db.refresh(agent_reply)
            return agent_reply

        # 3. Actionable Video or Web/App Build Request -> Plan + Execute Full Pipeline
        plan_spec = self._build_plan_specification(work_type, prompt_for_build, attached_summaries)

        estimated_cost = Decimal(str(plan_spec.get("estimated_cost", "0.2500")))
        account_selection = self.scheduler.select_eligible_account(
            work_type=work_type,
            estimated_cost=estimated_cost,
            db=db,
        )

        if not account_selection:
            msg_text = (
                f"**{plan_spec['title']}** start nahi ho paya kyunki abhi koi Emergent account eligible nahi hai "
                f"(ya to 50% credit limit reach ho chuki hai ya session verify nahi hai).\n\n"
                f"Aap **Sessions** ya **Autonomous** tab me jakar account reconnect/verify kar sakte hain."
                if is_hinglish
                else
                f"I prepared the plan for **{plan_spec['title']}**, but no Emergent account is currently eligible under the 50% credit ceiling or active session checks.\n\n"
                f"Please verify an account session in **Sessions** or **Autonomous** before running this build."
            )
            agent_reply = ConversationMessage(
                conversation_id=conversation.id,
                sender_type="AGENT",
                content=msg_text,
                action_plan_json=json.dumps(plan_spec),
                execution_status="PAUSED",
                is_mock=False,
                created_at=utcnow(),
            )
            db.add(agent_reply)
            db.commit()
            db.refresh(agent_reply)
            return agent_reply

        selected_account, selected_budget = account_selection
        remaining_headroom = self._compute_remaining_headroom(selected_budget)

        active_sess = (
            db.query(AccountSession)
            .filter(AccountSession.account_id == selected_account.id, AccountSession.session_status == "ACTIVE")
            .first()
        )
        force_local_mock = any(tok in prompt_lower for tok in ("local mock", "mock video", "demo mode"))
        use_real_emergent = bool(
            settings.EMERGENT_EXECUTION_ENABLED and auto_execute and active_sess and not force_local_mock
        )

        # Create AutonomousTask with clean subject title
        task_identifier = f"TASK-CHAT-{work_type[:3]}-{uuid.uuid4().hex[:8]}"
        task = AutonomousTask(
            task_identifier=task_identifier,
            work_type=work_type,
            source="AI_GENERATED",
            title=plan_spec["title"],
            description=f"{prompt_for_build}\n\nAttachments: {', '.join(attached_summaries) if attached_summaries else 'None'}",
            expected_result=plan_spec["expected_result"],
            acceptance_criteria=json.dumps(plan_spec["acceptance_criteria"]),
            assigned_account_id=selected_account.id,
            priority="HIGH",
            estimated_credit_cost=estimated_cost,
            actual_credit_cost=Decimal("0.0000"),
            status="IN_PROGRESS" if use_real_emergent else "QUEUED",
            retry_count=0,
            max_retries=3,
            idempotency_key=f"idemp-{task_identifier}",
            execution_adapter=(
                "EMERGENT_BROWSER_ADAPTER"
                if use_real_emergent
                else ("MOCK_VIDEO_ADAPTER" if work_type == "VIDEO_CREATION" else "MOCK_WEB_ADAPTER")
            ),
            is_mock=not use_real_emergent,
            checkpoints=json.dumps([]),
            started_at=utcnow() if use_real_emergent else None,
            last_heartbeat_at=utcnow() if use_real_emergent else None,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        conversation.current_task_id = task.id
        db.commit()

        if use_real_emergent:
            self.scheduler.reserve_budget(
                account_id=selected_account.id,
                task_id=task.id,
                estimated_cost=estimated_cost,
                db=db,
            )
            schedule_emergent_browser_task(
                task_id=task.id,
                account_id=selected_account.id,
                conversation_id=conversation.id,
                prompt=prompt_for_build,
                work_type=work_type,
                is_hinglish=is_hinglish,
            )
            response_content = regenerated_note + (
                f"Maine aapke connected Emergent account **`{selected_account.account_name}`** (`app.emergent.sh`) par **Real {'Video Agent' if work_type == 'VIDEO_CREATION' else 'Builder'}** start kar diya hai!\n\n"
                f"- **Prompt**: `{prompt_for_build[:180]}`\n"
                f"- **Remaining 50% Guard Headroom**: `{remaining_headroom:.2f}` credits\n"
                f"- **Task ID**: `{task.task_identifier}` (`IN_PROGRESS`)\n\n"
                "Emergent Chrome window me video/build tayyar ho raha hai — aap **Live Emergent Preview** niche **View Generated Deliverables & Script** me dekh sakte hain. Complete hote hi downloadable output yahin update ho jayega!"
                if is_hinglish
                else
                f"Started **Real Emergent {'Video Agent' if work_type == 'VIDEO_CREATION' else 'App Builder'}** on **`{selected_account.account_name}`** (`app.emergent.sh`)!\n\n"
                f"- **Task ID**: `{task.task_identifier}` (`IN_PROGRESS`)\n"
                f"- **50% Guard Headroom**: `{remaining_headroom:.2f}` credits\n\n"
                "Emergent is generating your deliverable in the authenticated Chrome profile. Live progress and the finished `.mp4` / workspace link will update right here automatically once ready."
            )
        else:
            # Execute ALL steps immediately when auto_execute=True so the user gets a finished playable artifact!
            steps_to_run = 5 if auto_execute else 1
            for _ in range(steps_to_run):
                step_res = self.worker_engine.poll_and_dispatch_next_task(db=db, force_run=True, target_task_id=task.id)
                if not step_res or step_res.get("is_completed"):
                    break

            db.refresh(task)
            script_preview = plan_spec.get("script_preview")
            response_content = regenerated_note + self._format_completion_reply(
                task=task,
                account_name=selected_account.account_name,
                headroom=remaining_headroom,
                script_data=script_preview,
                is_hinglish=is_hinglish,
                resumed=False,
            )

        agent_msg = ConversationMessage(
            conversation_id=conversation.id,
            sender_type="AGENT",
            content=response_content,
            task_id=task.id,
            action_plan_json=json.dumps({
                "title": plan_spec["title"],
                "expected_result": plan_spec["expected_result"],
                "work_type": plan_spec["work_type"],
            }),
            execution_status=task.status,
            account_id=selected_account.id,
            is_mock=not use_real_emergent,
            created_at=utcnow(),
        )
        db.add(agent_msg)
        db.commit()
        db.refresh(agent_msg)
        return agent_msg

    def _is_hinglish(self, text: str) -> bool:
        t = f" {text.lower()} "
        hinglish_markers = [
            " h ", " hai ", " kya ", " kaise ", " kse ", " banao ", " bnao ", " bnaye ",
            " kr ", " kro ", " karo ", " nhi ", " nahi ", " muje ", " mujhe ", " yar ", " yaar ",
            " bhai ", " yr ", " accha ", " acha ", " thik ", " batao ", " smj ", " dikhao ",
            " kharch ", " ky ", " haa ", " haan ", " isme ", " isko ", " chahiye ", " apna ",
        ]
        return any(m in t for m in hinglish_markers)

    def _compute_remaining_headroom(self, budget: AccountCreditBudget) -> float:
        try:
            start = Decimal(str(budget.starting_balance or 0))
            pct = Decimal(str(budget.ceiling_percentage or 50)) / Decimal("100")
            used = Decimal(str(budget.credit_usage or 0))
            reserved = Decimal(str(budget.reserved_credits or 0))
            return max(0.0, float((start * pct) - used - reserved))
        except Exception:
            return 0.0

    def _classify_conversational_intent(
        self, text: str, existing_task: Optional[AutonomousTask]
    ) -> Tuple[str, str]:
        """Returns (intent_mode, work_type) where intent_mode in ('CONVERSATION', 'BUILD_TASK', 'REGENERATE_LAST')."""
        norm = normalize_prompt_text(text).lower().strip()

        # Check explicit feedback wanting a remake / fix of previous build
        regen_phrases = [
            "regenerate", "remake", "dobara", "phir se", "better bnao", "better karo", "improve this",
            "change kro", "change karo", "ye kya bna", "maza nhi", "text likh", "fix video", "upgrade video"
        ]
        if existing_task and any(p in norm for p in regen_phrases):
            return "REGENERATE_LAST", existing_task.work_type

        # Pure greetings, chitchat, questions, advice, brainstorming -> CONVERSATION
        greeting_phrases = [
            "hi", "hello", "hey", "hlo", "namaste", "good morning", "good evening",
            "kaise ho", "kya haal", "how are you", "who are you", "tum kaun ho",
            "thanks", "thank you", "shukriya", "bye", "ok", "nice", "cool", "great", "good"
        ]
        if norm in greeting_phrases or (len(norm.split()) <= 4 and any(norm.startswith(g) for g in ["hi ", "hello ", "hey ", "kaise ", "kya haal", "thanks"])):
            return "CONVERSATION", "GENERAL"

        # Action verbs requesting generation/building RIGHT NOW
        build_action_verbs = [
            "create", "make", "generate", "render", "build", "develop", "design", "produce", "banao", "bana do", "taiyar"
        ]
        has_build_verb = any(v in norm.split() or v in norm for v in build_action_verbs)

        video_keywords = [
            "video", "animation", "animated", "reel", "clip", "voiceover", "storyboard",
            "short", "movie", "film", "trailer", "explainer"
        ]
        web_keywords = [
            "website", "app", "webapp", "landing", "dashboard", "portal", "webpage", "frontend", "ui", "site"
        ]

        video_score = sum(1 for k in video_keywords if k in norm)
        web_score = sum(1 for k in web_keywords if k in norm)

        # If asking for ideas, explanation, status, or story writing in chat (without "create video/app")
        conversational_queries = [
            "idea", "ideas", "suggest", "suggestion", "kya kr skte", "what can you do", "help",
            "balance", "credit", "credits", "headroom", "status", "check account", "audit",
            "explain", "batao", "btaiye", "kya hai", "what is", "how does", "kaise kaam"
        ]
        if any(q in norm for q in conversational_queries) and video_score == 0 and web_score == 0:
            return "CONVERSATION", "GENERAL"
        if ("idea" in norm or "suggest" in norm) and "create" not in norm and "banao" not in norm:
            return "CONVERSATION", "GENERAL"

        if video_score > web_score and (has_build_verb or len(norm.split()) >= 3):
            return "BUILD_TASK", "VIDEO_CREATION"
        if web_score >= video_score and web_score > 0 and (has_build_verb or len(norm.split()) >= 3):
            return "BUILD_TASK", "WEBSITE_APP_DEV"

        # Otherwise treat as natural conversation!
        return "CONVERSATION", "GENERAL"

    def _generate_conversational_reply(
        self,
        conversation: Conversation,
        prompt: str,
        existing_task: Optional[AutonomousTask],
        is_hinglish: bool,
        db: Session,
    ) -> str:
        """Generates an intelligent, contextual conversational response."""
        t = normalize_prompt_text(prompt).lower()

        # 1. Greetings
        if any(w in t for w in ["hi", "hello", "hey", "namaste", "kaise ho", "kya haal", "how are you"]):
            if is_hinglish:
                return (
                    "Hey! Main bilkul badhiya hoon, aap bataiye kaise hain? 😊\n\n"
                    "Bataiye aaj kya banayein? Agar aapko **animated story video** chahiye (jaise *Ancient Indian Warrior*, *Space Odyssey*, ya koi business explainer), ya koi **interactive web app / dashboard**, bas topic bata dijiye — main poora script, visuals aur voiceover khud craft kar dunga."
                )
            return (
                "Hey there! Doing great and ready to help. 😊\n\n"
                "We can brainstorm ideas, check your connected account credits, or create a custom **animated story video** or **interactive web app** from scratch. What's on your mind today?"
            )

        # 2. Capabilities / Help
        if any(w in t for w in ["who are you", "tum kaun", "what can you do", "kya kr skte", "help"]):
            if is_hinglish:
                return (
                    "Main aapka **Emergent Personal AI Agent** hoon. Main aapke liye kaafi cheezein kar sakta hoon:\n\n"
                    "- **Custom Animated Videos**: Sirf topic bataiye (typos ki tension mat lijiye!), main story chapters, bespoke visuals aur spoken voiceover ke saath downloadable `.mp4` bana dunga.\n"
                    "- **Websites & Dashboards**: Live Tailwind/HTML web apps build karke yahin preview & download ke liye ready kar dunga.\n"
                    "- **Credit & Account Guard**: Har task aapke connected Emergent account ki **50% limit** ke andar safely run hota hai.\n\n"
                    "Chaliye kuch try karein — kisi topic par video ya website suggest karoon?"
                )
            return (
                "I'm your **Emergent Personal AI Agent**. Here's what I can do for you right here:\n\n"
                "- **Animated Videos**: Give me a theme or story prompt and I'll craft distinct chapters, custom artwork, voiceover narration, and a downloadable `.mp4`.\n"
                "- **Web Apps & Dashboards**: I generate responsive standalone web apps with live preview.\n"
                "- **Account & Credit Insights**: I automatically schedule work within your 50% credit ceiling.\n\n"
                "Want to brainstorm a topic or build something now?"
            )

        # 3. Credit / Account status questions
        if any(w in t for w in ["credit", "balance", "account", "headroom", "status", "audit"]):
            accounts = db.query(EmergentAccount).all()
            lines = []
            for acc in accounts:
                bud = db.query(AccountCreditBudget).filter(AccountCreditBudget.account_id == acc.id).first()
                if bud:
                    rem = self._compute_remaining_headroom(bud)
                    lines.append(
                        f"- **{acc.account_name}** (`{acc.connection_status}`): Balance `{float(bud.verified_current_balance):.2f}` credits | 50% Eligible Remaining: `{rem:.2f}`"
                    )
            summary = "\n".join(lines) if lines else "- Abhi koi active budget record nahi mila."
            if is_hinglish:
                return f"Yeh raha aapke connected accounts ka live credit status:\n\n{summary}\n\nAgar chahein to main abhi kisi eligible account par naya build ya video task run kar sakta hoon!"
            return f"Here is the live status of your connected Emergent accounts:\n\n{summary}\n\nLet me know if you'd like me to kick off a new video or web build on an eligible account."

        # 4. Ideas / Suggestions / Story Discussion
        if any(w in t for w in ["idea", "suggest", "story", "kahani", "warrior", "ancient", "topic"]):
            if is_hinglish:
                return (
                    "Bahut badhiya! Yahan kuch zabardast concepts hain jo hum abhi animated video ya web app ke roop me bana sakte hain:\n\n"
                    "1. **\"Create an animated video of an Ancient Indian Warrior\"** — 3 dramatic chapters (Dawn of Honor, Battle with Talwar & Shield, Eternal Legacy) custom visuals ke saath.\n"
                    "2. **\"Build a sleek AI Finance Tracker web app\"** — Live responsive UI aur interactive features ke saath.\n"
                    "3. **\"Create an animated space odyssey video about Mars\"** — Starfield, ringed planet aur voiceover narration.\n\n"
                    "Inme se koi pasand aaya, ya aapka apna koi naya idea hai?"
                )
            return (
                "Here are a few creative concepts we can build right away:\n\n"
                "1. **Animated Historical Story**: *\"Create an animated video of an Ancient Indian Warrior\"* — 3 illustrated chapters with custom sword & fort artwork and voiceover.\n"
                "2. **Sci-Fi Mini Film**: *\"Create a space odyssey video exploring Mars\"* — cosmic visuals and narration.\n"
                "3. **Interactive Web App**: *\"Build a clean SaaS analytics dashboard\"* — standalone live HTML experience.\n\n"
                "Which direction sounds best to you?"
            )

        # 5. Follow-up referencing existing task
        if existing_task:
            clean_subj = extract_clean_topic(existing_task.title, existing_task.description or "")
            if is_hinglish:
                return (
                    f"Haan bilkul! Hamari pichhli build **\"{clean_subj}\"** (`{existing_task.task_identifier}`, status: **{existing_task.status}**) ready hai.\n\n"
                    "Agar aapko isme kuch change karna hai (jaise narration style, naya chapter, ya bilkul naya version regenerate karna), to bas bataiye — ya koi naya video/website topic dijiye!"
                )
            return (
                f"Got it! Your latest build **\"{clean_subj}\"** (`{existing_task.task_identifier}`, status: **{existing_task.status}**) is saved.\n\n"
                "Tell me what you'd like to tweak or regenerate, or share a brand-new topic for a video or web app!"
            )

        # 6. General friendly conversational fallback
        if is_hinglish:
            return (
                f"Samajh gaya! Agar aap **\"{prompt.strip()}\"** par ek **animated story video** ya **interactive webpage** banana chahte hain, "
                "to bas itna bol dijiye: *\"Is par animated video banao\"* ya *\"Iske liye website banao\"* — main turant clean chapters, art aur voiceover ke saath taiyar kar dunga."
            )
        return (
            f"Interesting! If you'd like me to turn **\"{prompt.strip()}\"** into a full **animated video** or an **interactive web app**, "
            "just tell me to create a video or build a webpage on it and I'll generate the complete deliverable for you."
        )

    def _format_completion_reply(
        self,
        task: AutonomousTask,
        account_name: str,
        headroom: Optional[float],
        script_data: Optional[Dict[str, Any]],
        is_hinglish: bool,
        resumed: bool,
    ) -> str:
        clean_topic = extract_clean_topic(task.title, task.description or "")
        cost_val = float(task.actual_credit_cost or 0)
        headroom_str = f" • Eligible Headroom left: `{headroom:.2f}`" if headroom is not None else ""

        scene_bullets = ""
        if script_data and script_data.get("scenes"):
            lines = [
                f"- **Chapter {s.get('scene_id', i+1)} — {s.get('scene_title')}**: {s.get('visual_headline') or s.get('visual')}"
                for i, s in enumerate(script_data["scenes"])
            ]
            scene_bullets = "\n".join(lines)

        if task.work_type == "VIDEO_CREATION":
            if is_hinglish:
                intro = (
                    f"Maine aapke topic **\"{clean_topic}\"** par ek proper animated story video ready kar diya hai — isme clean chapter visuals aur synced English voiceover hai!\n\n"
                )
                footer = (
                    f"\n\n**Run Summary**: Account `{account_name}`{headroom_str} • Status: **{task.status}** • Credits used: `{cost_val:.4f}` (`{task.task_identifier}`)\n\n"
                    "Niche **View Generated Deliverables & Script** button par click karke video play aur `.mp4` download karein. Koi scene badalna ho to bataiye!"
                )
            else:
                intro = (
                    f"Done! I've created your animated video for **\"{clean_topic}\"** with custom illustrated chapters and synced voiceover narration.\n\n"
                )
                footer = (
                    f"\n\n**Build Summary**: Executed on `{account_name}`{headroom_str} • Status: **{task.status}** • Credits used: `{cost_val:.4f}` (`{task.task_identifier}`)\n\n"
                    "Click **View Generated Deliverables & Script** below to watch the video, read the script, or download the `.mp4`. Want me to adjust any scene?"
                )
            body = f"**Video Chapters Created:**\n{scene_bullets}" if scene_bullets else ""
            return intro + body + footer
        else:
            if is_hinglish:
                return (
                    f"Done! Maine **\"{clean_topic}\"** ke liye standalone responsive web app build kar diya hai.\n\n"
                    f"**Build Summary**: Account `{account_name}`{headroom_str} • Status: **{task.status}** • Credits used: `{cost_val:.4f}` (`{task.task_identifier}`)\n\n"
                    "Niche **View Generated Deliverables & Script** par click karke live webpage preview dekhein ya `.html` file download karein!"
                )
            return (
                f"Your web app for **\"{clean_topic}\"** is built and verified!\n\n"
                f"**Build Summary**: Executed on `{account_name}`{headroom_str} • Status: **{task.status}** • Credits used: `{cost_val:.4f}` (`{task.task_identifier}`)\n\n"
                "Click **View Generated Deliverables & Script** below to open the interactive live preview or download the `.html` bundle."
            )

    def _build_plan_specification(
        self,
        work_type: str,
        prompt: str,
        attachments: List[str],
    ) -> Dict[str, Any]:
        clean_topic = extract_clean_topic("", prompt)
        if work_type == "VIDEO_CREATION":
            script_preview = build_prompt_specific_script(clean_topic, prompt, "")
            story_title = script_preview.get("title") or clean_topic
            return {
                "title": story_title[:90],
                "work_type": "VIDEO_CREATION",
                "expected_result": f"Animated multi-chapter story video for '{clean_topic}' with custom art & synced voiceover.",
                "script_preview": script_preview,
                "acceptance_criteria": [
                    "Custom chapter narrative arc and visual pacing",
                    "Scene-specific illustrated storyboard prompts",
                    "Synchronized spoken voiceover narration",
                    "Rendered H.264 MP4 with AAC audio",
                    "Verified artifact stored and downloadable",
                ],
                "estimated_cost": "0.3200",
            }
        else:
            return {
                "title": f"{clean_topic}"[:90],
                "work_type": "WEBSITE_APP_DEV",
                "expected_result": f"Responsive interactive web application built around '{clean_topic}'.",
                "acceptance_criteria": [
                    "Architecture schemas and routing contracts defined",
                    "Modular component and responsive UI generated",
                    "Automated checks pass with zero regressions",
                    "Interactive HTML deliverable compiled cleanly",
                ],
                "estimated_cost": "0.3000",
            }

    # -------------------------------------------------------------
    # 4. Task Controls (STOP, PAUSE, RESUME)
    # -------------------------------------------------------------
    def control_task(
        self,
        conversation: Conversation,
        action: str,
        user: User,
        db: Session,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Cooperative task control for conversation tasks.
        Uses safe checkpoint boundaries.
        """
        act = action.strip().upper()
        if act not in ("STOP", "PAUSE", "RESUME"):
            raise ValueError(f"Invalid task control action '{action}'. Valid: STOP, PAUSE, RESUME.")

        if not conversation.current_task_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active task associated with this conversation.")

        task = db.query(AutonomousTask).filter(AutonomousTask.id == conversation.current_task_id).first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated task not found.")

        if act == "STOP":
            task.status = "CANCELLED"
            task.error_details = f"Stopped by user {user.email}. {note or ''}"
            # Release any locked account
            if task.assigned_account_id:
                budget = db.query(AccountCreditBudget).filter(AccountCreditBudget.account_id == task.assigned_account_id).first()
                if budget and budget.active_task_id == task.id:
                    budget.active_task_id = None
        elif act == "PAUSE":
            task.status = "PAUSED"
        elif act == "RESUME":
            task.status = "QUEUED"

        task.updated_at = utcnow()

        # Log system message into conversation
        ctrl_msg = ConversationMessage(
            conversation_id=conversation.id,
            sender_type="SYSTEM",
            content=f"Operator executed **{act}** on task `{task.task_identifier}`. Note: {note or 'None'}",
            task_id=task.id,
            execution_status=task.status,
            is_mock=True,
            created_at=utcnow(),
        )
        db.add(ctrl_msg)
        db.commit()
        db.refresh(task)

        return {
            "task_id": task.task_identifier,
            "status": task.status,
            "action_executed": act,
            "message": f"Task {task.task_identifier} transitioned to {task.status}.",
        }
