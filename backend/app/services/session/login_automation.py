import asyncio
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
from playwright.async_api import async_playwright, BrowserContext, Page
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.account import EmergentAccount
from app.models.session import AccountSession
from app.models.audit import AuditLog
from app.services.session.manager import cleanup_stale_profile_locks, MultiAccountSessionManager
from app.services.otp.phx_fetcher import fetch_email_otp

logger = logging.getLogger("emergent.session.automation")

# Global in-memory progress tracker accessible to frontend polling
# key: account_id -> { "status": "...", "step": "...", "logs": [...], "command_id": ..., "otp_code": ..., "is_complete": bool, "error": ... }
login_progress: Dict[int, Dict[str, Any]] = {}
active_pages: Dict[int, Page] = {}


async def type_manual_otp_into_page(account_id: int, otp_code: str) -> bool:
    """If an automated login browser is waiting on the OTP screen, types manual OTP into it."""
    page = active_pages.get(account_id)
    if page and not page.is_closed():
        try:
            append_log(account_id, f"⌨️ Applying manual OTP ({otp_code}) to Emergent input...")
            entered = await _type_otp_into_emergent(page, otp_code)
            await _save_page_screenshot(page, account_id)
            return entered
        except Exception as e:
            logger.warning(f"Error applying manual OTP to page: {e}")
    return False


async def verify_manual_otp_and_authenticate(account_id: int, otp_code: str) -> Tuple[bool, str]:
    """
    Types manual OTP into the active Emergent browser session,
    verifies whether Emergent actually authenticates and loads the dashboard,
    and only marks the account CONNECTED upon genuine verification.
    """
    page = active_pages.get(account_id)
    if not page or page.is_closed():
        return False, "No active browser session open for this account. Please click 'Launch Isolated Browser & Sign In' first."

    clean_otp = otp_code.strip()
    append_log(account_id, f"⌨️ Submitting OTP ({clean_otp}) into Emergent...")
    entered = await _type_otp_into_emergent(page, clean_otp)
    if not entered:
        cur_url = page.url
        if "/landing" in cur_url.lower() and await page.locator("button:has-text('Continue with Email')").first.is_visible(timeout=300):
            return False, "Emergent OTP screen is not open yet (browser is still on landing page). Please check Chrome or restart Sign In."
        if await page.locator("input#password:visible, input[type='password']:visible").first.is_visible(timeout=300):
            return False, "Emergent is still on the Email/Password screen (OTP challenge has not appeared yet). Check Chrome for any error or CAPTCHA."
        return False, f"Could not find visible OTP input boxes on Emergent screen ({cur_url})."

    await _save_page_screenshot(page, account_id)
    append_log(account_id, "⏳ Verifying with Emergent whether OTP is valid...")

    # Wait up to 12 seconds for Emergent dashboard to load
    for _ in range(12):
        await asyncio.sleep(1.0)
        await _save_page_screenshot(page, account_id)

        # Check for error banners
        for err_sel in ["[role='alert']", ".text-red-500", ".text-destructive", "text=Invalid", "text=incorrect", "text=expired"]:
            try:
                el = page.locator(err_sel).first
                if await el.is_visible(timeout=200):
                    txt = (await el.text_content() or "").strip()
                    if txt:
                        append_log(account_id, f"❌ Emergent rejected OTP: {txt}", "error")
                        return False, f"Emergent rejected code: {txt}"
            except Exception:
                pass

        if await _is_dashboard_page(page):
            append_log(account_id, "🎉 Genuine Emergent Dashboard Verified! Session marked ACTIVE.")
            _mark_session_active(account_id)
            await _scrape_and_record_credits(page, account_id)
            if account_id in login_progress:
                login_progress[account_id]["status"] = "SUCCESS"
                login_progress[account_id]["is_complete"] = True
            return True, "Emergent dashboard successfully authenticated!"

    return False, "OTP submitted, but Emergent dashboard did not open. Code may be invalid or expired."


