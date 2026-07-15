"""
Verification that Lute is running correctly.

Used in github actions to verify running app.

Usage:

python -m utils.verify [port]
"""

import sys
import json
import time
import requests


def verify(port):
    """
    Check the /info page, retrying while the app starts.
    """

    url = f"http://localhost:{port}/info"
    max_wait = 60
    interval = 2
    elapsed = 0

    while True:
        try:
            resp = requests.get(url, timeout=5)
            c = resp.status_code

            if c != 200:
                raise RuntimeError(f"Code {c} for url {url}")

            print("Lute is running:")
            print(json.dumps(resp.json(), indent=2))
            return
        except requests.exceptions.ConnectionError:
            if elapsed >= max_wait:
                raise RuntimeError(
                    f"Server at {url} did not respond within {max_wait} seconds"
                ) from None
            time.sleep(interval)
            elapsed += interval


if __name__ == "__main__":
    useport = None
    if len(sys.argv) == 2:
        useport = sys.argv[1]
    else:
        print("Must supply port as argument")
        sys.exit(1)
    verify(useport)
