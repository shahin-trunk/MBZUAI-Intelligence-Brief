#!/usr/bin/env python3
"""CLI tool for Dead Letter Queue (DLQ) management.

Usage:
    cd backend
    python3.11 scripts/retry_dlq.py --list           # Show unresolved entries
    python3.11 scripts/retry_dlq.py --list --all      # Show all entries
    python3.11 scripts/retry_dlq.py --show <id>       # Full details of one entry
    python3.11 scripts/retry_dlq.py --retry <id>      # Retry one entry
    python3.11 scripts/retry_dlq.py --retry-all       # Retry all unresolved
    python3.11 scripts/retry_dlq.py --retry --item <item-id>  # Retry by item
    python3.11 scripts/retry_dlq.py --resolve <id>    # Dismiss without retry
    python3.11 scripts/retry_dlq.py --stats           # Aggregate counts
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend directory is on the Python path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

# Load environment variables from project root
PROJECT_ROOT = BACKEND_DIR.parent
root_env = PROJECT_ROOT / ".env"
if root_env.exists():
    load_dotenv(root_env, override=True)

frontend_env = PROJECT_ROOT / "frontend" / ".env.local"
if frontend_env.exists():
    load_dotenv(frontend_env, override=False)

from tasks.dlq import (
    push_to_dlq,
    get_dlq_entries,
    get_dlq_entry,
    retry_dlq_entry,
    resolve_dlq_entry,
    get_dlq_stats,
)


def format_entry(entry: dict) -> str:
    """Format a DLQ entry for display."""
    created = entry.get("created_at", "N/A")
    if isinstance(created, str):
        created = created[:19]
    task_name = entry.get("task_name", "?")
    item_id = entry.get("item_id", "?")
    lang = entry.get("lang", "?")
    error_type = entry.get("error_type", "?")
    error_msg = entry.get("error_message", "")[:80]
    resolved = "YES" if entry.get("resolved") else "NO"
    retry_count = entry.get("retry_count", 0)
    p_idx = entry.get("phrase_idx", "")
    s_idx = entry.get("script_idx", "")

    lines = [
        f"  ID:         {entry.get('id', '?')}",
        f"  Task:       {task_name}",
        f"  Item:       {item_id}",
        f"  Lang:       {lang}",
        f"  Phrase/Script: p{p_idx}/s{s_idx}",
        f"  Error:      {error_type}: {error_msg}",
        f"  Resolved:   {resolved}",
        f"  Retries:    {retry_count}",
        f"  Created:    {created}",
    ]
    if entry.get("traceback"):
        lines.append(f"  Traceback:  {entry['traceback'][:200]}")
    return "\n".join(lines)


def cmd_list(args):
    """List DLQ entries."""
    entries = get_dlq_entries(resolved=not args.all, limit=args.limit)
    if not entries:
        print(f"No {'un' if not args.all else ''}resolved entries found.")
        return

    print(f"\n{'='*80}")
    print(f"DLQ Entries ({'all' if args.all else 'unresolved'}): {len(entries)}")
    print(f"{'='*80}")
    for i, entry in enumerate(entries):
        if i > 0:
            print(f"\n{'-'*80}")
        print(format_entry(entry))
    print()


def cmd_show(args):
    """Show full details of one entry."""
    entry = get_dlq_entry(args.id)
    if not entry:
        print(f"Entry {args.id} not found.")
        return

    print(f"\n{'='*80}")
    print("DLQ Entry Details")
    print(f"{'='*80}")
    print(format_entry(entry))

    # Show full task_args
    task_args = entry.get("task_args")
    if task_args:
        print(f"\n  Task Args:")
        print(f"  {json.dumps(task_args, indent=4, default=str)}")
    print()


def cmd_retry(args):
    """Retry DLQ entries."""
    if args.item:
        # Retry all unresolved entries for a specific item
        entries = get_dlq_entries(resolved=False, limit=200)
        target_entries = [e for e in entries if e.get("item_id") == args.item]
        if not target_entries:
            print(f"No unresolved entries for item {args.item}")
            return
        print(f"\nRetrying {len(target_entries)} entries for item {args.item}...")
        retried = 0
        for entry in target_entries:
            task_id = retry_dlq_entry(entry["id"])
            if task_id:
                retried += 1
                print(f"  OK: {entry['id']} -> {task_id}")
            else:
                print(f"  FAIL: {entry['id']}")
        print(f"\nRetried {retried}/{len(target_entries)} entries.")

    elif args.all:
        # Retry all unresolved entries
        entries = get_dlq_entries(resolved=False, limit=200)
        if not entries:
            print("No unresolved entries to retry.")
            return
        print(f"\nRetrying {len(entries)} unresolved entries...")
        retried = 0
        for entry in entries:
            task_id = retry_dlq_entry(entry["id"])
            if task_id:
                retried += 1
                print(f"  OK: {entry['id']} -> {task_id}")
            else:
                print(f"  FAIL: {entry['id']}")
        print(f"\nRetried {retried}/{len(entries)} entries.")

    elif args.id:
        # Retry a single entry
        task_id = retry_dlq_entry(args.id)
        if task_id:
            print(f"\nRetried {args.id} -> task {task_id}")
        else:
            print(f"\nFailed to retry {args.id}")
    else:
        print("Error: Specify --id, --item, or --all")


def cmd_resolve(args):
    """Dismiss an entry without retrying."""
    ok = resolve_dlq_entry(args.id)
    if ok:
        print(f"\nResolved {args.id}")
    else:
        print(f"\nFailed to resolve {args.id}")


def cmd_stats(args):
    """Show aggregate counts."""
    stats = get_dlq_stats()
    print(f"\nDLQ Statistics:")
    print(f"  Total:      {stats['total']}")
    print(f"  Unresolved: {stats['unresolved']}")
    print(f"  Resolved:   {stats['resolved']}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Dead Letter Queue (DLQ) management tool."
    )
    parser.add_argument("--list", action="store_true", help="List unresolved DLQ entries")
    parser.add_argument("--all", action="store_true", help="Include resolved entries (with --list)")
    parser.add_argument("--limit", type=int, default=50, help="Max entries to list (default: 50)")
    parser.add_argument("--show", metavar="ID", help="Show full details of one entry")
    parser.add_argument("--retry", action="store_true", help="Retry DLQ entry/entries")
    parser.add_argument("--id", metavar="ID", help="Entry ID (with --retry or --resolve)")
    parser.add_argument("--item", metavar="ITEM_ID", help="Item ID (with --retry)")
    parser.add_argument("--resolve", metavar="ID", help="Dismiss entry without retrying")
    parser.add_argument("--stats", action="store_true", help="Show aggregate DLQ counts")

    args = parser.parse_args()

    if args.list:
        cmd_list(args)
    elif args.show:
        args.id = args.show
        cmd_show(args)
    elif args.retry:
        cmd_retry(args)
    elif args.resolve:
        args.id = args.resolve
        cmd_resolve(args)
    elif args.stats:
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
