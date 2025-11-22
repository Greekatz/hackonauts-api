#!/usr/bin/env python
"""
CLI Trigger Tool
A small script to manually trigger the agent and interact with the backend.
"""
import argparse
import json
import sys
from datetime import datetime
import httpx

DEFAULT_URL = "http://localhost:8000"


def make_request(method: str, endpoint: str, base_url: str, api_key: str = None, data: dict = None):
    """Make an HTTP request to the backend."""
    url = f"{base_url}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    try:
        with httpx.Client(timeout=60.0) as client:
            if method == "GET":
                response = client.get(url, headers=headers)
            elif method == "POST":
                response = client.post(url, headers=headers, json=data or {})
            else:
                raise ValueError(f"Unsupported method: {method}")

            return response.json(), response.status_code
    except httpx.ConnectError:
        return {"error": f"Could not connect to {base_url}"}, 0
    except Exception as e:
        return {"error": str(e)}, 0


def print_json(data: dict):
    """Pretty print JSON data."""
    print(json.dumps(data, indent=2, default=str))


def cmd_health(args):
    """Check backend health."""
    result, status = make_request("GET", "/health", args.url, args.api_key)
    print_json(result)
    return 0 if status == 200 else 1


def cmd_status(args):
    """Get system status."""
    result, status = make_request("GET", "/status", args.url, args.api_key)
    print_json(result)
    return 0 if status == 200 else 1


def cmd_generate_incident(args):
    """Generate a mock incident."""
    endpoint = f"/mock/generate-incident?incident_type={args.type}" if args.type else "/mock/generate-incident"
    result, status = make_request("POST", endpoint, args.url, args.api_key)

    if status == 200:
        print(f"[OK] Incident created: {result.get('incident_id')}")
        print(f"     Title: {result.get('title')}")
        print(f"     Severity: {result.get('severity')}")
        print(f"     Logs: {result.get('log_count')}")
        print(f"     Metrics: {result.get('metric_count')}")
    else:
        print("[ERROR] Failed to create incident")
        print_json(result)

    return 0 if status == 200 else 1


def cmd_list_incidents(args):
    """List incidents."""
    endpoint = f"/incidents?limit={args.limit}"
    if args.status:
        endpoint += f"&status={args.status}"

    result, status = make_request("GET", endpoint, args.url, args.api_key)

    if status == 200:
        if not result:
            print("No incidents found")
        else:
            print(f"Found {len(result)} incidents:\n")
            for inc in result:
                print(f"  [{inc.get('severity', 'unknown').upper():8}] {inc.get('id', 'N/A')[:8]} - {inc.get('title', 'Untitled')}")
                print(f"           Status: {inc.get('status')} | Agent Runs: {inc.get('agent_runs', 0)} | Duration: {inc.get('duration_minutes', 0):.1f}min")
                print()
    else:
        print_json(result)

    return 0 if status == 200 else 1


def cmd_get_incident(args):
    """Get incident details."""
    result, status = make_request("GET", f"/incidents/{args.incident_id}", args.url, args.api_key)
    print_json(result)
    return 0 if status == 200 else 1


def cmd_get_summary(args):
    """Get incident summary."""
    result, status = make_request("GET", f"/incidents/{args.incident_id}/summary", args.url, args.api_key)
    print_json(result)
    return 0 if status == 200 else 1


def cmd_trigger_agent(args):
    """Trigger the agent for an incident."""
    result, status = make_request("POST", f"/agent/trigger?incident_id={args.incident_id}", args.url, args.api_key)

    if status == 200:
        print(f"[OK] Agent triggered for incident {args.incident_id}")
    else:
        print("[ERROR] Failed to trigger agent")
        print_json(result)

    return 0 if status == 200 else 1


def cmd_force_rca(args):
    """Force an RCA with description."""
    data = {"description": args.description}
    result, status = make_request("POST", "/agent/force-rca", args.url, args.api_key, data)

    if status == 200:
        print(f"[OK] RCA completed for incident {result.get('incident_id')}")
        print(f"\nSummary: {result.get('summary')}")
        if result.get('rca'):
            print(f"\nRoot Cause: {result['rca'].get('root_cause')}")
        if result.get('recommended_actions'):
            print(f"\nRecommended Actions:")
            for action in result['recommended_actions']:
                print(f"   - {action.get('description')}")
    else:
        print_json(result)

    return 0 if status == 200 else 1