async def _scrape_and_record_credits(page: Page, account_id: int):
    """Scrapes live credit balance from Emergent dashboard and records CreditSnapshot in DB."""
    try:
        import re
        from decimal import Decimal
        from app.models.credit import CreditSnapshot
        from app.database import SessionLocal

        await asyncio.sleep(1.5)
        found_credits = None

        # 1. Dismiss any welcome dialogs or coachmarks
        for _ in range(2):
            try:
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.2)
            except Exception:
                pass

        try:
            maybe_later = page.locator("button:has-text('Maybe later')").first
            if await maybe_later.is_visible(timeout=1000):
                await maybe_later.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass

        # 2. Check User Avatar Menu (where Emergent displays exact credits, e.g. Credits\n109.65)
        try:
            avatar_btn = page.locator("[data-testid='menubar-avatar-button']").first
            if await avatar_btn.is_visible(timeout=2500):
                await avatar_btn.evaluate("e => e.click()")
                await asyncio.sleep(0.8)

                menu_texts = await page.eval_on_selector_all(
                    "[role='dialog'] *, [role='menu'] *, [data-radix-popper-content-wrapper] *",
                    "els => els.map(e => e.innerText ? e.innerText.trim() : '')"
                )
                full_text = "\n".join(menu_texts)

                m = re.search(r'Credits\s*\n\s*(\d+(?:\.\d+)?)', full_text, re.IGNORECASE)
                if m:
                    found_credits = Decimal(m.group(1))
                else:
                    m2 = re.search(r'(\d+(?:\.\d+)?)\s*credits', full_text, re.IGNORECASE)
                    if m2:
                        found_credits = Decimal(m2.group(1))

                await page.keyboard.press("Escape")
        except Exception as e:
            logger.debug(f"Avatar menu scrape note: {e}")

        # 3. Fallback: Search page text if avatar menu didn't yield
        if found_credits is None:
            content = await page.content()
            patterns = [
                r'Credits\s*[:\n]?\s*(\d+(?:\.\d+)?)',
                r'(\d+(?:\.\d+)?)\s*(?:credits|credit|cr\b)',
                r'(?:credits?|balance)\s*[:\-]?\s*(\d+(?:\.\d+)?)',
            ]
            for pat in patterns:
                matches = re.findall(pat, content, re.IGNORECASE)
                for m in matches:
                    try:
                        val = float(m)
                        if val >= 0:
                            found_credits = Decimal(str(val))
                            break
                    except Exception:
                        continue
                if found_credits is not None:
                    break

        if found_credits is not None:
            db = SessionLocal()
            try:
                from app.models.autonomous import AccountCreditBudget
                from app.models.credit import CreditEvent
                
                snap = CreditSnapshot(
                    account_id=account_id,
                    available_credits=found_credits,
                    consumed_credits=Decimal("0.0"),
                    total_allocated=found_credits,
                    balance_source="REAL_PROVIDER",
                    is_estimate=False,
                )
                db.add(snap)
                
                # Update account last synced
                acc = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
                if acc:
                    acc.last_synced_at = datetime.now(timezone.utc)

                # Sync AccountCreditBudget
                budget = db.query(AccountCreditBudget).filter(AccountCreditBudget.account_id == account_id).first()
                if budget:
                    budget.starting_balance = found_credits
                    budget.verified_current_balance = found_credits
                    budget.balance_source = "REAL_PROVIDER"
                    budget.last_balance_validated_at = datetime.now(timezone.utc)
                    budget.is_eligible = True
                    budget.ineligibility_reason = None
                else:
                    budget = AccountCreditBudget(
                        account_id=account_id,
                        starting_balance=found_credits,
                        verified_current_balance=found_credits,
                        credit_usage=Decimal("0.0000"),
                        reserved_credits=Decimal("0.0000"),
                        ceiling_percentage=Decimal("50.00"),
                        balance_source="REAL_PROVIDER",
                        last_balance_validated_at=datetime.now(timezone.utc),
                        is_eligible=True,
                        universal_api_usage=Decimal("0.0000"),
                        platform_build_usage=Decimal("0.0000"),
                    )
                    db.add(budget)

                # Log CreditEvent for telemetry audit
                evt = CreditEvent(
                    account_id=account_id,
                    event_type="deposit",
                    amount=found_credits,
                    balance_after=found_credits,
                    notes=f"Live balance synchronized from Emergent dashboard: {found_credits} credits",
                    event_timestamp=datetime.now(timezone.utc),
                )
                db.add(evt)

                db.commit()
                append_log(account_id, f"💰 Live credit balance detected & saved: {found_credits} credits")
            finally:
                db.close()
    except Exception as e:
        logger.warning(f"Error scraping credits from Emergent: {e}")


