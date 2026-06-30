"""The 77 BANKING77 intents and the support queue each one belongs to."""

QUEUE_INTENTS: dict[str, tuple[str, ...]] = {
    "security": (
        "card_payment_not_recognised",
        "cash_withdrawal_not_recognised",
        "compromised_card",
        "direct_debit_payment_not_recognised",
        "lost_or_stolen_card",
        "lost_or_stolen_phone",
    ),
    "cards": (
        "activate_my_card",
        "apple_pay_or_google_pay",
        "atm_support",
        "card_about_to_expire",
        "card_acceptance",
        "card_arrival",
        "card_delivery_estimate",
        "card_linking",
        "card_not_working",
        "card_swallowed",
        "change_pin",
        "contactless_not_working",
        "declined_card_payment",
        "declined_cash_withdrawal",
        "disposable_card_limits",
        "get_disposable_virtual_card",
        "get_physical_card",
        "getting_spare_card",
        "getting_virtual_card",
        "order_physical_card",
        "pending_card_payment",
        "pending_cash_withdrawal",
        "pin_blocked",
        "Refund_not_showing_up",
        "request_refund",
        "reverted_card_payment?",
        "supported_cards_and_currencies",
        "virtual_card_not_working",
        "visa_or_mastercard",
        "wrong_amount_of_cash_received",
    ),
    "topups": (
        "automatic_top_up",
        "balance_not_updated_after_cheque_or_cash_deposit",
        "pending_top_up",
        "top_up_by_cash_or_cheque",
        "top_up_failed",
        "top_up_limits",
        "top_up_reverted",
        "topping_up_by_card",
        "verify_top_up",
    ),
    "transfers": (
        "balance_not_updated_after_bank_transfer",
        "beneficiary_not_allowed",
        "cancel_transfer",
        "declined_transfer",
        "failed_transfer",
        "pending_transfer",
        "receiving_money",
        "transfer_into_account",
        "transfer_not_received_by_recipient",
        "transfer_timing",
    ),
    "exchange": (
        "card_payment_wrong_exchange_rate",
        "exchange_rate",
        "exchange_via_app",
        "fiat_currency_support",
        "wrong_exchange_rate_for_cash_withdrawal",
    ),
    "fees": (
        "card_payment_fee_charged",
        "cash_withdrawal_charge",
        "exchange_charge",
        "extra_charge_on_statement",
        "top_up_by_bank_transfer_charge",
        "top_up_by_card_charge",
        "transaction_charged_twice",
        "transfer_fee_charged",
    ),
    "verification": (
        "age_limit",
        "unable_to_verify_identity",
        "verify_my_identity",
        "verify_source_of_funds",
        "why_verify_identity",
    ),
    "account": ("country_support", "edit_personal_details", "passcode_forgotten", "terminate_account"),
}

INTENT_TO_QUEUE: dict[str, str] = {
    intent: queue for queue, intents in QUEUE_INTENTS.items() for intent in intents
}
INTENTS = tuple(sorted(INTENT_TO_QUEUE))
_CANONICAL = {intent.lower().rstrip("?"): intent for intent in INTENTS}


def canonical_intent(label: str) -> str:
    """BANKING77's spelling of an intent from any of its variants ("card arrival" -> "card_arrival")."""
    key = label.strip().lower().replace(" ", "_").rstrip("?")
    try:
        return _CANONICAL[key]
    except KeyError:
        raise ValueError(f"unknown intent {label!r}") from None
