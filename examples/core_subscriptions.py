#!/usr/bin/env python3
"""Manage event subscriptions on the 5G core.

The Decision Engine registers its own subscription through the chart's
lifecycle hooks; this script does the same thing by hand, which is handy when
bringing a new testbed up or clearing a stale subscription left behind by a
crashed pod.

    export CORE_API_URL=https://core.example.internal:30443/api/event_subscriber
    export CORE_API_USER=... CORE_API_PASSWORD=...

    ./core_subscriptions.py list
    ./core_subscriptions.py subscribe --id 150 --callback http://de.example:30080/form
    ./core_subscriptions.py unsubscribe --id 150
"""

import argparse
import os
import sys

import requests


def api():
    url = os.getenv("CORE_API_URL")
    user = os.getenv("CORE_API_USER")
    password = os.getenv("CORE_API_PASSWORD")
    if not (url and user and password):
        sys.exit("Set CORE_API_URL, CORE_API_USER and CORE_API_PASSWORD first.")
    return url, (user, password)


def list_subscriptions(args):
    url, auth = api()
    response = requests.get(url, auth=auth, verify=args.verify, timeout=30)
    response.raise_for_status()
    for subscriber in response.json():
        print(f"{subscriber['id']}\t{subscriber.get('description', '')}")


def subscribe(args):
    url, auth = api()
    response = requests.post(
        url,
        auth=auth,
        data={
            "id": args.id,
            "description": args.description,
            "event_type_filter": args.event_type,
            "obj_class_filter": "*",
            "url": args.callback,
        },
        verify=args.verify,
        timeout=30,
    )
    response.raise_for_status()
    print(f"Subscription {args.id} created, delivering to {args.callback}")


def unsubscribe(args):
    url, auth = api()
    response = requests.delete(
        url, auth=auth, params={"id": args.id}, verify=args.verify, timeout=30
    )
    response.raise_for_status()
    print(f"Subscription {args.id} removed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--insecure",
        dest="verify",
        action="store_false",
        help="skip TLS verification (testbed cores often use self-signed certs)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list").set_defaults(func=list_subscriptions)

    p = sub.add_parser("subscribe")
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--callback", required=True, help="URL the core POSTs events to")
    p.add_argument("--event-type", default="http_api_update_success")
    p.add_argument("--description", default="cell-aware service migration")
    p.set_defaults(func=subscribe)

    p = sub.add_parser("unsubscribe")
    p.add_argument("--id", type=int, required=True)
    p.set_defaults(func=unsubscribe)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
