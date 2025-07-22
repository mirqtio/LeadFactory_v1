#!/usr/bin/env python3
"""
PRP Ingest Script - Fixed for Current PRP Format
Scans .claude/PRPs/ directory and queues PRPs that aren't already in Redis queues
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import redis


def parse_prp_file(file_path):
    """Parse PRP markdown file for metadata using the current format."""
    with open(file_path, "r") as f:
        content = f.read()

    metadata = {}

    # Extract title from # heading
    title_match = re.search(r"^# ([^#\n]+)", content, re.MULTILINE)
    if title_match:
        full_title = title_match.group(1).strip()
        metadata["title"] = full_title

        # Extract ID from title (e.g., "P0-028 - Design System" -> "P0-028")
        id_match = re.search(r"(P\d+-\d+)", full_title)
        if id_match:
            metadata["id"] = id_match.group(1)

    # Alternative format: Check for "Task ID:" or "## Task ID:" line
    if not metadata.get("id"):
        task_id_match = re.search(r"(?:##\s*)?Task ID:\s*(P\d+-\d+)", content, re.MULTILINE)
        if task_id_match:
            metadata["id"] = task_id_match.group(1)

    # Handle numeric IDs that start with numbers (convert to P format)
    if not metadata.get("id"):
        numeric_match = re.search(r"(\d{4})", content)
        if numeric_match and title_match:
            # Convert 1042 -> P1-042 format
            num = numeric_match.group(1)
            if len(num) == 4:
                metadata["id"] = f"P{num[0]}-{num[1:4]}"

    # Extract priority
    priority_match = re.search(r"\*\*Priority\*\*:\s*(.+)", content)
    if priority_match:
        metadata["priority"] = priority_match.group(1).strip()

    # Extract status
    status_match = re.search(r"\*\*Status\*\*:\s*(.+)", content)
    if status_match:
        metadata["status"] = status_match.group(1).strip()

    # Extract estimated effort
    effort_match = re.search(r"\*\*Estimated Effort\*\*:\s*(.+)", content)
    if effort_match:
        metadata["estimated_effort"] = effort_match.group(1).strip()

    # Extract first paragraph as description
    desc_match = re.search(r"## Goal & Success Criteria\n(.+?)(?=\n\n|\*\*)", content, re.DOTALL)
    if desc_match:
        metadata["description"] = desc_match.group(1).strip()

    # Default stage based on status
    if metadata.get("status", "").lower() in ["not started", "new"]:
        metadata["priority_stage"] = "dev"
    elif "validation" in metadata.get("status", "").lower():
        metadata["priority_stage"] = "validation"
    elif "integration" in metadata.get("status", "").lower():
        metadata["priority_stage"] = "integration"
    else:
        metadata["priority_stage"] = "dev"

    return metadata


def is_prp_already_queued(redis_client, prp_id):
    """Check if PRP is already in any Redis queue or processed."""
    queues = ["dev_queue", "validation_queue", "integration_queue", "orchestrator_queue"]

    for queue in queues:
        items = redis_client.lrange(queue, 0, -1)
        if prp_id.encode() in items:
            return True

    # Check if already processed
    prp_key = f"prp:{prp_id}"
    if redis_client.exists(prp_key):
        status = redis_client.hget(prp_key, "status")
        if status and status.decode() in ["complete", "processed"]:
            return True

    return False


def main():
    prp_dir = Path(".claude/PRPs")
    if not prp_dir.exists():
        print(f"PRP directory not found: {prp_dir}")
        sys.exit(1)

    # Connect to Redis with URL correction for docker vs localhost
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    if "redis://redis:" in redis_url:
        redis_url = redis_url.replace("redis://redis:", "redis://localhost:")

    try:
        r = redis.from_url(redis_url)
        r.ping()
        print(f"✅ Connected to Redis: {redis_url}")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        sys.exit(1)

    queued_count = 0
    skipped_count = 0

    # Process all markdown files
    for prp_file in prp_dir.glob("*.md"):
        try:
            metadata = parse_prp_file(prp_file)
            if not metadata.get("id"):
                print(f"⚠️  No ID found in {prp_file.name}")
                continue

            prp_id = metadata["id"]

            # Skip if already queued or processed
            if is_prp_already_queued(r, prp_id):
                print(f"⏭️  Skipping {prp_id} (already queued/processed)")
                skipped_count += 1
                continue

            priority_stage = metadata.get("priority_stage", "dev").lower()

            # Map stage to queue
            queue_map = {
                "dev": "dev_queue",
                "development": "dev_queue",
                "validation": "validation_queue",
                "integration": "integration_queue",
                "orchestrator": "orchestrator_queue",
            }

            target_queue = queue_map.get(priority_stage, "dev_queue")

            # Create PRP hash
            prp_key = f"prp:{prp_id}"
            prp_data = {
                "id": prp_id,
                "title": metadata.get("title", prp_file.stem),
                "description": metadata.get("description", ""),
                "priority": metadata.get("priority", ""),
                "priority_stage": priority_stage,
                "status": "queued",
                "retry_count": "0",
                "added_at": datetime.utcnow().isoformat(),
                "source_file": str(prp_file),
                "estimated_effort": metadata.get("estimated_effort", ""),
                "content": prp_file.read_text(),
            }

            # Store in Redis
            r.hset(prp_key, mapping=prp_data)
            r.lpush(target_queue, prp_id)

            print(f"✅ Queued {prp_id} → {target_queue}")
            queued_count += 1

        except Exception as e:
            print(f"❌ Failed to process {prp_file.name}: {e}")

    print(f"\n📊 Ingest complete: {queued_count} PRPs queued, {skipped_count} skipped")

    # Show queue status
    print("\n📋 Current Queue Status:")
    queues = ["dev_queue", "validation_queue", "integration_queue", "orchestrator_queue"]
    for queue in queues:
        count = r.llen(queue)
        print(f"  {queue}: {count} items")

    # Broadcast completion if any PRPs were queued
    if queued_count > 0:
        broadcast_msg = json.dumps(
            {
                "type": "system_broadcast",
                "message": f"PRP ingest complete: {queued_count} new PRPs queued, {skipped_count} already processed.",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        r.lpush("orchestrator_queue", broadcast_msg)
        print(f"\n📤 Sent broadcast to orchestrator_queue")


if __name__ == "__main__":
    main()