def _mark_session_expired(account_id: int, reason: str = "Emergent browser session expired. Please Sign In again."):
    """Marks both AccountSession and EmergentAccount as expired/disconnected when live browser is logged out."""
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        from app.models.account import EmergentAccount
        from app.models.session import AccountSession
        from app.models.autonomous import AccountCreditBudget
        sess = db.query(AccountSession).filter(AccountSession.account_id == account_id).first()
        if sess:
            sess.session_status = "EXPIRED"
            sess.reauth_required = True
            sess.reauth_reason = reason
            sess.updated_at = now
        acc = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
        if acc:
            acc.connection_status = "DISCONNECTED"
            acc.updated_at = now
        bud = db.query(AccountCreditBudget).filter(AccountCreditBudget.account_id == account_id).first()
        if bud:
            bud.is_eligible = False
            bud.ineligibility_reason = reason
        db.commit()
    except Exception as e:
        logger.warning(f"Error marking session expired for account {account_id}: {e}")
    finally:
        db.close()


async def scrape_credits_from_active_session(account_id: int) -> Optional[float]:
    """
    Checks active page or opens headless browser with account persistent profile to scrape live credits.
    If Emergent redirects to /landing or /login, marks session EXPIRED & account DISCONNECTED (Login Required).
    """
    session_valid = False
    page = active_pages.get(account_id)
    if page and not page.is_closed():
        if await _is_dashboard_page(page):
            session_valid = True
            await _scrape_and_record_credits(page, account_id)
        else:
            _mark_session_expired(account_id)
            return None
    else:
        cdp_port = 9222 + (account_id % 100)
        cdp_url = f"http://127.0.0.1:{cdp_port}"
        pw = await async_playwright().start()
        try:
            connected = False
            try:
                r = requests.get(f"{cdp_url}/json/version", timeout=1)
                if r.status_code == 200:
                    browser = await pw.chromium.connect_over_cdp(cdp_url)
                    ctx = browser.contexts[0]
                    p = ctx.pages[0] if ctx.pages else await ctx.new_page()
                    if await _is_dashboard_page(p):
                        session_valid = True
                        await _scrape_and_record_credits(p, account_id)
                    else:
                        _mark_session_expired(account_id)
                    connected = True
                    await browser.close()
            except Exception:
                pass

            if not connected:
                manager = MultiAccountSessionManager()
                profile_dir = manager._get_browser_profile_dir(account_id)
                if profile_dir and os.path.exists(profile_dir):
                    cleanup_stale_profile_locks(profile_dir)
                    chrome_candidates = [
                        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                        r"C:\Users\Admin\AppData\Local\ms-playwright\chromium-1248\chrome-win64\chrome.exe",
                    ]
                    exe_path = next((c for c in chrome_candidates if os.path.exists(c)), None)
                    context = await pw.chromium.launch_persistent_context(
                        user_data_dir=profile_dir,
                        executable_path=exe_path,
                        headless=True,
                        args=["--no-first-run", "--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
                    )
                    try:
                        p = context.pages[0] if context.pages else await context.new_page()
                        await p.goto("https://app.emergent.sh/home", timeout=20000, wait_until="domcontentloaded")
                        await asyncio.sleep(3.0)
                        if await _is_dashboard_page(p):
                            session_valid = True
                            await _scrape_and_record_credits(p, account_id)
                        else:
                            _mark_session_expired(account_id, f"Emergent redirected to {p.url} — session expired, Sign In required.")
                            return None
                    finally:
                        await context.close()
        except Exception as e:
            logger.warning(f"Error checking live credits headless: {e}")
        finally:
            await pw.stop()

    if not session_valid:
        return None

    db = SessionLocal()
    try:
        from app.models.credit import CreditSnapshot
        snap = db.query(CreditSnapshot).filter(CreditSnapshot.account_id == account_id).order_by(CreditSnapshot.recorded_at.desc()).first()
        return float(snap.available_credits) if snap else None
    finally:
        db.close()


def get_progress(account_id: int) -> Dict[str, Any]:
    return login_progress.get(
        account_id,
        {
            "status": "IDLE",
            "step": "Ready",
            "logs": [],
            "command_id": None,
            "otp_code": None,
            "is_complete": False,
            "error": None,
        },
    )


def append_log(account_id: int, message: str, level: str = "info"):
    now_str = datetime.now().strftime("%H:%M:%S")
    entry = {"time": now_str, "msg": message, "level": level}
    if account_id not in login_progress:
        login_progress[account_id] = {
            "status": "RUNNING",
            "step": "Starting",
            "logs": [],
            "command_id": None,
            "otp_code": None,
            "screenshot_url": None,
            "is_complete": False,
            "error": None,
        }
    login_progress[account_id]["logs"].append(entry)
    logger.info(f"[Acc {account_id}] {message}")


async def _save_page_screenshot(page: Page, account_id: int):
    try:
        shot_dir = "d:/emargent/frontend/public/login_snapshots"
        os.makedirs(shot_dir, exist_ok=True)
        shot_path = os.path.join(shot_dir, f"acc_{account_id}.png")
        await page.screenshot(path=shot_path, timeout=3000)
        if account_id in login_progress:
            login_progress[account_id]["screenshot_url"] = f"/sessions/{account_id}/login-snapshot?t={int(time.time() * 1000)}"
    except Exception:
        pass


async def execute_automated_login(
    account_id: int,
    email: str,
    password: str,
    mailbox_email: Optional[str] = None,
    user_id: Optional[int] = None,
    client_ip: Optional[str] = None,
):
    """
    Complete end-to-end automated Emergent authentication:
    1. Launches headed Chrome with account isolated profile.
    2. Navigates to app.emergent.sh.
    3. Types email and password, clicks Login.
    4. Detects OTP challenge screen.
    5. Calls Phx Email API (employeeName='Mahendra Vishnoi') and streams live logs.
    6. Automatically types OTP into Emergent.
    7. Verifies dashboard and marks session ACTIVE.
    8. Leaves browser open on desktop.
    """
    manager = MultiAccountSessionManager()
    browser_exe = manager.find_dedicated_browser() or manager.find_system_browser()
    target_mailbox = (mailbox_email or email).strip()

    redacted_email = email[:3] + "***@" + email.split("@")[-1] if "@" in email else "***"

    browser_display_name = "Dedicated Chromium" if (browser_exe and "ms-playwright" in browser_exe.lower()) else "Chrome"

    login_progress[account_id] = {
        "status": "RUNNING",
        "step": f"1/5: Launching {browser_display_name}...",
        "logs": [],
        "command_id": None,
        "otp_code": None,
        "screenshot_url": None,
        "is_complete": False,
        "error": None,
    }

    append_log(account_id, f"🚀 Initiating automated login for {redacted_email}...")

    if not browser_exe:
        err = "Dedicated Chromium or Google Chrome executable not found on host."
        append_log(account_id, f"❌ {err}", "error")
        login_progress[account_id]["status"] = "FAILED"
        login_progress[account_id]["error"] = err
        login_progress[account_id]["is_complete"] = True
        return

    profile_dir = manager._get_browser_profile_dir(account_id)
    cleanup_stale_profile_locks(profile_dir)

    # Record audit log without plaintext password
    db = SessionLocal()
    try:
        audit = AuditLog(
            user_id=user_id,
            action="automated_login_started",
            resource_type="session",
            resource_id=str(account_id),
            details=f"Automated login workflow started for account {account_id} ({redacted_email}).",
            ip_address=client_ip,
        )
        db.add(audit)
        db.commit()
    finally:
        db.close()

    try:
        append_log(account_id, f"🌐 Launching visible {browser_display_name} (Profile: acc_{account_id})...")
        append_log(account_id, f"🔒 Zero-Bleed Isolation: Personal Chrome sessions/profiles are untouched.")

        cdp_port = 9222 + (account_id % 100)
        cdp_ready = False
        p = await async_playwright().start()

        if os.name == "nt":
            import ctypes
            args = f'--remote-debugging-port={cdp_port} --user-data-dir="{profile_dir}" --no-first-run --no-default-browser-check --disable-blink-features=AutomationControlled https://app.emergent.sh'
            res = ctypes.windll.shell32.ShellExecuteW(None, "open", browser_exe, args, None, 1)
            if res > 32:
                cdp_url = f"http://127.0.0.1:{cdp_port}"
                for _ in range(15):
                    await asyncio.sleep(0.5)
                    try:
                        r = requests.get(f"{cdp_url}/json/version", timeout=1)
                        if r.status_code == 200:
                            cdp_ready = True
                            break
                    except Exception:
                        pass
                if cdp_ready:
                    browser = await p.chromium.connect_over_cdp(cdp_url)
                    context = browser.contexts[0]
                    page = context.pages[0] if context.pages else await context.new_page()

        if not cdp_ready:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                executable_path=browser_exe,
                headless=False,
                args=[
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-blink-features=AutomationControlled",
                ],
                viewport=None,
            )
            page = context.pages[0] if context.pages else await context.new_page()

        active_pages[account_id] = page
        append_log(account_id, f"✨ {browser_display_name} connected successfully with isolated sandbox!")

        # STEP 2: Navigate / check page and wait for SPA redirect to finish
        login_progress[account_id]["step"] = "2/5: Checking session on Emergent..."
        append_log(account_id, "🔗 Navigating to https://app.emergent.sh...")
        if "emergent.sh" not in page.url.lower():
            await page.goto("https://app.emergent.sh", wait_until="domcontentloaded", timeout=30000)

        # Wait up to 8s for Emergent SPA to finish redirecting either to /landing (needs login) or /home (logged in)
        already_logged_in = False
        for _ in range(8):
            await asyncio.sleep(1.0)
            url_low = page.url.lower()
            if "/landing" in url_low or "/login" in url_low:
                break
            try:
                if await page.locator("button:has-text('Continue with Email'), button:has-text('Continue with Google')").first.is_visible(timeout=300):
                    break
            except Exception:
                pass
            if await _is_dashboard_page(page):
                already_logged_in = True
                break

        # Check if already authenticated on dashboard
        if already_logged_in:
            append_log(account_id, "🎉 Already authenticated! Emergent dashboard verified.")
            _mark_session_active(account_id)
            await _scrape_and_record_credits(page, account_id)
            login_progress[account_id]["status"] = "SUCCESS"
            login_progress[account_id]["step"] = "Authenticated"
            login_progress[account_id]["is_complete"] = True
            await _keep_browser_open(page, account_id)
            return

        # STEP 3: Fill Credentials
        login_progress[account_id]["step"] = "3/5: Filling credentials..."
        append_log(account_id, "🔑 Preparing login form...")
        credentials_submitted = False

        try:
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            email_loc = page.locator("input#email:visible, input[name='email']:visible, input[type='email']:visible").first
            pass_loc = page.locator("input#password:visible, input[name='password']:visible, input[type='password']:visible").first

            # 1. Click 'Continue with Email' if email/password form is not yet visible
            if not await email_loc.is_visible(timeout=1200):
                for _attempt in range(4):
                    btn = page.locator("button:has-text('Continue with Email'):visible").first
                    if await btn.is_visible(timeout=3000):
                        await btn.evaluate("e => e.scrollIntoView({block: 'center', inline: 'center'})")
                        await asyncio.sleep(0.2)
                        await btn.click(timeout=5000)
                        await asyncio.sleep(1.5)
                    if await email_loc.is_visible(timeout=1500):
                        break
                    await asyncio.sleep(0.8)

            # 2. Switch from Sign Up to Sign In mode if Sign Up name input or 'Sign in' toggle is visible
            name_loc = page.locator("input#name:visible, input[name='name']:visible").first
            login_submit_loc = page.locator("button[data-testid='login-submit-button']:visible").first
            if await name_loc.is_visible(timeout=800) or not await login_submit_loc.is_visible(timeout=800):
                for _attempt in range(3):
                    if await login_submit_loc.is_visible(timeout=800) and not await name_loc.is_visible(timeout=300):
                        break
                    signin_link = page.get_by_text("Sign in", exact=True).last
                    if await signin_link.is_visible(timeout=1500):
                        # Center in viewport so sticky header never intercepts pointer events
                        await signin_link.evaluate("e => e.scrollIntoView({block: 'center', inline: 'center'})")
                        await asyncio.sleep(0.2)
                        try:
                            await signin_link.click(timeout=5000)
                        except Exception:
                            await signin_link.evaluate("e => e.click()")
                        await asyncio.sleep(1.2)

            # 3. Verify & Enter Email and Password
            email_visible = await email_loc.is_visible(timeout=3000)
            pass_visible = await pass_loc.is_visible(timeout=3000)

            if not email_visible or not pass_visible:
                await _save_page_screenshot(page, account_id)
                append_log(account_id, "⚠️ Emergent Email/Password inputs did not open automatically. Please complete login in Chrome.", "warn")
            elif await page.locator("input[name='cf-turnstile-response'], iframe[src*='challenges.cloudflare.com']:visible").count() > 0:
                await _save_page_screenshot(page, account_id)
                append_log(account_id, "🛡️ Cloudflare verification challenge detected in Chrome. Please complete verification and click Login directly in Chrome.", "warn")
                login_progress[account_id]["step"] = "Waiting for Cloudflare verification in Chrome..."
                login_progress[account_id]["status"] = "OTP_WAITING"
                await _keep_browser_open(page, account_id)
                return
            elif not password:
                await email_loc.evaluate("e => e.scrollIntoView({block: 'center'})")
                await email_loc.click(timeout=5000)
                await email_loc.fill(email)
                await _save_page_screenshot(page, account_id)
                append_log(account_id, "⚠️ No saved password provided — please enter password in Chrome window.", "warn")
            else:
                await email_loc.evaluate("e => e.scrollIntoView({block: 'center'})")
                await email_loc.click(timeout=5000)
                await email_loc.fill(email)
                await pass_loc.evaluate("e => e.scrollIntoView({block: 'center'})")
                await pass_loc.click(timeout=5000)
                await pass_loc.fill(password)

                if (await email_loc.input_value()) != email:
                    await email_loc.click(timeout=5000)
                    await page.keyboard.press("Control+A")
                    await page.keyboard.type(email, delay=10)
                if not await pass_loc.input_value():
                    await pass_loc.click(timeout=5000)
                    await page.keyboard.press("Control+A")
                    await page.keyboard.type(password, delay=10)

                append_log(account_id, "📝 Email and password entered into Emergent form.")

                # 4. Submit Form via real Playwright click
                login_btn = page.locator("button[data-testid='login-submit-button']:visible, button:has-text('Login'):visible, button:has-text('Log In'):visible, button[type='submit']:visible").first
                if await login_btn.is_visible(timeout=3000):
                    append_log(account_id, "🔘 Submitting credentials...")
                    await login_btn.evaluate("e => e.scrollIntoView({block: 'center', inline: 'center'})")
                    await asyncio.sleep(0.2)
                    await login_btn.click(timeout=5000)
                    credentials_submitted = True
                else:
                    await pass_loc.press("Enter")
                    credentials_submitted = True

        except Exception as form_err:
            append_log(account_id, f"ℹ️ Note on automated entry: {form_err}. Credentials can also be typed in visible Chrome window.", "info")

        await asyncio.sleep(2.0)
        await _save_page_screenshot(page, account_id)

        # STEP 4: Wait for OTP challenge screen
        login_progress[account_id]["step"] = "4/5: Waiting for OTP challenge..."
        append_log(account_id, "⏳ Waiting for Emergent OTP challenge screen to open...")

        otp_detected = False
        for _ in range(15):
            await asyncio.sleep(1)
            await _save_page_screenshot(page, account_id)
            if await page.locator("input[name='cf-turnstile-response'], iframe[src*='challenges.cloudflare.com']:visible").count() > 0:
                append_log(account_id, "🛡️ Cloudflare verification challenge appeared in Chrome. Please complete it directly in the Chrome window.", "warn")
                login_progress[account_id]["step"] = "Waiting for verification in Chrome..."
                login_progress[account_id]["status"] = "OTP_WAITING"
                await _keep_browser_open(page, account_id)
                return

            # Check for error alerts on page (e.g. wrong password or captcha)
            for err_sel in ["[role='alert']", ".text-red-500", ".text-destructive", "text=Invalid", "text=incorrect", "text=User not found"]:
                try:
                    err_el = page.locator(err_sel).first
                    if await err_el.is_visible(timeout=200):
                        err_text = await err_el.text_content()
                        if err_text and len(err_text.strip()) > 0:
                            append_log(account_id, f"⚠️ Emergent Page Message: {err_text.strip()}", "warn")
                            break
                except Exception:
                    pass

            if await _is_otp_screen(page):
                otp_detected = True
                break
            if await _is_dashboard_page(page):
                # Dashboard opened directly without OTP!
                append_log(account_id, "🎉 Logged in directly! Emergent dashboard confirmed.")
                _mark_session_active(account_id)
                await _scrape_and_record_credits(page, account_id)
                login_progress[account_id]["status"] = "SUCCESS"
                login_progress[account_id]["is_complete"] = True
                await _keep_browser_open(page, account_id)
                return

        if not otp_detected and not credentials_submitted:
            append_log(account_id, "⚠️ Login form could not be submitted automatically. Please click 'Sign in' and submit credentials in Chrome; enter OTP below if prompted.", "warn")
            login_progress[account_id]["step"] = "Waiting for manual login in Chrome..."
            login_progress[account_id]["status"] = "OTP_WAITING"
            await _keep_browser_open(page, account_id)
            return

        if not otp_detected:
            append_log(account_id, "⚠️ OTP screen not auto-detected within 15s. Checking for MFA prompts...", "warn")

        append_log(account_id, f"📡 Triggering Phx Email API for mailbox: {target_mailbox} (Employee: Mahendra Vishnoi)...")
        login_progress[account_id]["step"] = "4/5: Retrieving OTP from Phx API..."

        # Callback to pipe Phx API progress directly into login_progress
        def on_phx_log(msg: str):
            append_log(account_id, msg)
            if "Command created with ID #" in msg:
                try:
                    cid = msg.split("#")[-1].split(" ")[0].strip("()")
                    login_progress[account_id]["command_id"] = cid
                except Exception:
                    pass

        # Run fetch_email_otp in thread pool to prevent blocking asyncio loop
        clean_otp = await asyncio.to_thread(
            fetch_email_otp,
            email=target_mailbox,
            employee_name="Mahendra Vishnoi",
            max_wait_sec=180,
            log_callback=on_phx_log,
        )

        if clean_otp:
            login_progress[account_id]["otp_code"] = clean_otp
            append_log(account_id, f"✅ Phx OTP Retrieved: {clean_otp}")
            login_progress[account_id]["step"] = f"5/5: Entering OTP ({clean_otp})..."

            # STEP 5: Type OTP into Emergent input
            entered = await _type_otp_into_emergent(page, clean_otp)
            if entered:
                append_log(account_id, f"⌨️ Typed OTP {clean_otp} into Emergent verification box.")
            else:
                append_log(account_id, f"⚠️ Could not find OTP input box automatically. Please type {clean_otp} in the Chrome window.", "warn")

            # Wait for dashboard
            append_log(account_id, "⏳ Verifying authenticated Emergent dashboard...")
            for _ in range(15):
                await asyncio.sleep(1.5)
                if await _is_dashboard_page(page):
                    append_log(account_id, "🎉 Dashboard verified successfully! Session marked ACTIVE.")
                    _mark_session_active(account_id)
                    await _scrape_and_record_credits(page, account_id)
                    login_progress[account_id]["status"] = "SUCCESS"
                    login_progress[account_id]["is_complete"] = True
                    await _keep_browser_open(page, account_id)
                    return

            append_log(account_id, "⚠️ Verification check timed out. If dashboard is open, click 'Confirm Dashboard' in Hub.", "warn")
            login_progress[account_id]["status"] = "OTP_WAITING"
        else:
            append_log(account_id, "⚠️ Phx API did not find OTP in Inbox or Spam within polling window.", "warn")
            append_log(account_id, "ℹ️ You can enter the OTP code manually in the input box below.", "info")
            login_progress[account_id]["status"] = "OTP_WAITING"

        # Keep browser open indefinitely so user can see it
        await _keep_browser_open(page, account_id)

    except Exception as e:
        logger.error(f"Error during automated login: {e}", exc_info=True)
        raw_err = str(e)
        if "Opening in existing browser session" in raw_err:
            clean_err = "The browser profile was already in use by a background process. Stale processes have been terminated. Please try again."
        elif "Call log:" in raw_err:
            clean_err = raw_err.split("Call log:")[0].strip()
        else:
            clean_err = raw_err[:250]
        append_log(account_id, f"❌ Automation Error: {clean_err}", "error")
        login_progress[account_id]["status"] = "FAILED"
        login_progress[account_id]["error"] = clean_err
        login_progress[account_id]["is_complete"] = True


