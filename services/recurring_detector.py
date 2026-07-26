from collections import defaultdict
from datetime import datetime
from statistics import mean


DATE_FORMATS = [
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",

    "%d %b %Y",
    "%d %B %Y",

    "%b %d %Y",
    "%B %d %Y",

    "%b %d, %Y",
    "%B %d, %Y",

    "%d %b, %Y",
    "%d %B, %Y",
]
SUBSCRIPTION_KEYWORDS = [
    "netflix",
    "spotify",
    "amazon prime",
    "prime",
    "google one",
    "apple music",
    "youtube premium",
    "microsoft",
    "office 365",
    "adobe",
    "dropbox",
    "icloud",
    "hotstar",
    "disney",
    "zee5",
    "sonyliv",
    "jio fiber",
    "airtel xstream",
    "canva",
    "notion",
    "chatgpt",
    "gemini",
    "claude"
]


def parse_date(date_string):
    """
    Convert date string into datetime object.
    """
    if isinstance(date_string, datetime):
        return date_string

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue

    raise ValueError(f"Unsupported date format: {date_string}")


def average_gap(dates):
    """
    Average number of days between transactions.
    """
    if len(dates) < 2:
        return None

    gaps = []

    for i in range(1, len(dates)):
        gaps.append((dates[i] - dates[i - 1]).days)

    return mean(gaps)


def detect_frequency(avg_days):
    """
    Detect billing frequency.
    """

    if avg_days is None:
        return None

    if 25 <= avg_days <= 35:
        return "Monthly"

    if 6 <= avg_days <= 8:
        return "Weekly"

    if 360 <= avg_days <= 370:
        return "Yearly"

    return None


def detect_recurring(transactions):
    """
    Detect recurring subscriptions.

    Input:
    [
        {
            "date":"2026-01-05",
            "merchant":"Netflix",
            "amount":649
        }
    ]

    Returns:
    subscriptions,
    summary
    """

    merchant_groups = defaultdict(list)

    for tx in transactions:
        merchant = tx["merchant"].strip().title()

        merchant_groups[merchant].append({
            "date": parse_date(tx["date"]),
            "amount": abs(float(tx["amount"]))
        })

    subscriptions = []

    total_monthly_cost = 0

    total_yearly_cost = 0

    for merchant, items in merchant_groups.items():

        # Skip merchants that are not subscriptions
        merchant_lower = merchant.lower()

        if not any(keyword in merchant_lower for keyword in SUBSCRIPTION_KEYWORDS):
            continue

        if len(items) < 2:
            continue

        items.sort(key=lambda x: x["date"])

        dates = [x["date"] for x in items]

        amounts = [x["amount"] for x in items]

        avg_days = average_gap(dates)

        frequency = detect_frequency(avg_days)

        if frequency is None:
            continue

        current_price = amounts[-1]

        previous_price = amounts[-2] if len(amounts) >= 2 else amounts[-1]

        increase = current_price - previous_price

        price_changed = increase > 0

        change_percent = (
            round((increase / previous_price) * 100, 2)
            if previous_price > 0 else 0
        )

        # Detect potentially unused subscriptions

        today = datetime.today()

        last_payment_date = dates[-1]

        days_since_last_payment = (today - last_payment_date).days

        # Only monthly subscriptions are checked
        if frequency == "Monthly":
            unused = days_since_last_payment > 60
            unused_months = max(0, round(days_since_last_payment / 30))
        else:
            unused = False
            unused_months = 0

        subscription = {
            "merchant": merchant,
            "frequency": frequency,
            "amount": current_price,
            "previous_amount": previous_price,
            "change_percent": change_percent,

            "first_payment": dates[0].strftime("%Y-%m-%d"),
            "last_payment": dates[-1].strftime("%Y-%m-%d"),
            "payments": len(items),

            "price_changed": price_changed,
            "price_increase": round(increase, 2) if increase > 0 else 0,

            "unused": unused,
            "unused_months": unused_months,

            "status": "Active"
        }

        subscriptions.append(subscription)

        if frequency == "Monthly":
            total_monthly_cost += current_price
            total_yearly_cost += current_price * 12

        elif frequency == "Yearly":
            total_yearly_cost += current_price

        elif frequency == "Weekly":
            total_monthly_cost += current_price * 4
            total_yearly_cost += current_price * 52

    summary = {
        "total_subscriptions": len(subscriptions),
        "monthly_cost": round(total_monthly_cost, 2),
        "yearly_cost": round(total_yearly_cost, 2)
    }

    return subscriptions, summary