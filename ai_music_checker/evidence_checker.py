"""Evidence URL checker — verify evidence URLs are still valid."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ai_music_checker.lib.http import fetch_url


@dataclass
class EvidenceStatus:
    url: str
    status: str  # "valid" | "broken" | "outdated"
    last_checked: str  # YYYY-MM-DD
    note: str


def check_evidence_url(url: str, timeout: int = 10) -> EvidenceStatus:
    """Check if an evidence URL is still accessible.
    
    Returns EvidenceStatus with status "valid", "broken", or "outdated".
    """
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    
    try:
        content = fetch_url(url, timeout=timeout)
        if content is None:
            return EvidenceStatus(
                url=url,
                status="broken",
                last_checked=today,
                note="URL returned no content"
            )
        
        # Check for common "not found" patterns
        content_lower = content.lower() if isinstance(content, str) else ""
        not_found_patterns = [
            "404", "not found", "page not found", "does not exist",
            "removed", "deleted", "no longer available", "expired",
        ]
        
        for pattern in not_found_patterns:
            if pattern in content_lower[:500]:  # Check first 500 chars
                return EvidenceStatus(
                    url=url,
                    status="broken",
                    last_checked=today,
                    note=f"Page contains '{pattern}' indicator"
                )
        
        return EvidenceStatus(
            url=url,
            status="valid",
            last_checked=today,
            note="URL accessible"
        )
        
    except TimeoutError:
        return EvidenceStatus(
            url=url,
            status="broken",
            last_checked=today,
            note="Timeout after 10s"
        )
    except (OSError, ValueError) as e:
        return EvidenceStatus(
            url=url,
            status="broken",
            last_checked=today,
            note=f"Error: {str(e)[:50]}"
        )


def check_entry_evidence(entry: dict[str, Any]) -> list[EvidenceStatus]:
    """Check all evidence URLs for a single entry.
    
    Returns list of EvidenceStatus for each evidence item.
    """
    results = []
    for ev in entry.get("evidence", []):
        url = ev.get("url", "")
        if url:
            status = check_evidence_url(url)
            results.append(status)
    return results


def check_database_evidence(db: dict[str, Any], 
                            max_entries: int | None = None) -> dict[str, list[EvidenceStatus]]:
    """Check evidence URLs for all entries in the database.
    
    Args:
        db: Database dict with entries
        max_entries: Limit number of entries to check (for testing)
    
    Returns:
        Dict mapping entry IDs to their evidence statuses
    """
    results = {}
    entries = db.get("entries", [])
    
    if max_entries:
        entries = entries[:max_entries]
    
    for entry in entries:
        entry_id = entry.get("id", "unknown")
        results[entry_id] = check_entry_evidence(entry)
    
    return results


def generate_evidence_report(results: dict[str, list[EvidenceStatus]]) -> str:
    """Generate a human-readable report of evidence check results."""
    lines = ["Evidence URL Check Report", "=" * 50, ""]
    
    total = 0
    valid = 0
    broken = 0
    
    for entry_id, statuses in results.items():
        lines.append(f"Entry: {entry_id}")
        for status in statuses:
            total += 1
            icon = "✓" if status.status == "valid" else "✗"
            lines.append(f"  {icon} [{status.status}] {status.url}")
            lines.append(f"    Last checked: {status.last_checked}")
            lines.append(f"    Note: {status.note}")
            
            if status.status == "valid":
                valid += 1
            else:
                broken += 1
        lines.append("")
    
    lines.append("=" * 50)
    lines.append(f"Summary: {valid}/{total} valid, {broken} broken")
    
    return "\n".join(lines)


def update_evidence_in_entry(entry: dict[str, Any], 
                             statuses: list[EvidenceStatus]) -> dict[str, Any]:
    """Update evidence items with new status and last_checked dates.
    
    Returns updated entry dict.
    """
    updated_entry = entry.copy()
    updated_evidence = []
    
    for ev, status in zip(updated_entry.get("evidence", []), statuses):
        updated_ev = ev.copy()
        updated_ev["status"] = status.status
        updated_ev["last_checked"] = status.last_checked
        updated_evidence.append(updated_ev)
    
    updated_entry["evidence"] = updated_evidence
    updated_entry["verified"] = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    
    return updated_entry

def update_database_evidence(
    db: dict[str, Any],
    results: dict[str, list[EvidenceStatus]],
    retention_days: int = 30,
) -> dict[str, Any]:
    """Update database with evidence check results and remove expired broken evidence.
    
    Args:
        db: Database dict with entries
        results: Evidence check results from check_database_evidence
        retention_days: Days to keep broken evidence before removal (default: 30)
    
    Returns:
        Updated database dict
    """
    from datetime import timedelta
    
    updated_db = db.copy()
    updated_entries = []
    
    today = datetime.now(tz=timezone.utc)
    cutoff_date = (today - timedelta(days=retention_days)).strftime("%Y-%m-%d")
    
    for entry in updated_db.get("entries", []):
        entry_id = entry.get("id", "unknown")
        
        if entry_id in results:
            # Update evidence with new statuses
            updated_entry = update_evidence_in_entry(entry, results[entry_id])
            
            # Filter out broken evidence older than retention period
            if retention_days > 0:
                evidence = updated_entry.get("evidence", [])
                filtered_evidence = []
                
                for ev in evidence:
                    status = ev.get("status", "valid")
                    last_checked = ev.get("last_checked", "")
                    
                    # Keep if not broken, or if broken but within retention period
                    if status != "broken" or (last_checked and last_checked >= cutoff_date):
                        filtered_evidence.append(ev)
                    else:
                        print(f"  Removing broken evidence from {entry_id}: {ev.get('url', 'unknown')}")
                
                updated_entry["evidence"] = filtered_evidence
            
            updated_entries.append(updated_entry)
        else:
            updated_entries.append(entry)
    
    updated_db["entries"] = updated_entries
    updated_db["updated"] = today.strftime("%Y-%m-%d")
    
    return updated_db
