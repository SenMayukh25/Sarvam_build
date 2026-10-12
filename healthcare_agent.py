import json
import os
import sys
import uuid
from datetime import datetime

# Minimal .env loader (stdlib only, no extra dependency).
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
try:
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _, _value = _line.partition("=")
            os.environ.setdefault(_key.strip(), _value.strip().strip('"').strip("'"))
except FileNotFoundError:
    pass

api_key = os.environ.get("SARVAM_API_KEY", "").strip()
if not api_key:
    sys.exit("SARVAM_API_KEY is not set. Paste your key into .env and run again.")

from sarvamai import SarvamAI
from sarvamai.core.api_error import ApiError

# sarvam-105b is Sarvam's model tuned for agentic/tool-calling workflows.
# (sarvam-105b-conversations is the dialogue/voice-agent variant.)
MODEL = "sarvam-105b"

client = SarvamAI(api_subscription_key=api_key)

# --- In-memory demo store (session-only). Replace these with your real backend: ---
# a calendar/booking system, an insurer/TPA API, and a messaging/telephony provider.
FAKE_POLICIES = {
    "POL123": {"insurer": "Example Health Insurance", "sum_insured": 500000, "active": True},
    "POL999": {"insurer": "Example Health Insurance", "sum_insured": 0, "active": False},
}
appointments = []  # booked appointments
preauths = {}      # policy_id -> latest pre-authorization record
claims = []        # submitted claims
reminders = []     # scheduled reminders

SYSTEM_PROMPT = (
    "You are a healthcare front-desk assistant. You help patients with three things: "
    "(1) booking appointments, (2) insurance paperwork — verifying cashless eligibility, "
    "raising/updating pre-authorization, and coordinating claims, and (3) scheduling "
    "follow-up, care, and re-engagement reminders. Collect the details you need, then call "
    "the matching tool. Keep replies short and friendly, and always relay the confirmation "
    "ID or reference the tool returns."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a clinic appointment for a patient with a doctor at a given date/time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string", "description": "Patient's full name"},
                    "doctor": {"type": "string", "description": "Preferred doctor"},
                    "appointment_time": {
                        "type": "string",
                        "description": "Requested date and time as YYYY-MM-DD HH:MM",
                    },
                },
                "required": ["patient_name", "doctor", "appointment_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_insurance",
            "description": "Verify a patient's insurance policy and cashless eligibility before treatment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string", "description": "Patient's full name"},
                    "policy_id": {"type": "string", "description": "Insurance policy ID, e.g. POL123"},
                },
                "required": ["patient_name", "policy_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_preauthorization",
            "description": "Raise or update an insurance pre-authorization request for a procedure/amount.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string", "description": "Patient's full name"},
                    "policy_id": {"type": "string", "description": "Insurance policy ID"},
                    "procedure": {"type": "string", "description": "Planned procedure/treatment"},
                    "estimated_amount": {"type": "number", "description": "Estimated cost in INR"},
                },
                "required": ["patient_name", "policy_id", "procedure", "estimated_amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_claim_status",
            "description": "Check the status of a submitted insurance claim by claim ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string", "description": "Claim ID, e.g. CLM-00001"},
                },
                "required": ["claim_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_reminder",
            "description": "Schedule a follow-up, care, or re-engagement reminder for a patient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string", "description": "Patient's full name"},
                    "reminder_type": {
                        "type": "string",
                        "enum": ["follow_up", "medication", "re_engagement"],
                        "description": "Kind of reminder",
                    },
                    "message": {"type": "string", "description": "What the reminder should say"},
                    "due_at": {
                        "type": "string",
                        "description": "When to send, as YYYY-MM-DD HH:MM",
                    },
                },
                "required": ["patient_name", "reminder_type", "message", "due_at"],
            },
        },
    },
]


def _parse_when(value):
    """Parse a 'YYYY-MM-DD HH:MM' string, returning None if invalid."""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def book_appointment(patient_name, doctor, appointment_time):
    """STUB backend — replace body with a call to your real calendar/booking system.

    Validates the requested time and rejects double-bookings of the same doctor/slot.
    """
    when = _parse_when(appointment_time)
    if when is None:
        return {
            "status": "error",
            "message": f"Could not understand the date/time '{appointment_time}'. Use YYYY-MM-DD HH:MM.",
        }

    slot = when.strftime("%Y-%m-%d %H:%M")
    for existing in appointments:
        if existing["doctor"].lower() == doctor.strip().lower() and existing["appointment_time"] == slot:
            return {
                "status": "conflict",
                "message": f"{doctor} is already booked at {slot}. Please choose another time.",
            }

    confirmation_id = "APT-" + uuid.uuid4().hex[:6].upper()
    record = {
        "confirmation_id": confirmation_id,
        "status": "confirmed",
        "patient_name": patient_name.strip(),
        "doctor": doctor.strip(),
        "appointment_time": slot,
    }
    appointments.append(record)
    return record


