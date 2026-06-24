#!/usr/bin/env python3
"""Update dashboard metrics.json with new timestamp & optionally vote counts.
Usage:
  python3 scripts/update_dashboard.py --yes 120 --no 5 --outfile assets/data/metrics.json
"""
import argparse, json, datetime, pathlib

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--yes', type=int, default=None, help='YES votes')
    ap.add_argument('--no', type=int, default=None, help='NO votes')
    ap.add_argument('--outfile', default='assets/data/metrics.json')
    args = ap.parse_args()
    path = pathlib.Path(args.outfile)
    data = json.loads(path.read_text()) if path.exists() else {}
    data['generated_at'] = datetime.datetime.utcnow().isoformat() + 'Z'
    if 'vote_status' not in data:
        data['vote_status'] = { 'status': 'Voting Open', 'yes': 0, 'no': 0 }
    if args.yes is not None:
        data['vote_status']['yes'] = args.yes
    if args.no is not None:
        data['vote_status']['no'] = args.no
    path.write_text(json.dumps(data, indent=2))
    print('Updated', path)

if __name__ == '__main__':
    main()