def cmd_check_stability(args):
    """Check system stability."""
    result, status = make_request("GET", "/stability/check", args.url, args.api_key)

    if status == 200:
        stable = result.get('is_stable', False)
        status_str = "[STABLE]" if stable else "[UNSTABLE]"
        print(f"{status_str} System Stability")
        print(f"   Metrics OK: {result.get('metrics_ok')}")
        print(f"   Logs OK: {result.get('logs_ok')}")
        print(f"   Details: {result.get('details')}")
        print(f"   Should Re-run Agent: {result.get('should_rerun_agent')}")
    else:
        print_json(result)

    return 0 if status == 200 else 1


def cmd_check_anomaly(args):
    """Check for anomalies."""
    result, status = make_request("GET", "/anomaly/status", args.url, args.api_key)

    if status == 200:
        detected = result.get('anomaly_detected', False)
        status_str = "[ALERT]" if detected else "[OK]"
        print(f"{status_str} Anomaly Detection: {'DETECTED' if detected else 'None'}")
        if detected:
            print(f"   Type: {result.get('anomaly_type')}")
            print(f"   Severity: {result.get('severity')}")
            print(f"   Description: {result.get('description')}")
            print(f"   Confidence: {result.get('confidence', 0):.2f}")
    else:
        print_json(result)

    return 0 if status == 200 else 1


def cmd_autoheal(args):
    """Execute an auto-heal action."""
    action_map = {
        "restart": "/autoheal/restart",
        "scale": "/autoheal/scale",
        "flush": "/autoheal/flush",
        "clear-queue": "/autoheal/clear-queue",
        "reroute": "/autoheal/reroute",
        "rollback": "/autoheal/rollback"
    }

    endpoint = action_map.get(args.action)
    if not endpoint:
        print(f"[ERROR] Unknown action: {args.action}")
        print(f"        Available: {', '.join(action_map.keys())}")
        return 1

    data = {"service": args.service}
    if args.params:
        try:
            data["parameters"] = json.loads(args.params)
        except json.JSONDecodeError:
            print("[ERROR] Invalid JSON in --params")
            return 1

    result, status = make_request("POST", endpoint, args.url, args.api_key, data)

    if status == 200 and result.get('success'):
        print(f"[OK] Auto-heal action '{args.action}' executed successfully")
        print(f"     Service: {args.service}")
        print(f"     Message: {result.get('message')}")
    else:
        print("[ERROR] Auto-heal action failed")
        print_json(result)

    return 0 if status == 200 and result.get('success') else 1


def cmd_notify(args):
    """Send notifications for an incident."""
    channels = args.channels.split(",") if args.channels else None
    endpoint = f"/notify/{args.incident_id}"
    data = {"channels": channels} if channels else None

    result, status = make_request("POST", endpoint, args.url, args.api_key, data)

    if status == 200:
        print(f"Notification results for incident {args.incident_id}:")
        for channel, success in result.items():
            status_str = "[OK]" if success else "[FAILED]"
            print(f"   {status_str} {channel}")
    else:
        print_json(result)

    return 0 if status == 200 else 1


def cmd_resolve(args):
    """Resolve an incident."""
    result, status = make_request(
        "POST",
        f"/incidents/{args.incident_id}/resolve?summary={args.summary}",
        args.url,
        args.api_key
    )

    if status == 200:
        print(f"[OK] Incident {args.incident_id} resolved")
    else:
        print_json(result)

    return 0 if status == 200 else 1


def cmd_generate_logs(args):
    """Generate mock logs."""
    endpoint = f"/mock/generate-logs?count={args.count}&error_rate={args.error_rate}"
    if args.service:
        endpoint += f"&service={args.service}"

    result, status = make_request("POST", endpoint, args.url, args.api_key)

    if status == 200:
        print(f"[OK] Generated {result.get('generated')} logs ({result.get('error_count')} errors)")
    else:
        print_json(result)

    return 0 if status == 200 else 1


