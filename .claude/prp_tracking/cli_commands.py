#!/usr/bin/env python3
"""
PRP Management CLI Commands
Provides command-line interface for managing PRP status transitions
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from typing import List, Optional

# Add current directory to path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Add parent directory to path to import redis_cli
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from github_integration import GitHubIntegration
from prp_state_manager import PRPEntry, PRPStateManager, PRPStatus
from redis_enhanced_state_manager import RedisEnhancedStateManager, get_redis_state_manager


class PRPCLICommands:
    """CLI interface for PRP management"""

    def __init__(self, use_redis: bool = True):
        if use_redis:
            self.prp_manager = get_redis_state_manager()
        else:
            self.prp_manager = PRPStateManager()
        self.github = GitHubIntegration()

    def status(self, prp_id: str = None) -> None:
        """Show status of one or all PRPs"""
        if prp_id:
            prp = self.prp_manager.get_prp(prp_id)
            if not prp:
                print(f"❌ PRP {prp_id} not found")
                return

            print(f"📋 **PRP {prp_id}**: {prp.title}")
            print(f"   Status: `{prp.status.value}`")
            print(f"   Validated: {prp.validated_at or 'Not yet'}")
            print(f"   Started: {prp.started_at or 'Not yet'}")
            print(f"   Completed: {prp.completed_at or 'Not yet'}")

            if prp.github_commit:
                print(f"   GitHub Commit: {prp.github_commit}")
            if prp.ci_run_url:
                print(f"   CI Run: {prp.ci_run_url}")
            if prp.notes:
                print(f"   Notes: {prp.notes}")

            # Show allowed transitions
            transitions = self._get_allowed_transitions(prp.status)
            if transitions:
                print(f"   Allowed transitions: {', '.join(transitions)}")
            else:
                print(f"   No further transitions available")
        else:
            # Show all PRPs
            stats = self.prp_manager.get_stats()
            print(f"📊 **PRP Statistics**")
            print(f"   Total: {stats['total_prps']}")
            print(f"   New: {stats['new']}")
            print(f"   Validated: {stats['validated']}")
            print(f"   In Progress: {stats['in_progress']}")
            print(f"   Complete: {stats['complete']}")
            print(f"   Completion Rate: {stats['completion_rate']:.1%}")
            print()

            # Show PRPs by status
            for status in PRPStatus:
                prps = self.prp_manager.list_prps(status)
                if prps:
                    print(f"**{status.value.upper()}** ({len(prps)} PRPs):")
                    for prp in prps:
                        print(f"   {prp.prp_id}: {prp.title}")
                    print()

    def list_prps(self, status_filter: str = None) -> None:
        """List PRPs with optional status filter"""
        status_enum = None
        if status_filter:
            try:
                status_enum = PRPStatus(status_filter)
            except ValueError:
                print(f"❌ Invalid status: {status_filter}")
                print(f"Valid statuses: {', '.join([s.value for s in PRPStatus])}")
                return

        prps = self.prp_manager.list_prps(status_enum)

        if not prps:
            filter_text = f" with status '{status_filter}'" if status_filter else ""
            print(f"No PRPs found{filter_text}")
            return

        print(f"📋 **PRPs{' (' + status_filter + ')' if status_filter else ''}**:")
        for prp in prps:
            status_icon = {
                PRPStatus.NEW: "🆕",
                PRPStatus.VALIDATED: "✅",
                PRPStatus.IN_PROGRESS: "🔄",
                PRPStatus.COMPLETE: "✅",
            }.get(prp.status, "❓")

            print(f"   {status_icon} {prp.prp_id}: {prp.title} ({prp.status.value})")

    def start(self, prp_id: str) -> None:
        """Start work on a PRP"""
        prp = self.prp_manager.get_prp(prp_id)
        if not prp:
            print(f"❌ PRP {prp_id} not found")
            return

        # Validate transition
        valid, message = self.prp_manager.validate_transition(prp_id, PRPStatus.IN_PROGRESS)
        if not valid:
            print(f"❌ Cannot start PRP {prp_id}: {message}")
            return

        # Multi-agent orchestration: Allow multiple PRPs in progress
        in_progress = self.prp_manager.get_in_progress_prps()
        if in_progress:
            print(f"ℹ️  Other PRPs currently in progress ({len(in_progress)} active):")
            for ip_prp in in_progress:
                print(f"   - {ip_prp.prp_id}: {ip_prp.title}")
            print(f"✅ Multi-agent orchestration: Starting {prp_id} concurrently")

        # Transition to in_progress
        success, transition_message = self.prp_manager.transition_prp(
            prp_id, PRPStatus.IN_PROGRESS, notes=f"Started by user at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        if success:
            print(f"🚀 {transition_message}")
            print(f"   Ready to begin implementation of: {prp.title}")
        else:
            print(f"❌ Failed to start PRP {prp_id}: {transition_message}")

    def complete(self, prp_id: str, commit_hash: str = None) -> None:
        """Complete a PRP"""
        prp = self.prp_manager.get_prp(prp_id)
        if not prp:
            print(f"❌ PRP {prp_id} not found")
            return

        # Get current commit hash if not provided
        if not commit_hash:
            try:
                result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
                if result.returncode == 0:
                    commit_hash = result.stdout.strip()
                else:
                    print("❌ Could not get current commit hash")
                    return
            except Exception as e:
                print(f"❌ Error getting commit hash: {e}")
                return

        # Validate GitHub CI status
        print(f"🔍 Validating completion requirements for PRP {prp_id}...")
        valid, message = self.github.validate_prp_completion(commit_hash)
        if not valid:
            print(f"❌ Completion validation failed: {message}")
            return

        # Transition to complete
        success, transition_message = self.prp_manager.transition_prp(
            prp_id,
            PRPStatus.COMPLETE,
            commit_hash=commit_hash,
            notes=f"Completed with validation at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        )

        if success:
            print(f"🎉 {transition_message}")
            print(f"   Commit: {commit_hash}")
            print(f"   All requirements validated successfully!")
        else:
            print(f"❌ Failed to complete PRP {prp_id}: {transition_message}")

    def validate(self, prp_id: str) -> None:
        """Validate PRP requirements (6-gate process)"""
        prp = self.prp_manager.get_prp(prp_id)
        if not prp:
            print(f"❌ PRP {prp_id} not found")
            return

        print(f"🔍 Running 6-gate validation for PRP {prp_id}...")

        # Run PRP completion validator
        validator_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "prompts", "prp_completion_validator.md"
        )

        if os.path.exists(validator_path):
            print("✅ PRP completion validator found")
            # TODO: Implement actual validation logic
            print("⚠️  6-gate validation not yet implemented")
        else:
            print("❌ PRP completion validator not found")
            return

        # For now, just mark as validated
        success, message = self.prp_manager.transition_prp(
            prp_id, PRPStatus.VALIDATED, notes=f"Validated by user at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")

    def next_prp(self) -> None:
        """Get next PRP ready for execution"""
        next_prp = self.prp_manager.get_next_prp()
        if not next_prp:
            print("📭 No PRPs ready for execution")

            # Show what's available
            validated = self.prp_manager.list_prps(PRPStatus.VALIDATED)
            in_progress = self.prp_manager.list_prps(PRPStatus.IN_PROGRESS)

            if in_progress:
                print("\\n🔄 PRPs currently in progress:")
                for prp in in_progress:
                    print(f"   - {prp.prp_id}: {prp.title}")

            if validated:
                print("\\n✅ PRPs ready to start:")
                for prp in validated:
                    print(f"   - {prp.prp_id}: {prp.title}")

            return

        print(f"📋 **Next PRP ready for execution:**")
        print(f"   {next_prp.prp_id}: {next_prp.title}")
        print(f"   Status: {next_prp.status.value}")
        print(f"   Validated: {next_prp.validated_at}")
        print(f"\\nTo start: `python .claude/prp_tracking/cli_commands.py start {next_prp.prp_id}`")

    def redis_status(self) -> None:
        """Show Redis connection and sync status"""
        if isinstance(self.prp_manager, RedisEnhancedStateManager):
            redis_status = self.prp_manager.get_redis_status()
            print("📊 **Redis Status**")
            print(f"   Connection: {'available' if redis_status['connected'] else 'unavailable'}")
            print(f"   Enabled: {redis_status['enabled']}")
            print(f"   Helper Available: {redis_status['helper_available']}")
            print(f"   URL: {redis_status['url']}")

            if redis_status["connected"] and redis_status["enabled"]:
                print("   ✅ Redis coordination fully operational")
            elif redis_status["enabled"] and not redis_status["connected"]:
                print("   ⚠️  Redis enabled but connection failed")
            else:
                print("   ⚠️  Redis functionality disabled - using YAML only")
        else:
            print("📊 **Redis Status**")
            print("   ⚠️  Using basic PRP manager - Redis features not available")

    def redis_sync(self) -> None:
        """Sync all PRPs from YAML to Redis"""
        if not isinstance(self.prp_manager, RedisEnhancedStateManager):
            print("❌ Redis-enhanced manager not available")
            return

        print("🔄 Syncing all PRPs from YAML to Redis...")
        results = self.prp_manager.sync_all_to_redis()

        if "error" in results:
            print(f"❌ Sync failed: {results['error']}")
            return

        print(f"✅ Sync completed successfully!")
        print(f"   Synced: {results['synced']} PRPs")
        if results["errors"] > 0:
            print(f"   Errors: {results['errors']} PRPs failed to sync")
        print(f"   PRPs: {', '.join(results['prps'])}")

    def redis_merge_status(self) -> None:
        """Show merge lock status"""
        if not isinstance(self.prp_manager, RedisEnhancedStateManager):
            print("❌ Redis-enhanced manager not available")
            return

        # This would need async support, for now show basic info
        print("🔒 **Merge Lock Status**")
        print("   ⚠️  Async merge lock status check not implemented in CLI")
        print("   Use Redis CLI: redis-cli get leadfactory:prp:merge:lock")

    def _get_allowed_transitions(self, current_status: PRPStatus) -> List[str]:
        """Get allowed transitions from current status"""
        transitions = {
            PRPStatus.NEW: ["validated"],
            PRPStatus.VALIDATED: ["in_progress"],
            PRPStatus.IN_PROGRESS: ["complete"],
            PRPStatus.COMPLETE: [],
        }
        return transitions.get(current_status, [])


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="PRP Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show PRP status")
    status_parser.add_argument("prp_id", nargs="?", help="PRP ID to show status for")

    # List command
    list_parser = subparsers.add_parser("list", help="List PRPs")
    list_parser.add_argument("--status", choices=[s.value for s in PRPStatus], help="Filter by status")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start work on a PRP")
    start_parser.add_argument("prp_id", help="PRP ID to start")

    # Complete command
    complete_parser = subparsers.add_parser("complete", help="Complete a PRP")
    complete_parser.add_argument("prp_id", help="PRP ID to complete")
    complete_parser.add_argument("--commit", help="Commit hash (uses current if not provided)")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate PRP (6-gate process)")
    validate_parser.add_argument("prp_id", help="PRP ID to validate")

    # Next command
    next_parser = subparsers.add_parser("next", help="Get next PRP ready for execution")

    # Redis commands
    redis_status_parser = subparsers.add_parser("redis-status", help="Show Redis connection status")
    redis_sync_parser = subparsers.add_parser("redis-sync", help="Sync all PRPs to Redis")
    redis_merge_parser = subparsers.add_parser("redis-merge-status", help="Show merge lock status")

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Execute command
    cli = PRPCLICommands()

    try:
        if args.command == "status":
            cli.status(args.prp_id)
        elif args.command == "list":
            cli.list_prps(args.status)
        elif args.command == "start":
            cli.start(args.prp_id)
        elif args.command == "complete":
            cli.complete(args.prp_id, args.commit)
        elif args.command == "validate":
            cli.validate(args.prp_id)
        elif args.command == "next":
            cli.next_prp()
        elif args.command == "redis-status":
            cli.redis_status()
        elif args.command == "redis-sync":
            cli.redis_sync()
        elif args.command == "redis-merge-status":
            cli.redis_merge_status()
        else:
            print(f"❌ Unknown command: {args.command}")

    except Exception as e:
        print(f"❌ Error executing command: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
