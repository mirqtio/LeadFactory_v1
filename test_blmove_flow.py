#!/usr/bin/env python3
"""
Simple test of BLMOVE -> tmux flow
"""
import os
import subprocess
import time


def test_blmove_flow():
    print("🧪 Testing BLMOVE -> Tmux Flow")

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    print(f"🔗 Using Redis URL: {redis_url}")

    # 1. Check queue status
    result = subprocess.run(["redis-cli", "-u", redis_url, "LLEN", "dev_queue"], capture_output=True, text=True)

    queue_len = result.stdout.strip()
    print(f"📊 dev_queue length: {queue_len}")

    # 2. Try BLMOVE
    print("🔄 Attempting BLMOVE...")
    result = subprocess.run(
        ["redis-cli", "-u", redis_url, "BLMOVE", "dev_queue", "dev_queue:inflight", "RIGHT", "LEFT", "1"],
        capture_output=True,
        text=True,
        timeout=3,
    )

    if result.returncode == 0 and result.stdout.strip():
        prp_id = result.stdout.strip()
        print(f"✅ BLMOVE success: {prp_id}")

        # 3. Test tmux send
        tmux_target = "leadstack:dev-1"
        test_message = f"🚀 TEST MESSAGE: Processing {prp_id}"

        print(f"📤 Sending to tmux: {tmux_target}")

        # Send message
        proc1 = subprocess.run(["tmux", "send-keys", "-t", tmux_target, test_message], capture_output=True, text=True)

        # Send Enter
        proc2 = subprocess.run(["tmux", "send-keys", "-t", tmux_target, "Enter"], capture_output=True, text=True)

        if proc1.returncode == 0 and proc2.returncode == 0:
            print("✅ Tmux send successful")
        else:
            print(f"❌ Tmux send failed: {proc1.stderr} {proc2.stderr}")

        # 4. Check inflight queue
        result = subprocess.run(
            ["redis-cli", "-u", redis_url, "LRANGE", "dev_queue:inflight", "0", "-1"], capture_output=True, text=True
        )

        inflight = result.stdout.strip().split("\n") if result.stdout.strip() else []
        print(f"📋 Inflight queue: {inflight}")

        # 5. Move back to main queue for cleanup
        subprocess.run(
            ["redis-cli", "-u", redis_url, "LMOVE", "dev_queue:inflight", "dev_queue", "LEFT", "RIGHT"],
            capture_output=True,
        )

        print("✅ Test complete - PRP moved back to dev_queue")

    else:
        print("❌ BLMOVE failed or timed out")
        print(f"Return code: {result.returncode}")
        print(f"Stdout: {result.stdout}")
        print(f"Stderr: {result.stderr}")


if __name__ == "__main__":
    test_blmove_flow()
