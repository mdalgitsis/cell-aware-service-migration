#!/usr/bin/env python3
"""Replay a synthetic 5G core event at the Decision Engine.

Lets you exercise the migration path without a live core and radio: point it
at a running engine and hand it the gNB the UE has supposedly moved to.

    ./replay_event.py --target http://localhost:8880/form \
        --supi 001010000000000 --gnb-id 21
"""

import argparse
import json

import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="http://localhost:8880/form")
    parser.add_argument("--supi", required=True, help="subscriber the event is about")
    parser.add_argument("--gnb-id", required=True, help="gNB the UE is now camped on")
    parser.add_argument("--event-type", default="http_api_update_success")
    args = parser.parse_args()

    # The core delivers session details as a JSON document inside a form field.
    data = {
        "event_type": args.event_type,
        "obj_class": "event_subscriber",
        "add_text": json.dumps({"supi": args.supi, "gnb_id": args.gnb_id}),
    }

    response = requests.post(args.target, data=data, timeout=30)
    print(f"Status Code: {response.status_code}")
    print(f"Response Text: {response.text}")


if __name__ == "__main__":
    main()
