"""
Validator for Email API responses.
Validates schemas for /create-email-command.asp and /unstop-otp.asp.
"""
from typing import Any, Dict, Optional, Tuple


def validate_create_command_response(data: Any) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates response from GET /create-email-command.asp.
    Expected contract:
    {
      "status": "success",
      "message": "Command added successfully",
      "data": {
        "commandId": "7591"
      }
    }
    Returns:
        (is_success, command_id, error_message)
    """
    if not isinstance(data, dict):
        return False, None, "Invalid response: payload is not a JSON object"

    status = data.get("status")
    if status != "success":
        error_msg = data.get("message") or data.get("error") or f"API returned non-success status: {status}"
        return False, None, str(error_msg)

    inner_data = data.get("data")
    if not isinstance(inner_data, dict):
        return False, None, "Invalid response: 'data' field is missing or not a JSON object"

    command_id = inner_data.get("commandId")
    if command_id is None or str(command_id).strip() == "":
        return False, None, "Invalid response: 'commandId' is missing or empty in data"

    return True, str(command_id).strip(), None


def validate_retrieve_otp_response(data: Any) -> Tuple[bool, bool, Optional[str], Optional[str]]:
    """
    Validates response from GET /unstop-otp.asp.
    Expected contract on OTP found:
    {
      "status": "success",
      "message": "OTP Found",
      "data": {
        "otp": "123456"
      }
    }
    Expected contract when pending/no OTP yet:
    {
      "status": "...",
      "message": "No OTP found" or similar,
      "data": ...
    }
    Returns:
        (is_valid_response, otp_found, otp_code, error_message)
    """
    if not isinstance(data, dict):
        return False, False, None, "Invalid response: payload is not a JSON object"

    status = data.get("status")
    message = str(data.get("message") or "")
    inner_data = data.get("data")

    # If status is success and otp exists in data
    if status == "success" and isinstance(inner_data, dict):
        otp = inner_data.get("otp")
        if otp:
            otp_str = str(otp).strip()
            if otp_str:
                return True, True, otp_str, None

    # Check if this is an expected "pending" / "no otp found" state
    pending_indicators = ["no otp", "not found", "waiting", "pending", "empty"]
    msg_lower = message.lower()
    if any(ind in msg_lower for ind in pending_indicators) or (status == "success" and not inner_data):
        return True, False, None, None

    # Check if there is an explicit failure/error
    if status in ("failed", "error"):
        error_msg = message or "Email API reported retrieval error"
        return False, False, None, error_msg

    # Any other structure where OTP is not present yet
    return True, False, None, None

