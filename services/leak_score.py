from collections import defaultdict
from datetime import datetime


class LeakScoreEngine:
    """
    LeakGuard AI Leak Score Engine

    Input:
        subscriptions (from recurring_detector.py)
        summary (from recurring_detector.py)

    Output:
        Leak Score
        Risk Level
        Monthly Savings
        Yearly Savings
        Dashboard Data
    """

    CATEGORY_MAP = {
        "Netflix": "Entertainment",
        "Prime Video": "Entertainment",
        "Amazon Prime": "Entertainment",
        "Disney+": "Entertainment",
        "Disney+ Hotstar": "Entertainment",
        "Hotstar": "Entertainment",
        "Sony Liv": "Entertainment",
        "Spotify": "Music",
        "Apple Music": "Music",
        "YouTube Premium": "Music",
        "Google One": "Cloud Storage",
        "Dropbox": "Cloud Storage",
        "iCloud": "Cloud Storage",
        "Microsoft 365": "Productivity",
        "Notion": "Productivity",
        "Canva": "Productivity",
        "Adobe": "Design",
        "Figma": "Design",
        "Swiggy One": "Food",
        "Zomato Gold": "Food",
        "Cult Fit": "Fitness",
        "HealthifyMe": "Fitness",
        "Audible": "Education",
        "Coursera": "Education",
        "Udemy": "Education"
    }

    def __init__(self, subscriptions, summary):
        self.subscriptions = subscriptions
        self.summary = summary

    # -------------------------------------------------------
    # CATEGORY DETECTION
    # -------------------------------------------------------

    def get_category(self, merchant):
        """
        Return category for merchant.
        """
        merchant = merchant.strip()

        for key, value in self.CATEGORY_MAP.items():
            if key.lower() in merchant.lower():
                return value

        return "Others"

    # -------------------------------------------------------
    # PRICE INCREASE COUNT
    # -------------------------------------------------------

    def price_increase_count(self):
        return sum(
            1
            for sub in self.subscriptions
            if sub.get("price_changed")
        )

    # -------------------------------------------------------
    # UNUSED SUBSCRIPTIONS
    # (Currently dummy logic)
    # Future:
    # Connect SMS/App usage detection
    # -------------------------------------------------------

    def unused_count(self):

        count = 0

        for sub in self.subscriptions:

            if sub.get("status", "").lower() == "unused":
                count += 1

        return count

    # -------------------------------------------------------
    # MONTHLY COST
    # -------------------------------------------------------

    def monthly_cost(self):
        return round(
            self.summary.get("monthly_cost", 0),
            2
        )

    # -------------------------------------------------------
    # YEARLY COST
    # -------------------------------------------------------

    def yearly_cost(self):
        return round(
            self.summary.get("yearly_cost", 0),
            2
        )

    # -------------------------------------------------------
    # CATEGORY SPENDING
    # -------------------------------------------------------

    def category_spending(self):

        categories = defaultdict(float)

        for sub in self.subscriptions:

            category = self.get_category(
                sub["merchant"]
            )

            amount = sub["amount"]

            if sub["frequency"] == "Monthly":
                categories[category] += amount

            elif sub["frequency"] == "Weekly":
                categories[category] += amount * 4

            elif sub["frequency"] == "Yearly":
                categories[category] += amount / 12

        return {
            key: round(value, 2)
            for key, value in categories.items()
        }

    # -------------------------------------------------------
    # PRICE INCREASE LOSS
    # -------------------------------------------------------

    def monthly_price_loss(self):

        total = 0

        for sub in self.subscriptions:

            total += sub.get(
                "price_increase",
                0
            )

        return round(total, 2)

    # -------------------------------------------------------
    # POTENTIAL SAVINGS
    # -------------------------------------------------------

    def potential_monthly_savings(self):

        savings = 0

        for sub in self.subscriptions:

            if sub["status"] == "Unused":

                if sub["frequency"] == "Monthly":
                    savings += sub["amount"]

                elif sub["frequency"] == "Weekly":
                    savings += sub["amount"] * 4

                elif sub["frequency"] == "Yearly":
                    savings += sub["amount"] / 12

            savings += sub.get(
                "price_increase",
                0
            )

        return round(savings, 2)

    def potential_yearly_savings(self):

        return round(
            self.potential_monthly_savings() * 12,
            2
        )
        # -------------------------------------------------------
    # LEAK SCORE CALCULATION
    # -------------------------------------------------------

    def calculate_score(self):
        """
        Returns leak score (0-100)

        Scoring Logic:
        - Base score starts at 100.
        - More subscriptions reduce score.
        - Price increases reduce score.
        - Unused subscriptions reduce score.
        - High monthly spending reduces score.
        """

        score = 100

        total_subs = self.summary.get("total_subscriptions", 0)
        monthly_cost = self.monthly_cost()
        unused = self.unused_count()
        price_changes = self.price_increase_count()

        # Too many subscriptions
        score -= total_subs * 4

        # Unused subscriptions
        score -= unused * 12

        # Price increases
        score -= price_changes * 8

        # Monthly spending impact
        if monthly_cost > 10000:
            score -= 20

        elif monthly_cost > 7000:
            score -= 15

        elif monthly_cost > 5000:
            score -= 10

        elif monthly_cost > 2500:
            score -= 5

        # Keep score in range
        score = max(0, min(100, score))

        return round(score)

    # -------------------------------------------------------
    # RISK LEVEL
    # -------------------------------------------------------

    def risk_level(self):

        score = self.calculate_score()

        if score >= 80:
            return "Low"

        elif score >= 50:
            return "Medium"

        return "High"

    # -------------------------------------------------------
    # RISK COLOR
    # -------------------------------------------------------

    def risk_color(self):

        risk = self.risk_level()

        if risk == "Low":
            return "#22C55E"      # Green

        if risk == "Medium":
            return "#F59E0B"      # Orange

        return "#EF4444"          # Red

    # -------------------------------------------------------
    # DASHBOARD SUMMARY
    # -------------------------------------------------------

    def dashboard_summary(self):

        return {
            "leak_score": self.calculate_score(),
            "risk_level": self.risk_level(),
            "risk_color": self.risk_color(),

            "total_subscriptions":
                self.summary.get("total_subscriptions", 0),

            "monthly_cost":
                self.monthly_cost(),

            "yearly_cost":
                self.yearly_cost(),

            "monthly_savings":
                self.potential_monthly_savings(),

            "yearly_savings":
                self.potential_yearly_savings(),

            "price_increases":
                self.price_increase_count(),

            "unused_subscriptions":
                self.unused_count(),

            "category_spending":
                self.category_spending()
        }

    # -------------------------------------------------------
    # SUBSCRIPTION STATISTICS
    # -------------------------------------------------------

    def subscription_statistics(self):

        stats = {
            "Monthly": 0,
            "Weekly": 0,
            "Yearly": 0
        }

        for sub in self.subscriptions:

            freq = sub.get("frequency")

            if freq in stats:
                stats[freq] += 1

        return stats

    # -------------------------------------------------------
    # TOP EXPENSIVE SUBSCRIPTIONS
    # -------------------------------------------------------

    def top_expensive(self, limit=5):

        subs = sorted(
            self.subscriptions,
            key=lambda x: x["amount"],
            reverse=True
        )

        return subs[:limit]

        # -------------------------------------------------------
    # AI SUMMARY
    # -------------------------------------------------------

    def ai_summary(self):
        """
        Create a concise summary that can be sent directly to
        Gemini/Mistral for recommendations.
        """

        dashboard = self.dashboard_summary()

        summary = {
            "Leak Score": dashboard["leak_score"],
            "Risk": dashboard["risk_level"],
            "Total Subscriptions": dashboard["total_subscriptions"],
            "Monthly Cost": dashboard["monthly_cost"],
            "Yearly Cost": dashboard["yearly_cost"],
            "Potential Monthly Savings": dashboard["monthly_savings"],
            "Potential Yearly Savings": dashboard["yearly_savings"],
            "Price Increases": dashboard["price_increases"],
            "Unused Subscriptions": dashboard["unused_subscriptions"]
        }

        return summary

    # -------------------------------------------------------
    # RECOMMENDATIONS
    # -------------------------------------------------------

    def recommendations(self):

        recommendations = []

        if self.unused_count() > 0:
            recommendations.append(
                "Cancel or pause unused subscriptions."
            )

        if self.price_increase_count() > 0:
            recommendations.append(
                "Review subscriptions with recent price increases."
            )

        if self.monthly_cost() > 3000:
            recommendations.append(
                "Your monthly subscription spending is high. Consider downgrading premium plans."
            )

        if self.calculate_score() < 50:
            recommendations.append(
                "Immediate action recommended to reduce unnecessary recurring payments."
            )

        if len(recommendations) == 0:
            recommendations.append(
                "Great! Your subscriptions appear to be well managed."
            )

        return recommendations

    # -------------------------------------------------------
    # COMPLETE REPORT
    # -------------------------------------------------------

    def generate_report(self):

        return {
            "dashboard": self.dashboard_summary(),
            "statistics": self.subscription_statistics(),
            "category_spending": self.category_spending(),
            "top_expensive": self.top_expensive(),
            "subscriptions": self.subscriptions,
            "recommendations": self.recommendations(),
            "ai_summary": self.ai_summary()
        }