async def _is_dashboard_page(page: Page) -> bool:
    try:
        url = page.url.lower()
        if "/landing" in url or "/login" in url or "/signup" in url or "/auth" in url:
            return False
        # Never treat login/landing screens with auth buttons as authenticated
        for login_sel in ["button:has-text('Continue with Email')", "button:has-text('Continue with Google')"]:
            try:
                if await page.locator(login_sel).first.is_visible(timeout=200):
                    return False
            except Exception:
                pass
        # Positive authenticated URL paths
        if any(x in url for x in ["/home", "/projects", "/dashboard", "/workspace"]):
            return True
        # Strict authenticated dashboard DOM elements (never generic marketing text like 'Projects')
        for sel in ["[data-testid='menubar-avatar-button']", "button:has-text('Sign Out')", "button:has-text('Log out')", "button:has-text('Create video')", "text=App builder"]:
            if await page.locator(sel).first.is_visible(timeout=400):
                return True
    except Exception:
        pass
    return False


async def _is_otp_screen(page: Page) -> bool:
    try:
        # Never mistake landing or email/password login screens for an OTP screen
        if await page.locator("button:has-text('Continue with Email'):visible").first.is_visible(timeout=200):
            return False
        if await page.locator("input#password:visible, input[type='password']:visible").first.is_visible(timeout=200):
            return False

        selectors = [
            "text=Enter the 6-digit code",
            "text=6-digit code",
            "text=Resend in",
            "text=Enter verification code",
            "text=Verification code",
            "text=Check your email",
            "text=We sent a code",
            "input[autocomplete='one-time-code']:visible",
            "input[data-input-otp='true']:visible",
            "input[name='otp']:visible",
            "input[name='code']:visible",
            "input[placeholder*='code' i]:visible",
            "input[placeholder*='otp' i]:visible",
            "input[placeholder*='verification' i]:visible",
        ]
        for sel in selectors:
            if await page.locator(sel).first.is_visible(timeout=400):
                return True
        visible_inputs = page.locator("input:not([type='hidden']):visible")
        if await visible_inputs.count() >= 4:
            return True
    except Exception:
        pass
    return False


