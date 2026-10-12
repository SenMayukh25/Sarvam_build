import os
import sys

# Minimal .env loader (stdlib only, no extra dependency): populate os.environ
# from a .env file sitting next to this script.
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
    sys.exit("SARVAM_API_KEY is not set. Paste your key into .env (SARVAM_API_KEY=...) and run again.")

from sarvamai import SarvamAI

client = SarvamAI(api_subscription_key=api_key)

response = client.chat.completions(
    messages=[{"role": "user", "content": "Say hello in one short sentence."}],
    model="sarvam-105b-conversations",
)

print(response.choices[0].message.content)

