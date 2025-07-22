#!/usr/bin/env python3
"""
PRP Backlog Ingest Script
Scans backlog_prps/ directory and queues PRPs in Redis
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import redis


def parse_prp_file(file_path):
    """Parse PRP markdown file for metadata."""
    with open(file_path, "r") as f:
        content = f.read()

    # Extract front matter
    frontmatter_match = re.search(r"^---\n(.*?)\n---", content, re.DOTALL | re.MULTILINE)
    if not frontmatter_match:
        return None

    frontmatter = frontmatter_match.group(1)

    # Parse YAML-like front matter
    metadata = {}
    for line in frontmatter.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip().strip("\"'")

    return metadata


def main():
    if len(sys.argv) < 2:
        print("Usage: python prp_ingest.py <backlog_directory>")
        sys.exit(1)

    backlog_dir = Path(sys.argv[1])
    if not backlog_dir.exists():
        print(f"Backlog directory not found: {backlog_dir}")
        sys.exit(1)

    # Connect to Redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        r = redis.from_url(redis_url)
        r.ping()
    except Exception as e:
        print(f"Redis connection failed: {e}")
        sys.exit(1)

    queued_count = 0

    # Process all markdown files
    for prp_file in backlog_dir.glob("*.md"):
        try:
            metadata = parse_prp_file(prp_file)
            if not metadata:
                print(f"⚠️ No metadata found in {prp_file.name}")
                continue

            prp_id = metadata.get("id", prp_file.stem)
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
                "priority_stage": priority_stage,
                "status": "queued",
                "retry_count": "0",
                "added_at": datetime.utcnow().isoformat(),
                "source_file": str(prp_file),
                "content": prp_file.read_text(),
            }

            # Store in Redis
            r.hset(prp_key, mapping=prp_data)
            r.lpush(target_queue, prp_id)

            print(f"✅ Queued {prp_id} → {target_queue}")
            queued_count += 1

        except Exception as e:
            print(f"❌ Failed to process {prp_file.name}: {e}")

    print(f"\n📊 Ingest complete: {queued_count} PRPs queued")

    # Broadcast completion
    broadcast_msg = json.dumps(
        {
            "type": "system_broadcast",
            "message": f"Backlog ingest complete, {queued_count} PRPs queued.",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )
    r.lpush("orchestrator_queue", broadcast_msg)


if __name__ == "__main__":
    main()
