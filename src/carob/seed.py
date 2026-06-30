"""Reference data every environment needs (house accounts, rates, staff), plus demo customers for dev.

python -m carob.seed            # idempotent reference data
python -m carob.seed --demo     # and 24 demo customers with money in their wallets
"""

import argparse
import os
import random
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from carob.db import session_scope
from carob.ledger import Leg, house_account, post_entry
from carob.models import Account, Customer, FxRate, Staff
from carob.money import SUPPORTED
from carob.security import hash_password

HOUSE_KINDS = ("house_fees", "house_fx", "provider_clearing")

# Units of quote per one base, as published on Carob's rate sheet.
RATES: list[tuple[str, str, str, int]] = [
    ("USD", "LBP", "89500", 50),
    ("LBP", "USD", "0.0000111732", 50),
    ("USD", "EUR", "0.92", 40),
    ("EUR", "USD", "1.087", 40),
    ("EUR", "LBP", "97250", 60),
    ("LBP", "EUR", "0.0000102828", 60),
]

STAFF = [
    ("omar.aziz@carob.example", "Omar Aziz", "admin"),
    ("nour.haddad@carob.example", "Nour Haddad", "supervisor"),
    ("ziad.farah@carob.example", "Ziad Farah", "agent"),
    ("hala.mansour@carob.example", "Hala Mansour", "agent"),
]

FIRST = ["Rami", "Lea", "Karim", "Maya", "Jad", "Nadine", "Elie", "Rita", "Fadi", "Joelle", "Hadi", "Yasmine"]
LAST = ["Khoury", "Haddad", "Saab", "Nasr", "Aoun", "Gemayel", "Frem", "Sleiman", "Daher", "Rizk"]


def reference_data(session: Session) -> None:
    for currency in sorted(SUPPORTED):
        for kind in HOUSE_KINDS:
            exists = session.scalar(
                select(Account.id).where(
                    Account.customer_id.is_(None), Account.kind == kind, Account.currency == currency
                )
            )
            if not exists:
                session.add(Account(customer_id=None, kind=kind, currency=currency))
    if not session.scalar(select(FxRate.id).limit(1)):
        for base, quote, rate, spread in RATES:
            session.add(FxRate(base=base, quote=quote, rate=Decimal(rate), spread_bps=spread, source="seed"))
    password = os.environ.get("CAROB_SEED_STAFF_PASSWORD", "carob-dev-password")
    for email, name, role in STAFF:
        if not session.scalar(select(Staff.id).where(Staff.email == email)):
            session.add(Staff(email=email, name=name, role=role, password_hash=hash_password(password)))
    session.flush()


def demo_customers(session: Session, count: int = 24, seed: int = 7) -> None:
    rng = random.Random(seed)
    for i in range(count):
        email = f"demo{i:02d}@customers.carob.example"
        if session.scalar(select(Customer.id).where(Customer.email == email)):
            continue
        customer = Customer(
            full_name=f"{rng.choice(FIRST)} {rng.choice(LAST)}",
            email=email,
            phone=f"+961 70 {rng.randint(100, 999)} {rng.randint(100, 999)}",
            kyc_status="verified" if i % 6 else "pending",
            segment="vip" if i % 11 == 0 else "standard",
            locale="ar" if i % 3 == 0 else "en",
        )
        session.add(customer)
        session.flush()
        for currency, low, high in (("USD", 2_000, 400_000), ("LBP", 50_000_000, 9_000_000_000)):
            wallet = Account(customer_id=customer.id, kind="wallet", currency=currency)
            session.add(wallet)
            session.flush()
            amount = rng.randint(low, high)
            clearing = house_account(session, "provider_clearing", currency)
            post_entry(
                session,
                "topup",
                [Leg(clearing.id, -amount, currency), Leg(wallet.id, amount, currency)],
                memo="Seed top-up",
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="also create demo customers with balances")
    args = parser.parse_args()
    with session_scope() as session:
        reference_data(session)
        if args.demo:
            demo_customers(session)
    print("seeded" + (" with demo customers" if args.demo else ""))


if __name__ == "__main__":
    main()
