"""Simulated customers, so dashboards move and incidents show up the way they would in production.

    uv run python scripts/traffic.py --base http://localhost:8200 --paystub http://localhost:8290

Each simulated customer signs up, is verified by a supervisor, tops up by
card through the Paystub sandbox, sends money, exchanges currency and now
and then writes to support. Stop with Ctrl-C; it prints what it did.
"""

import argparse
import os
import random
import time
import uuid
from collections import Counter

import httpx

MESSAGES = [
    "My top up from this morning is still pending",
    "I sent money to my sister and she did not receive it",
    "Why was I charged a fee for this transfer?",
    "What exchange rate do you use for dollars?",
    "I think my card was stolen",
    "حولت مصاري لأخي وما وصلت",
    "ليش في رسوم على التحويل؟",
    "بدي غير الرقم السري للبطاقة",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--paystub", default="http://localhost:8090")
    parser.add_argument("--customers", type=int, default=12)
    parser.add_argument("--rate", type=float, default=2.0, help="actions per second")
    parser.add_argument("--minutes", type=float, default=0, help="stop after this long (0: run until Ctrl-C)")
    parser.add_argument("--supervisor", default="nour.haddad@carob.example")
    parser.add_argument(
        "--password", default=os.environ.get("CAROB_SEED_STAFF_PASSWORD", "carob-dev-password")
    )
    parser.add_argument("--paystub-key", default=os.environ.get("PAYSTUB_API_KEY", "sk_test_carob_dev"))
    args = parser.parse_args()

    api = httpx.Client(base_url=args.base, timeout=10)
    paystub = httpx.Client(
        base_url=args.paystub, timeout=10, headers={"authorization": f"Bearer {args.paystub_key}"}
    )
    staff = {
        "authorization": "Bearer "
        + api.post("/staff/login", json={"email": args.supervisor, "password": args.password}).json()["token"]
    }
    rng = random.Random()
    run = uuid.uuid4().hex[:6]
    people = []
    for i in range(args.customers):
        body = api.post(
            "/v1/signup", json={"full_name": f"Traffic {run} {i}", "email": f"traffic-{run}-{i}@example.com"}
        ).json()
        api.post(f"/staff/customers/{body['customer']['id']}/kyc", json={"status": "verified"}, headers=staff)
        headers = {"authorization": f"Bearer {body['api_token']}"}
        wallets = {w["currency"]: w["id"] for w in api.get("/v1/wallets", headers=headers).json()}
        people.append({"email": body["customer"]["email"], "headers": headers, "wallets": wallets})

    done: Counter[str] = Counter()
    stop_at = time.monotonic() + args.minutes * 60 if args.minutes else float("inf")
    try:
        while time.monotonic() < stop_at:
            me = rng.choice(people)
            action = rng.choices(["topup", "transfer", "exchange", "support", "history"], [3, 4, 1, 1, 2])[0]
            try:
                if action == "topup":
                    r = api.post(
                        "/v1/topups",
                        json={"account_id": me["wallets"]["USD"], "amount_minor": rng.randint(1_000, 40_000)},
                        headers=me["headers"],
                    )
                    if r.status_code == 201:
                        intent = r.json()["checkout_url"].rsplit("/", 1)[1]
                        paystub.post(f"/v1/test/payment_intents/{intent}/succeed")
                elif action == "transfer":
                    to = rng.choice([p for p in people if p is not me])
                    r = api.post(
                        "/v1/transfers",
                        json={
                            "from_account_id": me["wallets"]["USD"],
                            "to_email": to["email"],
                            "amount_minor": rng.randint(100, 15_000),
                        },
                        headers=me["headers"],
                    )
                elif action == "exchange":
                    r = api.post(
                        "/v1/fx/conversions",
                        json={
                            "from_account_id": me["wallets"]["USD"],
                            "to_account_id": me["wallets"]["LBP"],
                            "from_minor": rng.randint(100, 5_000),
                        },
                        headers=me["headers"],
                    )
                elif action == "support":
                    r = api.post(
                        "/v1/support/messages", json={"body": rng.choice(MESSAGES)}, headers=me["headers"]
                    )
                else:
                    r = api.get(
                        f"/v1/wallets/{me['wallets']['USD']}/transactions?limit=20", headers=me["headers"]
                    )
                done[f"{action} {r.status_code}"] += 1
            except httpx.HTTPError as exc:
                done[f"{action} {type(exc).__name__}"] += 1
            time.sleep(1 / args.rate)
    except KeyboardInterrupt:
        pass
    for key, count in sorted(done.items()):
        print(f"{count:6d}  {key}")


if __name__ == "__main__":
    main()