def cmd_generate_metrics(args):
    """Generate mock metrics."""
    endpoint = f"/mock/generate-metrics?count={args.count}&stress_level={args.stress}"
    result, status = make_request("POST", endpoint, args.url, args.api_key)

    if status == 200:
        print(f"[OK] Generated {result.get('generated')} metric snapshots (stress: {result.get('stress_level')})")
    else:
        print_json(result)

    return 0 if status == 200 else 1


def main():
    parser = argparse.ArgumentParser(
        description="CLI tool for Incident Response Backend",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Backend URL (default: {DEFAULT_URL})")
    parser.add_argument("--api-key", help="API key for authentication")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Health
    subparsers.add_parser("health", help="Check backend health")

    # Status
    subparsers.add_parser("status", help="Get system status")

    # Generate incident
    gen_inc = subparsers.add_parser("generate-incident", help="Generate a mock incident")
    gen_inc.add_argument("--type", choices=["database", "memory", "latency", "service", "disk", "random"],
                         help="Incident type")

    # List incidents
    list_inc = subparsers.add_parser("list-incidents", help="List incidents")
    list_inc.add_argument("--status", choices=["open", "investigating", "mitigating", "resolved", "closed"],
                          help="Filter by status")
    list_inc.add_argument("--limit", type=int, default=10, help="Max incidents to return")

    # Get incident
    get_inc = subparsers.add_parser("get-incident", help="Get incident details")
    get_inc.add_argument("incident_id", help="Incident ID")

    # Get summary
    get_sum = subparsers.add_parser("get-summary", help="Get incident summary")
    get_sum.add_argument("incident_id", help="Incident ID")

    # Trigger agent
    trigger = subparsers.add_parser("trigger-agent", help="Trigger agent for incident")
    trigger.add_argument("incident_id", help="Incident ID")

    # Force RCA
    force_rca = subparsers.add_parser("force-rca", help="Force an RCA run")
    force_rca.add_argument("description", help="Description of the issue")

    # Stability check
    subparsers.add_parser("check-stability", help="Check system stability")

    # Anomaly check
    subparsers.add_parser("check-anomaly", help="Check for anomalies")

    # Auto-heal
    autoheal = subparsers.add_parser("autoheal", help="Execute auto-heal action")
    autoheal.add_argument("action", choices=["restart", "scale", "flush", "clear-queue", "reroute", "rollback"],
                          help="Action to execute")
    autoheal.add_argument("service", help="Service name")
    autoheal.add_argument("--params", help="JSON parameters")

    # Notify
    notify = subparsers.add_parser("notify", help="Send notifications for incident")
    notify.add_argument("incident_id", help="Incident ID")
    notify.add_argument("--channels", help="Comma-separated channels (slack,discord,email,jira,servicenow)")

    # Resolve
    resolve = subparsers.add_parser("resolve", help="Resolve an incident")
    resolve.add_argument("incident_id", help="Incident ID")
    resolve.add_argument("summary", help="Resolution summary")

    # Generate logs
    gen_logs = subparsers.add_parser("generate-logs", help="Generate mock logs")
    gen_logs.add_argument("--count", type=int, default=50, help="Number of logs")
    gen_logs.add_argument("--error-rate", type=float, default=0.2, help="Error rate (0.0-1.0)")
    gen_logs.add_argument("--service", help="Service name")

    # Generate metrics
    gen_metrics = subparsers.add_parser("generate-metrics", help="Generate mock metrics")
    gen_metrics.add_argument("--count", type=int, default=20, help="Number of snapshots")
    gen_metrics.add_argument("--stress", type=float, default=0.0, help="Stress level (0.0-1.0)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Command dispatch
    commands = {
        "health": cmd_health,
        "status": cmd_status,
        "generate-incident": cmd_generate_incident,
        "list-incidents": cmd_list_incidents,
        "get-incident": cmd_get_incident,
        "get-summary": cmd_get_summary,
        "trigger-agent": cmd_trigger_agent,
        "force-rca": cmd_force_rca,
        "check-stability": cmd_check_stability,
        "check-anomaly": cmd_check_anomaly,
        "autoheal": cmd_autoheal,
        "notify": cmd_notify,
        "resolve": cmd_resolve,
        "generate-logs": cmd_generate_logs,
        "generate-metrics": cmd_generate_metrics,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
