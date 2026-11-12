import time
import requests
from typing import Optional, Callable

def fetch_email_otp(
    email: str,
    employee_name: str = "Mahendra Vishnoi",
    max_wait_sec: int = 180,
    log_callback: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    """
    Phx Email OTP Automation Workflow:
    Step 1: Create Email Command (GET create-email-command.asp)
    Step 2: Wait 8 seconds, then poll every 5 seconds (GET unstop-otp.asp)
    Spam fallback: If not found in Inbox after 60s, creates Spam command and polls for 60s.
    """
    def log(msg: str):
        if log_callback:
            try:
                log_callback(msg)
            except Exception:
                pass

    if not email:
        log("No email address provided for OTP retrieval.")
        return None

    clean_email = email.strip()
    folders = ["Inbox", "Spam"]
    start_time = time.time()
    poll_interval = 5.0

    for folder in folders:
        elapsed = int(time.time() - start_time)
        if elapsed >= max_wait_sec:
            log(f"Max wait time of {max_wait_sec}s reached.")
            break

        command_id = None
        log(f"Step 1: Creating email command for {clean_email} in '{folder}' (Employee: {employee_name})...")
        try:
            cmd_url = (
                f"https://m.phx.co.in/automation/api/email-api/create-email-command.asp"
                f"?emailAddress={requests.utils.quote(clean_email)}"
                f"&employeeName={requests.utils.quote(employee_name)}"
                f"&commandType={folder}"
            )
            r = requests.get(cmd_url, timeout=15)
            if r.status_code == 200:
                res = r.json()
                if res.get("status") == "success":
                    command_id = res.get("data", {}).get("commandId")
                    log(f"Step 1 Success: Command created with ID #{command_id} ({folder})")
                else:
                    log(f"Step 1 Response: {res.get('message', res)}")
            else:
                log(f"Step 1 HTTP Error: {r.status_code}")
        except Exception as e:
            log(f"Step 1 Exception: {str(e)}")

        if not command_id:
            log("No command ID received. Waiting 5s before next attempt...")
            time.sleep(5.0)
            continue

        log(f"Waiting initial 8s for email delivery to {folder}...")
        time.sleep(8.0)
        folder_start = time.time()
        attempt = 1

        while (time.time() - folder_start) < 60.0 and (time.time() - start_time) < max_wait_sec:
            try:
                poll_url = (
                    f"https://m.phx.co.in/automation/api/email-api/unstop-otp.asp"
                    f"?fileid={command_id}&limit=1&action=unstop_otp"
                )
                pr = requests.get(poll_url, timeout=15)
                if pr.status_code == 200:
                    raw_text = pr.text.strip()
                    if not raw_text:
                        log(f"Poll #{attempt} ({folder}): Checking mailbox for incoming email...")
                    else:
                        try:
                            pdata = pr.json()
                            status_text = str(pdata.get("status", "")).lower()
                            if status_text == "success":
                                otp_val = pdata.get("data", {}).get("otp")
                                if otp_val:
                                    clean_otp = "".join(ch for ch in str(otp_val) if ch.isdigit())
                                    if len(clean_otp) in (4, 6, 8):
                                        log(f"Step 2 Success: OTP FOUND -> {clean_otp}")
                                        return clean_otp
                            else:
                                msg = pdata.get("message", "Pending delivery")
                                log(f"Poll #{attempt} ({folder}): {msg}")
                        except Exception:
                            log(f"Poll #{attempt} ({folder}): Awaiting mail arrival...")
                else:
                    log(f"Poll #{attempt} HTTP {pr.status_code}")
            except Exception as e:
                log(f"Poll #{attempt} ({folder}): Polling server...")

            attempt += 1
            time.sleep(poll_interval)

        log(f"No OTP found in '{folder}' within 60s.")

    log("OTP retrieval complete: No code found in Inbox or Spam.")
    return None

