#!/usr/bin/env python3
"""
notification-suite.py

Utility to send launch communications (email, Slack) and watch Kubernetes pod readiness.

Subcommands:
  email  - send an email via SMTP
  slack  - send a Slack webhook message
  watch  - poll kubectl until targeted pods reach Running state or timeout

Examples:
  python3 notification-suite.py email -s "Subject" -b "Body" -t "a@b.com,c@d.com" --smtp-host localhost --smtp-port 25
  python3 notification-suite.py slack -w https://hooks.slack.com/services/XXX/YYY/ZZZ -m "Hello"
  python3 notification-suite.py watch -n mtls-demo -l "app=service-a,app=service-b" --timeout 600 --interval 10

Exit codes:
  0 success
  1 generic failure
  2 timeout (watch)
"""
import argparse
import socket
import sys
import time
import json
import ssl
from email.mime.text import MIMEText
from typing import List
import subprocess
import urllib.request


def send_email(subject: str, body: str, to: List[str], smtp_host: str, smtp_port: int, smtp_user: str = None, smtp_pass: str = None, use_tls: bool = False, sender: str = None):
    if not sender:
        # Derive a sender from hostname
        sender = f"noreply@{socket.gethostname()}"
    msg = MIMEText(body, _charset="utf-8")
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(to)
    try:
        if use_tls:
            context = ssl.create_default_context()
            with socket.create_connection((smtp_host, smtp_port), timeout=5) as raw_sock:
                with context.wrap_socket(raw_sock, server_hostname=smtp_host) as tls_sock:
                    import smtplib
                    s = smtplib.SMTP()
                    s.sock = tls_sock  # hack - direct assignment
                    s.file = tls_sock.makefile('rb')
                    s._host = smtp_host
                    s.connect(host=smtp_host, port=smtp_port)  # formally handshake
                    if smtp_user and smtp_pass:
                        s.login(smtp_user, smtp_pass)
                    s.send_message(msg)
                    s.quit()
        else:
            import smtplib
            with smtplib.SMTP(smtp_host, smtp_port, timeout=5) as s:
                if smtp_user and smtp_pass:
                    s.login(smtp_user, smtp_pass)
                s.send_message(msg)
        print(f"[email] Sent to {len(to)} recipients")
        return 0
    except Exception as e:
        print(f"[email][error] {e}")
        return 1


def send_slack(webhook: str, message: str):
    payload = json.dumps({"text": message}).encode("utf-8")
    req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
            print(f"[slack] Response: {resp.status} {data.decode('utf-8', 'ignore')}")
            return 0
    except Exception as e:
        print(f"[slack][error] {e}")
        return 1


def kubectl_get_pods(namespace: str, label_selector: str = None):
    base_cmd = ["kubectl", "get", "pods", "-n", namespace]
    if label_selector:
        base_cmd.extend(["-l", label_selector])
    base_cmd.extend(["-o", "json"])
    try:
        result = subprocess.run(base_cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print(f"[watch][kubectl-error] {result.stderr.strip()}")
            return None
        return json.loads(result.stdout)
    except Exception as e:
        print(f"[watch][exception] {e}")
        return None


def pods_all_running(pod_list_json) -> bool:
    items = pod_list_json.get('items', [])
    if not items:
        return False
    for item in items:
        phase = item.get('status', {}).get('phase')
        if phase != 'Running':
            return False
        # Optionally ensure all containers ready
        conditions = item.get('status', {}).get('conditions', [])
        ready_cond = next((c for c in conditions if c.get('type') == 'Ready'), None)
        if not ready_cond or ready_cond.get('status') != 'True':
            return False
    return True


def watch(namespace: str, labels: List[str], timeout: int, interval: int):
    start = time.time()
    label_selector = None
    if labels:
        # Combine multiple labels into OR by doing multiple queries if needed.
        # Simpler: join by comma = AND. We'll run each separately and require all sets running.
        while True:
            all_ok = True
            for lab in labels:
                pods_json = kubectl_get_pods(namespace, lab)
                if not pods_json or not pods_all_running(pods_json):
                    all_ok = False
                    break
            elapsed = int(time.time() - start)
            if all_ok:
                print(f"[watch] All targeted pods Running (elapsed {elapsed}s)")
                return 0
            if elapsed >= timeout:
                print(f"[watch][timeout] Pods not Running after {elapsed}s")
                return 2
            # Print brief status snapshot
            for lab in labels:
                pods_json = kubectl_get_pods(namespace, lab)
                if not pods_json:
                    print(f"[watch] label={lab} no data")
                    continue
                for item in pods_json.get('items', []):
                    name = item.get('metadata', {}).get('name')
                    phase = item.get('status', {}).get('phase')
                    container_states = []
                    for cs in item.get('status', {}).get('containerStatuses', []) or []:
                        state_desc = next(iter(cs.get('state', {}).keys()), 'unknown')
                        container_states.append(f"{cs.get('name')}={state_desc}")
                    print(f"[watch] {name} phase={phase} containers={';'.join(container_states) if container_states else 'NA'}")
            time.sleep(interval)


def parse_args():
    p = argparse.ArgumentParser(description="x0tta6bl4 notification suite")
    sub = p.add_subparsers(dest="command", required=True)

    e = sub.add_parser("email", help="Send email")
    e.add_argument('-s', '--subject', required=True)
    e.add_argument('-b', '--body', required=True)
    e.add_argument('-t', '--to', required=True, help="Comma-separated recipients")
    e.add_argument('--smtp-host', required=True)
    e.add_argument('--smtp-port', type=int, default=25)
    e.add_argument('--smtp-user')
    e.add_argument('--smtp-pass')
    e.add_argument('--use-tls', action='store_true')
    e.add_argument('--from', dest='sender')

    s = sub.add_parser("slack", help="Send Slack webhook message")
    s.add_argument('-w', '--webhook', required=True)
    s.add_argument('-m', '--message', required=True)

    w = sub.add_parser("watch", help="Watch pods until Running")
    w.add_argument('-n', '--namespace', required=True)
    w.add_argument('-l', '--labels', help="Comma-separated label selectors", required=True)
    w.add_argument('--timeout', type=int, default=600)
    w.add_argument('--interval', type=int, default=10)

    return p.parse_args()


def main():
    args = parse_args()
    if args.command == 'email':
        recipients = [r.strip() for r in args.to.split(',') if r.strip()]
        rc = send_email(args.subject, args.body, recipients, args.smtp_host, args.smtp_port, args.smtp_user, args.smtp_pass, args.use_tls, args.sender)
        sys.exit(rc)
    elif args.command == 'slack':
        rc = send_slack(args.webhook, args.message)
        sys.exit(rc)
    elif args.command == 'watch':
        labels = [l.strip() for l in args.labels.split(',') if l.strip()]
        rc = watch(args.namespace, labels, args.timeout, args.interval)
        sys.exit(rc)
    else:
        print("Unknown command")
        sys.exit(1)


if __name__ == '__main__':
    main()