def verify_insurance(patient_name, policy_id):
    """STUB backend — replace with a call to your insurer/TPA eligibility API."""
    policy = FAKE_POLICIES.get(policy_id.strip().upper())
    if policy is None:
        return {"status": "not_found", "patient_name": patient_name, "policy_id": policy_id}
    return {
        "status": "eligible" if policy["active"] else "inactive",
        "patient_name": patient_name,
        "policy_id": policy_id.strip().upper(),
        "insurer": policy["insurer"],
        "sum_insured": policy["sum_insured"],
        "cashless": bool(policy["active"]),
    }


def request_preauthorization(patient_name, policy_id, procedure, estimated_amount):
    """STUB backend — replace with a call to your insurer/TPA pre-auth API."""
    policy = FAKE_POLICIES.get(policy_id.strip().upper())
    if policy is None or not policy["active"]:
        return {
            "status": "rejected",
            "reason": "policy not found or inactive",
            "policy_id": policy_id,
        }
    if float(estimated_amount) > policy["sum_insured"]:
        return {
            "status": "rejected",
            "reason": "estimated amount exceeds sum insured",
            "policy_id": policy_id.strip().upper(),
            "sum_insured": policy["sum_insured"],
            "estimated_amount": estimated_amount,
        }
    preauth_id = "PA-" + uuid.uuid4().hex[:6].upper()
    record = {
        "preauth_id": preauth_id,
        "status": "approved",
        "patient_name": patient_name,
        "policy_id": policy_id.strip().upper(),
        "procedure": procedure,
        "estimated_amount": float(estimated_amount),
    }
    preauths[policy_id.strip().upper()] = record
    return record


def check_claim_status(claim_id):
    """STUB backend — replace with a call to your claims/TPA system."""
    for claim in claims:
        if claim["claim_id"].lower() == claim_id.strip().lower():
            return claim
    return {"status": "not_found", "claim_id": claim_id}


def schedule_reminder(patient_name, reminder_type, message, due_at):
    """STUB backend — replace with a call to your messaging/telephony provider."""
    when = _parse_when(due_at)
    if when is None:
        return {
            "status": "error",
            "message": f"Could not understand the time '{due_at}'. Use YYYY-MM-DD HH:MM.",
        }
    reminder_id = "REM-" + uuid.uuid4().hex[:6].upper()
    record = {
        "reminder_id": reminder_id,
        "status": "scheduled",
        "patient_name": patient_name.strip(),
        "reminder_type": reminder_type,
        "message": message,
        "due_at": when.strftime("%Y-%m-%d %H:%M"),
    }
    reminders.append(record)
    return record


TOOL_IMPL = {
    "book_appointment": book_appointment,
    "verify_insurance": verify_insurance,
    "request_preauthorization": request_preauthorization,
    "check_claim_status": check_claim_status,
    "schedule_reminder": schedule_reminder,
}


def run_turn(messages):
    """One agentic turn: call the model, run any requested tools, loop until it replies in text."""
    for _ in range(5):  # safety cap on tool-calling rounds
        response = client.chat.completions(model=MODEL, messages=messages, tools=TOOLS)
        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content

        # Echo the assistant's tool-call request back into the conversation...
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        # ...then feed each tool's result back as a tool message.
        for tc in msg.tool_calls:
            fn = TOOL_IMPL.get(tc.function.name)
            try:
                args = json.loads(tc.function.arguments or "{}")
                if fn is None:
                    result = {"error": f"unknown tool {tc.function.name}"}
                else:
                    result = fn(**args)
            except Exception as e:  # never let a bad tool call crash the loop
                result = {"error": f"{type(e).__name__}: {e}"}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                }
            )

    return "I wasn't able to complete the booking. Please try again."


def main():
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("Healthcare booking agent (type 'quit' to exit)\n")
    while True:
        user = input("Patient: ").strip()
        if user.lower() in {"quit", "exit"}:
            break
        if not user:
            continue
        messages.append({"role": "user", "content": user})
        try:
            reply = run_turn(messages)
        except ApiError as e:
            print(f"API error {e.status_code}: {e.body}")
            messages.pop()  # drop the unanswered user turn
            continue
        messages.append({"role": "assistant", "content": reply})
        print(f"Agent: {reply}\n")


if __name__ == "__main__":
    main()