# ===========================================================
# TEST CODE
# ===========================================================

if __name__ == "__main__":

    sample_subscriptions = [
        {
            "merchant": "Netflix",
            "frequency": "Monthly",
            "amount": 649,
            "first_payment": "2026-01-01",
            "last_payment": "2026-06-01",
            "payments": 6,
            "price_changed": False,
            "price_increase": 0,
            "status": "Active"
        },
        {
            "merchant": "Spotify",
            "frequency": "Monthly",
            "amount": 119,
            "first_payment": "2026-01-05",
            "last_payment": "2026-06-05",
            "payments": 6,
            "price_changed": True,
            "price_increase": 20,
            "status": "Unused"
        },
        {
            "merchant": "Amazon Prime",
            "frequency": "Yearly",
            "amount": 1499,
            "first_payment": "2025-12-15",
            "last_payment": "2026-12-15",
            "payments": 2,
            "price_changed": False,
            "price_increase": 0,
            "status": "Active"
        }
    ]

    sample_summary = {
        "total_subscriptions": 3,
        "monthly_cost": 893,
        "yearly_cost": 10535
    }

    engine = LeakScoreEngine(
        sample_subscriptions,
        sample_summary
    )

    report = engine.generate_report()

    print("=" * 60)
    print("LEAKGUARD AI REPORT")
    print("=" * 60)

    print(f"Leak Score           : {report['dashboard']['leak_score']}")
    print(f"Risk Level           : {report['dashboard']['risk_level']}")
    print(f"Monthly Cost         : ₹{report['dashboard']['monthly_cost']}")
    print(f"Yearly Cost          : ₹{report['dashboard']['yearly_cost']}")
    print(f"Monthly Savings      : ₹{report['dashboard']['monthly_savings']}")
    print(f"Yearly Savings       : ₹{report['dashboard']['yearly_savings']}")
    print(f"Price Increases      : {report['dashboard']['price_increases']}")
    print(f"Unused Subscriptions : {report['dashboard']['unused_subscriptions']}")

    print("\nCategory Spending")
    for category, amount in report["category_spending"].items():
        print(f"  {category:<20} ₹{amount}")

    print("\nTop Expensive Subscriptions")
    for sub in report["top_expensive"]:
        print(f"  {sub['merchant']:<20} ₹{sub['amount']}")

    print("\nRecommendations")
    for rec in report["recommendations"]:
        print(f" • {rec}")

    print("\nAI Summary")
    print(report["ai_summary"])

    print("=" * 60)