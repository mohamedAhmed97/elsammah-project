"""Quick test script for the BPO Ops Superflow API."""
import json
import time
import urllib.request

BASE = "http://localhost:8000"

# 1. Start a flow
body = json.dumps({
    "flow_type": "schedule",
    "queue_id": "Q-SUPPORT-01",
    "time_window": "2025-W24",
}).encode()

req = urllib.request.Request(
    f"{BASE}/api/flow/start",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        print(f"[OK] Flow started: {json.dumps(result, indent=2)}")
        run_id = result["run_id"]
except Exception as e:
    print(f"[FAIL] Failed to start flow: {e}")
    exit(1)

# 2. Poll state a few times
for i in range(5):
    time.sleep(2)
    try:
        with urllib.request.urlopen(f"{BASE}/api/flow/{run_id}/state") as resp:
            state = json.loads(resp.read())
            print(f"\n[POLL {i+1}] Step: {state['current_step']}, HITL: {state['hitl_status']}")
            print(f"  Audit log entries: {len(state['audit_log'])}")
            if state.get("error_state"):
                print(f"  [WARN] Error: {state['error_state']['error_type']}: {state['error_state']['message']}")
                break
    except Exception as e:
        print(f"  Poll error: {e}")