async def _type_otp_into_emergent(page: Page, otp: str) -> bool:
    try:
        # Never treat landing/password screens as OTP fields
        if await page.locator("button:has-text('Continue with Email'):visible").first.is_visible(timeout=250):
            return False
        if await page.locator("input#password:visible, input[type='password']:visible").first.is_visible(timeout=250):
            return False

        otp_inputs = page.locator(
            "input[autocomplete='one-time-code']:visible, "
            "input[data-input-otp='true']:visible, "
            "input[name='otp']:visible, "
            "input[name='code']:visible, "
            "input[inputmode='numeric']:visible, "
            "input[maxlength='1']:visible, "
            "input[placeholder*='code' i]:visible, "
            "input[placeholder*='otp' i]:visible"
        )
        count = await otp_inputs.count()
        if count == 0:
            otp_inputs = page.locator(
                "input:not([type='hidden']):not([name='enterprise-sso-email']):not([id='email']):not([type='password']):visible"
            )
            count = await otp_inputs.count()

        if count == 0:
            return False
        if count == 1:
            await otp_inputs.first.click()
            await otp_inputs.first.fill(otp)
            await _click_submit_if_present(page)
            return True
        else:
            # Multi-box OTP: click first box and type digits sequentially
            await otp_inputs.first.click()
            await page.keyboard.type(otp, delay=100)
            # Fallback if boxes did not auto-advance
            if count >= len(otp):
                last_val = await otp_inputs.nth(len(otp) - 1).input_value()
                if not last_val:
                    for idx, ch in enumerate(otp[:count]):
                        await otp_inputs.nth(idx).fill(ch)
            await _click_submit_if_present(page)
            return True
    except Exception as e:
        logger.warning(f"Error typing OTP: {e}")
        return False


async def _click_submit_if_present(page: Page):
    try:
        btn = page.locator("button:has-text('Verify'):visible, button:has-text('Submit'):visible, button:has-text('Continue'):visible, button[type='submit']:visible").first
        if await btn.is_visible(timeout=1000):
            await btn.click()
    except Exception:
        pass


def _mark_session_active(account_id: int):
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        sess = db.query(AccountSession).filter(AccountSession.account_id == account_id).first()
        if sess:
            sess.session_status = "ACTIVE"
            sess.reauth_required = False
            sess.reauth_reason = None
            sess.last_validated_at = now
            sess.last_active_at = now

        acc = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
        if acc:
            acc.connection_status = "CONNECTED"
            acc.last_connected_at = now

        db.commit()
    finally:
        db.close()


async def _keep_browser_open(page: Page, account_id: Optional[int] = None):
    try:
        # Keep process open indefinitely (up to 24h) unless browser is manually closed by user
        while not page.is_closed():
            await asyncio.sleep(5)
    except Exception:
        pass
    finally:
        if account_id is not None:
            active_pages.pop(account_id, None)

