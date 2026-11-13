"""
Real Emergent Browser Execution Adapter.
Drives the authenticated isolated Chrome/Chromium session on https://app.emergent.sh
for VIDEO_CREATION and WEBSITE_APP_DEV tasks dispatched from Agent Chat.
"""
import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.database import SessionLocal
from app.models.account import EmergentAccount
from app.models.autonomous import AccountCreditBudget, AutonomousTask, AutonomousTaskLog
from app.models.chat import ConversationMessage
from app.services.autonomous.scheduler import AccountCreditScheduler
from app.services.session.login_automation import (
    _is_dashboard_page,
    _mark_session_expired,
    _scrape_and_record_credits,
    active_pages,
)
from app.services.session.manager import MultiAccountSessionManager, cleanup_stale_profile_locks

logger = logging.getLogger("emergent.autonomous.emergent_browser")

MAIN_EVENT_LOOP: Optional[asyncio.AbstractEventLoop] = None
_ACTIVE_TASK_RUNNERS: Dict[int, asyncio.Task] = {}


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Stores the FastAPI main asyncio event loop so sync routes can schedule Playwright tasks."""
    global MAIN_EVENT_LOOP
    MAIN_EVENT_LOOP = loop


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _append_task_log(task_id: int, message: str, step: str = "EMERGENT_BROWSER", level: str = "INFO") -> None:
    db = SessionLocal()
    try:
        db.add(
            AutonomousTaskLog(
                task_id=task_id,
                worker_id="emergent-browser",
                log_level=level,
                message=message,
                step_name=step,
                created_at=utcnow(),
            )
        )
        db.commit()
    finally:
        db.close()


def _update_task_fields(
    task_id: int,
    *,
    status: Optional[str] = None,
    checkpoints: Optional[List[Dict[str, Any]]] = None,
    result_metadata: Optional[Dict[str, Any]] = None,
    actual_credit_cost: Optional[Decimal] = None,
    error_details: Optional[str] = None,
    error_classification: Optional[str] = None,
    completed: bool = False,
) -> None:
    db = SessionLocal()
    try:
        task = db.query(AutonomousTask).filter(AutonomousTask.id == task_id).first()
        if not task:
            return
        if status is not None:
            task.status = status
        if checkpoints is not None:
            task.checkpoints = json.dumps(checkpoints)
        if result_metadata is not None:
            task.result_metadata = json.dumps(result_metadata)
        if actual_credit_cost is not None:
            task.actual_credit_cost = actual_credit_cost
        if error_details is not None:
            task.error_details = error_details
        if error_classification is not None:
            task.error_classification = error_classification
        task.last_heartbeat_at = utcnow()
        task.updated_at = utcnow()
        if completed:
            task.completed_at = utcnow()
        db.commit()
    finally:
        db.close()


def _post_chat_update(
    conversation_id: int,
    task_id: int,
    account_id: int,
    content: str,
    execution_status: str,
    plan_title: str = "",
) -> None:
    db = SessionLocal()
    try:
        action_plan = (
            json.dumps({
                "title": plan_title,
                "expected_result": "Generated via live Emergent Studio browser session.",
                "work_type": "EMERGENT_BROWSER",
            })
            if plan_title
            else None
        )
        msg = ConversationMessage(
            conversation_id=conversation_id,
            sender_type="AGENT",
            content=content,
            task_id=task_id,
            action_plan_json=action_plan,
            execution_status=execution_status,
            account_id=account_id,
            is_mock=False,
            created_at=utcnow(),
        )
        db.add(msg)
        db.commit()
    finally:
        db.close()


async def _dismiss_emergent_overlays(page: Page) -> None:
    """Dismisses onboarding modals/coachmarks and accepts first-time Video Use Policy on Emergent."""
    try:
        later = page.locator("button[data-testid='video-intro-maybe-later']").first
        if await later.is_visible(timeout=500):
            await later.click(timeout=3000)
            await asyncio.sleep(0.4)
    except Exception:
        pass
    try:
        # First-time "Creating videos on Emergent" Video Use Policy modal on /chat
        agree_btn = page.locator("button:has-text('I agree, continue')").first
        if await agree_btn.is_visible(timeout=500):
            cb = page.locator("[role='dialog'] input[type='checkbox'], [role='dialog'] [role='checkbox'], input[type='checkbox']").first
            if await cb.is_visible(timeout=800):
                try:
                    await cb.check(timeout=2000)
                except Exception:
                    await cb.click(timeout=2000, force=True)
                await asyncio.sleep(0.3)
            if await agree_btn.is_enabled(timeout=1000):
                await agree_btn.click(timeout=3000)
                await asyncio.sleep(0.6)
    except Exception:
        pass
    try:
        coach = page.locator("div.z-fast-mode-coachmark, [class*='coachmark']").first
        if await coach.is_visible(timeout=400):
            await coach.click(timeout=3000)
            await asyncio.sleep(0.3)
    except Exception:
        pass
    try:
        # Only press Escape if no policy dialog is open
        if not await page.locator("button:has-text('I agree, continue')").first.is_visible(timeout=200):
            await page.keyboard.press("Escape")
    except Exception:
        pass


async def _save_task_screenshot(page: Page, task_identifier: str) -> str:
    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    shot_dir = os.path.join(backend_root, "storage", "artifacts", "emergent_shots")
    os.makedirs(shot_dir, exist_ok=True)
    shot_path = os.path.join(shot_dir, f"{task_identifier}.png")
    try:
        await page.screenshot(path=shot_path, timeout=8000)
    except Exception:
        pass
    return shot_path


async def _scrape_credits_number(page: Page) -> Optional[float]:
    try:
        for sel in [
            "button[data-testid='nudges-sidebar-credit-chip']",
            "button[data-testid='menubar-topup-discount-button']",
            "button:has-text('Credits')",
        ]:
            el = page.locator(sel).first
            if await el.is_visible(timeout=600):
                txt = (await el.inner_text()).strip()
                if "%" in txt:
                    continue
                m = re.search(r"(\d+(?:\.\d+)?)\s*(?:credits)?", txt, re.I)
                if m:
                    return float(m.group(1))
        body_txt = await page.evaluate("document.body.innerText")
        m = re.search(r"(\d+\.\d+|\d+)\s+credits\b", body_txt, re.I)
        if m:
            return float(m.group(1))
    except Exception:
        pass
    return None


async def _acquire_account_page(
    playwright: Any, account_id: int
) -> Tuple[Optional[Browser], Optional[BrowserContext], Optional[Page], bool, Optional[str]]:
    """
    Attaches to an already-open CDP Chromium instance for `account_id`, or launches one with CDP enabled.
    Returns (cdp_browser, persistent_context, page, should_close_context, error_msg).
    """
    import subprocess

    cdp_port = 9222 + account_id
    cdp_url = f"http://127.0.0.1:{cdp_port}"

    async def _attach_cdp(timeout_ms: int = 2500) -> Optional[Tuple[Browser, Page]]:
        browser = await playwright.chromium.connect_over_cdp(cdp_url, timeout=timeout_ms)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        # Prefer an open emergent.sh tab or create a fresh page if existing tabs are closed/blank
        open_pages = [pg for pg in context.pages if not pg.is_closed()]
        emergent_pages = [pg for pg in open_pages if "emergent.sh" in (pg.url or "").lower()]
        page = emergent_pages[0] if emergent_pages else (open_pages[0] if open_pages else await context.new_page())
        return browser, page

    try:
        browser, page = await _attach_cdp(2500)
        return browser, None, page, False, None
    except Exception:
        pass

    manager = MultiAccountSessionManager()
    browser_exe = manager.find_dedicated_browser() or manager.find_system_browser()
    if not browser_exe:
        return None, None, None, False, "No Chromium/Chrome executable found on host."

    profile_dir = manager._get_browser_profile_dir(account_id)
    cleanup_stale_profile_locks(profile_dir)

    is_linux = os.name != "nt"
    has_display = bool(os.environ.get("DISPLAY"))
    extra_flags = []
    if is_linux:
        extra_flags.extend(["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"])
        if not has_display:
            extra_flags.append("--headless=new")

    # Launch detached Chrome with CDP port so the session stays alive across tasks
    try:
        cmd = [
            browser_exe,
            f"--user-data-dir={profile_dir}",
            f"--remote-debugging-port={cdp_port}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled",
        ] + extra_flags + ["https://app.emergent.sh/home"]
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(16):
            await asyncio.sleep(0.5)
            try:
                browser, page = await _attach_cdp(1500)
                return browser, None, page, False, None
            except Exception:
                continue
    except Exception:
        pass

    # Fallback: direct persistent context inside this Playwright session
    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        executable_path=browser_exe,
        headless=(not has_display if is_linux else False),
        args=[
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled",
        ] + extra_flags,
        viewport={"width": 1280, "height": 720} if (is_linux and not has_display) else None,
    )
    open_pages = [pg for pg in context.pages if not pg.is_closed()]
    page = open_pages[0] if open_pages else await context.new_page()
    return None, context, page, False, None


def _is_valid_video_bytes(data: bytes, content_type: str = "") -> bool:
    """Validates that downloaded bytes are an actual MP4/WebM binary, not an HTML/JSON page."""
    if not data or len(data) < 20480:
        return False
    ct = (content_type or "").lower()
    if "text/html" in ct or "application/json" in ct or "text/plain" in ct:
        return False
    head = data[:32]
    if head.lstrip().startswith(b"<") or head.lstrip().startswith(b"{"):
        return False
    # MP4 / MOV ('ftyp' box at bytes 4..12) or WebM / Matroska (EBML 0x1A45DFA3)
    if b"ftyp" in head[:16] or head.startswith(b"\x1a\x45\xdf\xa3"):
        return True
    return ct.startswith("video/")


async def _detect_emergent_video_asset(page: Page) -> Optional[str]:
    """Finds a generated MP4/WebM video source URL (ignoring policy/landing/intro links)."""
    try:
        candidates = await page.evaluate(
            """() => {
                const urls = [];
                document.querySelectorAll('video, video source').forEach(v => {
                    const src = v.currentSrc || v.src || v.getAttribute('src');
                    if (src) urls.push({src, fromVideo: true});
                });
                document.querySelectorAll('a[download], a[href*=".mp4"], a[href*=".webm"]').forEach(a => {
                    if (a.href) urls.push({src: a.href, fromVideo: false});
                });
                return urls;
            }"""
        )
        for item in candidates:
            u = item.get("src") or ""
            low = u.lower()
            if not u:
                continue
            if any(bad in low for bad in ("landing", "intro", "hero", "showcase", "policy", "terms", "docs", "help")):
                continue
            if low.startswith("blob:") and item.get("fromVideo"):
                return u
            if ".mp4" in low or ".webm" in low or (item.get("fromVideo") and low.startswith("http")):
                return u
    except Exception:
        pass
    return None


async def _detect_emergent_preview_url(page: Page) -> Optional[str]:
    try:
        hrefs = await page.evaluate(
            """() => {
                const out = [];
                document.querySelectorAll('iframe[src], a[href*="emergent.host"], a[href*="preview"], a[target="_blank"]').forEach(e => {
                    const u = e.src || e.href;
                    if (u && u.startsWith('http') && !u.includes('app.emergent.sh/landing')) out.push(u);
                });
                return out;
            }"""
        )
        return hrefs[0] if hrefs else None
    except Exception:
        return None


async def _check_emergent_errors(page: Page) -> Optional[str]:
    for sel in ["[role='alert']", "text=/insufficient credits/i", "text=/out of credits/i", "text=/quota exceeded/i", "text=/failed to generate/i"]:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=200):
                txt = (await el.inner_text()).strip()
                if txt and len(txt) < 220:
                    return txt
        except Exception:
            pass
    return None


async def _execute_emergent_browser_workflow(
    task_id: int,
    account_id: int,
    conversation_id: int,
    prompt: str,
    work_type: str,
    is_hinglish: bool,
) -> None:
    """Runs the real Emergent.sh task end-to-end via Playwright on the account's Chrome session."""
    scheduler = AccountCreditScheduler()

    db = SessionLocal()
    try:
        task = db.query(AutonomousTask).filter(AutonomousTask.id == task_id).first()
        account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
        if not task or not account:
            return
        task_identifier = task.task_identifier
        task_title = task.title
        estimated_cost = task.estimated_credit_cost
        account_name = account.account_name
    finally:
        db.close()

    checkpoints: List[Dict[str, Any]] = []
    cdp_browser: Optional[Browser] = None
    page: Optional[Page] = None
    current_stage = "Initializing Emergent browser session"

    try:
        async with async_playwright() as p:
            current_stage = "Attaching/launching isolated Chrome profile"
            cdp_browser, _ctx, page, _, err_msg = await _acquire_account_page(p, account_id)
            if err_msg or not page:
                raise RuntimeError(err_msg or "Failed to open isolated Chromium session.")

            current_stage = "Navigating to https://app.emergent.sh/home"
            if "emergent.sh" not in page.url.lower() or "/home" not in page.url.lower():
                await page.goto("https://app.emergent.sh/home", wait_until="domcontentloaded", timeout=30000)

            current_stage = "Verifying authenticated Emergent dashboard"
            authenticated = False
            for _ in range(12):
                await asyncio.sleep(1.0)
                if "/landing" in page.url.lower() or "/login" in page.url.lower():
                    break
                if await _is_dashboard_page(page):
                    authenticated = True
                    break

            if not authenticated:
                await _save_task_screenshot(page, task_identifier)
                _mark_session_expired(account_id, f"Session expired at {page.url} during task execution.")
                raise RuntimeError(f"Emergent session for '{account_name}' expired (redirected to {page.url}). Please Sign In again in Accounts.")

            await _dismiss_emergent_overlays(page)
            start_credits = await _scrape_credits_number(page)
            checkpoints.append({
                "step": "EMERGENT_SESSION_VERIFIED",
                "completed_at": utcnow().isoformat(),
                "starting_credits": start_credits,
            })
            _update_task_fields(task_id, checkpoints=checkpoints)
            _append_task_log(task_id, f"Attached to authenticated Emergent Chrome for '{account_name}'. Starting credits: {start_credits}", step="EMERGENT_SESSION_VERIFIED")

            # Ensure we are still on /home before looking for main-task-input
            if "/home" not in page.url.lower():
                await page.goto("https://app.emergent.sh/home", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(1.5)
                await _dismiss_emergent_overlays(page)

            # Select mode tab (supports both Emergent v1 and v2 Home UIs)
            current_stage = f"Selecting Emergent mode tab ({work_type})"
            if work_type == "VIDEO_CREATION":
                tab_sel = "button[data-testid='main-task-tab-desktop-video'], button[data-testid='home-v2-composer-target-video']"
            elif any(k in prompt.lower() for k in ("website", "landing page")):
                tab_sel = "button[data-testid='main-task-tab-desktop-landing'], button[data-testid='home-v2-composer-target-website']"
            elif any(k in prompt.lower() for k in ("mobile", "android", "ios app")):
                tab_sel = "button[data-testid='main-task-tab-desktop-mobile'], button[data-testid='home-v2-composer-target-mobile_app']"
            else:
                tab_sel = "button[data-testid='main-task-tab-desktop-fullstack'], button[data-testid='home-v2-composer-target-web_app']"

            # Wait for React composer (#mainTaskInput or home-v2-composer-input) to mount
            current_stage = "Waiting for Emergent prompt input (#mainTaskInput / home-v2)"
            composer = page.locator(
                "textarea[data-testid='main-task-input'], #mainTaskInput, textarea[data-testid='home-v2-composer-input'], textarea:visible"
            ).first
            try:
                await composer.wait_for(state="visible", timeout=10000)
            except Exception:
                await page.reload(wait_until="domcontentloaded", timeout=25000)
                await asyncio.sleep(2.0)
                await _dismiss_emergent_overlays(page)
                try:
                    await composer.wait_for(state="visible", timeout=12000)
                except Exception as inner_exc:
                    await _save_task_screenshot(page, task_identifier)
                    _mark_session_expired(account_id, f"Emergent /home stuck on skeleton loader at {page.url}. Please Re-auth '{account_name}'.")
                    raise RuntimeError(
                        f"Emergent /home page stuck on loading skeleton for '{account_name}' (#mainTaskInput did not appear). "
                        f"Session may be incomplete/expired — please Sign In again in Accounts."
                    ) from inner_exc

            # Select mode tab (Video vs Web app / Website) now that Home UI is mounted
            current_stage = f"Selecting Emergent mode tab ({work_type})"
            tab_btn = page.locator(tab_sel).first
            if await tab_btn.is_visible(timeout=5000):
                await tab_btn.evaluate("e => e.scrollIntoView({block: 'center', inline: 'center'})")
                await asyncio.sleep(0.3)
                try:
                    await tab_btn.click(timeout=5000)
                except Exception:
                    await _dismiss_emergent_overlays(page)
                    await tab_btn.click(timeout=5000, force=True)
                await asyncio.sleep(0.8)

            # Enter prompt into Emergent composer & submit
            await _save_task_screenshot(page, task_identifier)
            current_stage = "Filling prompt and clicking Submit"
            await composer.click()
            await composer.fill(prompt.strip())
            await asyncio.sleep(0.4)

            submit_btn = page.locator(
                "button[data-testid='main-task-submit'], button[data-testid='home-v2-composer-send'], button[aria-label='Send']"
            ).first
            try:
                await submit_btn.wait_for(state="visible", timeout=8000)
                await submit_btn.click(timeout=5000)
            except Exception:
                await composer.press("Enter")

            _append_task_log(task_id, "Submitted prompt to live Emergent Studio composer.", step="EMERGENT_PROMPT_SUBMITTED")
            checkpoints.append({"step": "EMERGENT_PROMPT_SUBMITTED", "completed_at": utcnow().isoformat()})
            _update_task_fields(task_id, checkpoints=checkpoints)

            current_stage = "Waiting for Emergent workspace deliverable"

            # Wait up to 15s for workspace navigation
            for _ in range(15):
                await asyncio.sleep(1.0)
                if "/home" not in page.url.lower():
                    break

            emergent_url = page.url
            await _save_task_screenshot(page, task_identifier)

            # Poll Emergent until video/webapp deliverable finishes (max 20 mins) or user stops task
            max_polls = 240
            downloaded_video_path: Optional[str] = None
            preview_url: Optional[str] = None
            generation_done = False

            for poll_idx in range(max_polls):
                await asyncio.sleep(5.0)

                # Cooperative check for CANCELLED / PAUSED
                db_chk = SessionLocal()
                try:
                    t_chk = db_chk.query(AutonomousTask).filter(AutonomousTask.id == task_id).first()
                    if not t_chk or t_chk.status in ("CANCELLED", "PAUSED"):
                        _append_task_log(task_id, f"Task cooperatively stopped ({t_chk.status if t_chk else 'DELETED'}).", step="ABORTED", level="WARN")
                        return
                finally:
                    db_chk.close()

                if page.url != emergent_url and "/home" not in page.url.lower():
                    emergent_url = page.url

                await _dismiss_emergent_overlays(page)
                # Auto-advance Emergent Video Director approval gates (Frames / Scenes) & unanswered wizard
                if work_type == "VIDEO_CREATION":
                    try:
                        approve_btn = page.locator("button:has-text('Approve'):visible").first
                        if await approve_btn.is_visible(timeout=250):
                            await approve_btn.click(timeout=2500)
                            _append_task_log(task_id, "Auto-approved Emergent Frames/Scenes stage.", step="EMERGENT_STAGE_APPROVED")
                            await asyncio.sleep(1.0)
                    except Exception:
                        pass
                    if poll_idx >= 4:
                        try:
                            skip_btn = page.locator("button:has-text('Skip'):visible").first
                            if await skip_btn.is_visible(timeout=200):
                                await skip_btn.click(timeout=2000)
                                _append_task_log(task_id, "Auto-skipped Emergent Director clarification prompt.", step="EMERGENT_WIZARD_SKIPPED")
                                await asyncio.sleep(1.0)
                        except Exception:
                            pass
                await _save_task_screenshot(page, task_identifier)

                err_banner = await _check_emergent_errors(page)
                if err_banner:
                    raise RuntimeError(f"Emergent returned error: {err_banner}")

                if work_type == "VIDEO_CREATION":
                    vid_src = await _detect_emergent_video_asset(page)
                    if vid_src:
                        video_dir = os.path.join(os.getcwd(), "storage", "artifacts", "videos")
                        os.makedirs(video_dir, exist_ok=True)
                        local_mp4 = os.path.join(video_dir, f"{task_identifier}.mp4")
                        raw_bytes: bytes = b""
                        ct = ""
                        if vid_src.startswith("blob:"):
                            import base64
                            b64_data = await page.evaluate(
                                """async (u) => {
                                    const r = await fetch(u);
                                    const buf = await r.arrayBuffer();
                                    const bytes = new Uint8Array(buf);
                                    let bin = '';
                                    for (let i = 0; i < bytes.length; i += 0x8000) {
                                        bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
                                    }
                                    return btoa(bin);
                                }""",
                                vid_src,
                            )
                            if b64_data:
                                raw_bytes = base64.b64decode(b64_data)
                                ct = "video/mp4"
                        else:
                            resp = await page.request.get(vid_src, timeout=60000)
                            if resp.ok:
                                ct = resp.headers.get("content-type", "")
                                raw_bytes = await resp.body()
                        if _is_valid_video_bytes(raw_bytes, ct):
                            with open(local_mp4, "wb") as f:
                                f.write(raw_bytes)
                            downloaded_video_path = local_mp4
                            generation_done = True
                            break
                else:
                    preview_url = await _detect_emergent_preview_url(page)
                    stop_btn = page.locator("button:has-text('Stop'):visible, [aria-label*='Stop' i]:visible").first
                    is_busy = await stop_btn.is_visible(timeout=200)
                    if preview_url and not is_busy and poll_idx >= 3:
                        generation_done = True
                        break

                if poll_idx % 6 == 0:
                    _update_task_fields(task_id)

            end_credits = await _scrape_credits_number(page)
            await _scrape_and_record_credits(page, account_id)

            actual_cost = Decimal("0.0000")
            if start_credits is not None and end_credits is not None and start_credits >= end_credits:
                actual_cost = Decimal(str(round(start_credits - end_credits, 4)))

            checkpoints.append({
                "step": "EMERGENT_DELIVERABLE_READY" if generation_done else "EMERGENT_WORKSPACE_TIMEOUT",
                "completed_at": utcnow().isoformat(),
                "emergent_url": emergent_url,
                "ending_credits": end_credits,
            })

            result_meta: Dict[str, Any] = {
                "adapter": "EMERGENT_BROWSER_ADAPTER",
                "is_mock": False,
                "emergent_task_url": emergent_url,
                "preview_image_url": f"/api/v1/autonomous/tasks/{task_id}/preview-image",
                "preview_url": preview_url,
                "output_format": "mp4" if downloaded_video_path else "emergent_workspace",
            }
            if downloaded_video_path:
                result_meta["video_url"] = f"/artifacts/videos/{task_identifier}.mp4"
                result_meta["file_size_bytes"] = os.path.getsize(downloaded_video_path)

            final_status = "COMPLETED" if generation_done else "FAILED"
            _update_task_fields(
                task_id,
                status=final_status,
                checkpoints=checkpoints,
                result_metadata=result_meta,
                actual_credit_cost=actual_cost,
                error_details=None if generation_done else f"Timed out waiting for Emergent deliverable at {emergent_url}",
                completed=generation_done,
            )

            db_rec = SessionLocal()
            try:
                scheduler.record_usage_and_release(
                    account_id=account_id,
                    task_id=task_id,
                    estimated_cost=estimated_cost,
                    actual_cost=actual_cost,
                    usage_type="PLATFORM_BUILD",
                    db=db_rec,
                )
            finally:
                db_rec.close()

            # Automatic Failover Check: If active account credits reached 0, auto-switch to next account!
            if end_credits is not None and end_credits <= 0:
                try:
                    from app.services.session.failover_service import auto_failover_exhausted_account
                    asyncio.create_task(auto_failover_exhausted_account(account_id))
                    logger.info(f"Account {account_id} credits exhausted (0 Cr). Triggered background auto-failover.")
                except Exception as ex_fail:
                    logger.warning(f"Error triggering auto-failover: {ex_fail}")

            if downloaded_video_path:
                msg_txt = (
                    f"Real Emergent Video ready hai! **{task_title}** (`{account_name}`) par generate ho chuka hai.\n\n"
                    f"- **Emergent Project**: {emergent_url}\n"
                    f"- **Actual Credits Delta**: `{actual_cost}`\n\n"
                    "Niche **View Generated Deliverables & Script** par click karke real Emergent MP4 video play ya download karein!"
                    if is_hinglish
                    else
                    f"Your real Emergent video for **{task_title}** is ready (executed on `{account_name}`)!\n\n"
                    f"- **Emergent Project**: {emergent_url}\n"
                    f"- **Actual Credits Used**: `{actual_cost}`\n\n"
                    "Click **View Generated Deliverables & Script** below to watch or download the `.mp4`."
                )
            elif generation_done:
                msg_txt = (
                    f"Real Emergent build ready hai! **{task_title}** (`{account_name}`) par complete ho chuka hai.\n\n"
                    f"- **Emergent Project**: {emergent_url}\n"
                    + (f"- **Live Preview**: {preview_url}\n" if preview_url else "")
                    + f"- **Actual Credits Delta**: `{actual_cost}`"
                    if is_hinglish
                    else
                    f"Your real Emergent project for **{task_title}** is complete on `{account_name}`!\n\n"
                    f"- **Emergent Project**: {emergent_url}\n"
                    + (f"- **Live Preview**: {preview_url}\n" if preview_url else "")
                )
            else:
                msg_txt = (
                    f"Emergent (`{account_name}`) par task abhi process ho raha hai (timeout reached while waiting for final asset).\n"
                    f"Aap seedhe **Chrome window** ya is link par live progress dekh sakte hain: {emergent_url}"
                    if is_hinglish
                    else
                    f"Emergent is still processing **{task_title}** on `{account_name}`.\n"
                    f"You can follow live progress directly in Chrome or at: {emergent_url}"
                )

            _post_chat_update(conversation_id, task_id, account_id, msg_txt, final_status, plan_title=task_title)
            _append_task_log(task_id, f"Emergent run finished ({final_status}). URL: {emergent_url}", step=final_status)

    except Exception as exc:
        last_url = "N/A"
        try:
            if page and not page.is_closed():
                last_url = page.url
                await _save_task_screenshot(page, task_identifier)
        except Exception:
            pass
        detailed_err = f"[{current_stage}] (URL: {last_url}) -> {exc}"
        logger.error(f"Emergent browser execution failed for task {task_id}: {detailed_err}", exc_info=True)
        _update_task_fields(
            task_id,
            status="FAILED",
            error_details=detailed_err,
            error_classification="EMERGENT_BROWSER_ERROR",
        )
        db_rel = SessionLocal()
        try:
            scheduler.record_usage_and_release(
                account_id=account_id,
                task_id=task_id,
                estimated_cost=estimated_cost,
                actual_cost=Decimal("0.0000"),
                usage_type="PLATFORM_BUILD",
                db=db_rel,
            )
        finally:
            db_rel.close()

        err_chat = (
            f"Real Emergent run (`{account_name}`) fail hua:\n"
            f"- **Stage**: `{current_stage}`\n"
            f"- **Page URL**: `{last_url}`\n"
            f"- **Reason**: `{exc}`"
            if is_hinglish
            else
            f"Real Emergent execution on `{account_name}` failed:\n"
            f"- **Stage**: `{current_stage}`\n"
            f"- **Page URL**: `{last_url}`\n"
            f"- **Reason**: `{exc}`"
        )
        _post_chat_update(conversation_id, task_id, account_id, err_chat, "FAILED")
        _append_task_log(task_id, detailed_err, step="FAILED", level="ERROR")
    finally:
        if cdp_browser:
            try:
                await cdp_browser.close()
            except Exception:
                pass


def schedule_emergent_browser_task(
    task_id: int,
    account_id: int,
    conversation_id: int,
    prompt: str,
    work_type: str,
    is_hinglish: bool,
) -> None:
    """Dispatches the async Playwright Emergent workflow cleanly onto the main FastAPI loop."""
    coro = _execute_emergent_browser_workflow(
        task_id=task_id,
        account_id=account_id,
        conversation_id=conversation_id,
        prompt=prompt,
        work_type=work_type,
        is_hinglish=is_hinglish,
    )
    if MAIN_EVENT_LOOP and MAIN_EVENT_LOOP.is_running():
        asyncio.run_coroutine_threadsafe(coro, MAIN_EVENT_LOOP)
    else:
        import threading

        threading.Thread(target=lambda: asyncio.run(coro), daemon=True).start()

