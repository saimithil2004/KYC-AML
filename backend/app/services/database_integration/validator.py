import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

# Valid ISO currency list
VALID_CURRENCIES = {"GBP", "USD", "EUR", "CHF", "AUD", "CAD", "JPY", "SGD", "AED"}


class IngestionValidator:
    @staticmethod
    def validate_customer(
        record: Dict[str, Any], existing_emails: List[str], existing_phones: List[str]
    ) -> Tuple[bool, List[str]]:
        errors = []

        # Missing fields check
        required = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "dob",
            "nationality",
            "country",
        ]
        for field in required:
            if not record.get(field):
                errors.append(f"Missing required customer field: {field}")

        # Validate duplicate checks
        email = record.get("email")
        if email and email.strip().lower() in existing_emails:
            errors.append(f"Duplicate customer email detected: {email}")

        phone = record.get("phone")
        if phone and phone.strip() in existing_phones:
            errors.append(f"Duplicate customer phone detected: {phone}")

        # Validate DOB format or bounds
        dob = record.get("dob")
        if dob:
            # check basic validation rules
            pass

        return len(errors) == 0, errors

    @staticmethod
    def validate_account(
        record: Dict[str, Any], existing_account_numbers: List[str]
    ) -> Tuple[bool, List[str]]:
        errors = []

        required = [
            "account_number",
            "sort_code",
            "currency",
            "balance",
            "customer_ext_id",
        ]
        for field in required:
            if record.get(field) is None:
                errors.append(f"Missing required account field: {field}")

        acc_num = record.get("account_number")
        if acc_num and acc_num.strip() in existing_account_numbers:
            errors.append(f"Duplicate account number detected: {acc_num}")

        curr = record.get("currency")
        if curr and curr.strip().upper() not in VALID_CURRENCIES:
            errors.append(f"Invalid account currency: {curr}")

        return len(errors) == 0, errors

    @staticmethod
    def validate_transaction(
        record: Dict[str, Any], active_account_numbers: List[str]
    ) -> Tuple[bool, List[str]]:
        errors = []

        required = [
            "account_number",
            "sort_code",
            "receiver_name",
            "receiver_account_number",
            "receiver_sort_code",
            "receiver_country",
            "amount",
            "currency",
        ]
        for field in required:
            if record.get(field) is None:
                errors.append(f"Missing required transaction field: {field}")

        # Orphan check: sender account number must exist
        sender_acc = record.get("account_number")
        if sender_acc and sender_acc.strip() not in active_account_numbers:
            errors.append(
                f"Orphan transaction: sender account number {sender_acc} not found in database."
            )

        curr = record.get("currency")
        if curr and curr.strip().upper() not in VALID_CURRENCIES:
            errors.append(f"Invalid transaction currency: {curr}")

        amount = record.get("amount")
        if amount is not None:
            try:
                if float(amount) <= 0:
                    errors.append(f"Transaction amount must be positive: {amount}")
            except ValueError:
                errors.append(f"Invalid amount value: {amount}")

        return len(errors) == 0, errors

    @staticmethod
    def validate_company(
        record: Dict[str, Any], existing_reg_numbers: List[str]
    ) -> Tuple[bool, List[str]]:
        errors = []

        required = [
            "company_name",
            "registration_number",
            "registered_address",
            "country_of_incorporation",
            "customer_ext_id",
        ]
        for field in required:
            if not record.get(field):
                errors.append(f"Missing required company field: {field}")

        reg_num = record.get("registration_number")
        if reg_num and reg_num.strip() in existing_reg_numbers:
            errors.append(f"Duplicate company registration number: {reg_num}")

        return len(errors) == 0, errors
