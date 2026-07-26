import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.platypus import Image
from reportlab.lib.units import inch
from datetime import datetime
from fileinput import filename
import json
from operator import sub
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from routes import report
from services.parser import StatementParser
from flask import Flask, jsonify, render_template, redirect, url_for, request, flash, session, send_from_directory
from werkzeug.utils import secure_filename
from services.recurring_detector import detect_recurring
from services.leak_score import LeakScoreEngine
from collections import defaultdict

from io import BytesIO

from flask import send_file

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
def load_env_file(env_path):
    """Load simple KEY=value entries from a private .env file without extra packages."""
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


load_env_file(Path(__file__).with_name(".env"))
env_path = Path(__file__).with_name(".env")


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "development-only-secret")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = Path(app.root_path) / "uploads"
app.config["UPLOAD_FOLDER"].mkdir(exist_ok=True)


@app.route("/styles.css")
def styles():
    """Serve the stylesheet through Flask for hosts that don't expose /static."""
    return send_from_directory(app.static_folder, "styles.css", mimetype="text/css")

users = {}
parser = StatementParser()

def generate_monthly_spending(transactions):

    monthly = defaultdict(float)

    for tx in transactions:

        try:
            date = str(tx["date"])

            # yyyy-mm-dd format
            month = date[:7]

            monthly[month] += float(
                tx["amount"]
            )

        except Exception:
            continue

    return dict(monthly)

def create_category_chart(category_data):

    chart_path = "category_chart.png"


    labels = list(category_data.keys())
    values = list(category_data.values())


    plt.figure(figsize=(5,5))

    plt.pie(
        values,
        labels=labels,
        autopct="%1.1f%%"
    )

    plt.title(
        "Subscription Spending by Category"
    )

    plt.savefig(
        chart_path,
        bbox_inches="tight"
    )

    plt.close()


    return chart_path

CHAT_SYSTEM_PROMPT = """You are LeakGuard, a friendly financial-assistant chatbot for LeakGuard AI.
Help users understand subscriptions, recurring payments, potential savings, and how to use this app.
Do not claim you can access the user's bank account or see data that was not provided. Keep responses concise,
supportive, and practical. You do not provide financial, legal, or tax advice."""


def initials(name):
    return "".join(part[0] for part in name.split()[:2]).upper() or "LG"


@app.context_processor
def inject_user():
    name = session.get("user_name", "Guest")
    return {"current_user": name, "user_initials": initials(name)}

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        if email and password:
            session["user_name"] = users.get(email.lower(), email.split("@")[0].replace(".", " ").title())
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))
        flash("Please enter both email and password.", "error")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():

    dashboard = session.get("dashboard", {})

    subscriptions = session.get("subscriptions", [])

    recommendations = session.get("recommendations", [])

    statistics = session.get("statistics", {})

    category_spending = session.get(
        "category_spending",
        {}
    )

    transactions = session.get(
        "transactions",
        []
    )

    return render_template(
        "dashboard.html",

        dashboard=dashboard,

        subscriptions=subscriptions,

        recommendations=recommendations,

        statistics=statistics,

        category_spending=category_spending,

        transactions=transactions
    )

@app.route("/subscriptions")
def subscriptions():

    subscriptions = session.get("subscriptions", [])

    dashboard = session.get("dashboard", {})

    return render_template(
        "subscriptions.html",
        subscriptions=subscriptions,
        dashboard=dashboard
    )

@app.route("/subscription/<merchant>")
def subscription_details(merchant):

    subscriptions = session.get("subscriptions", [])

    sub = next(
        (
            s
            for s in subscriptions
            if s["merchant"].lower() == merchant.lower()
        ),
        None
    )

    if not sub:
        flash("Subscription not found.", "error")
        return redirect(url_for("subscriptions"))

    from datetime import datetime, timedelta

    last_payment = datetime.strptime(
        sub["last_payment"],
        "%Y-%m-%d"
    )

    if sub["frequency"] == "Monthly":
        next_bill = last_payment + timedelta(days=30)

    elif sub["frequency"] == "Weekly":
        next_bill = last_payment + timedelta(days=7)

    elif sub["frequency"] == "Yearly":
        next_bill = last_payment + timedelta(days=365)

    else:
        next_bill = last_payment

    sub["next_billing"] = next_bill.strftime("%d %b %Y")

    sub["total_paid"] = round(
        sub["amount"] * sub["payments"],
        2
    )

    if sub["price_changed"]:
        sub["previous_price"] = (
            sub["amount"] - sub["price_increase"]
        )
    else:
        sub["previous_price"] = sub["amount"]

    return render_template(
        "subscription_details.html",
        subscription=sub
    )

@app.route("/transactions")
def transactions():

    transactions = session.get("transactions", [])
    subscriptions = session.get("subscriptions", [])
    dashboard = session.get("dashboard", {})

    total_debit = sum(
        tx["amount"]
        for tx in transactions
        if tx.get("type") == "Debit"
    )

    return render_template(
        "feature.html",
        page="transactions",
        title="Transactions",
        subtitle="View all detected recurring transactions.",
        transactions=transactions,
        subscriptions=subscriptions,
        dashboard=dashboard,
        total_debit=round(total_debit, 2)
    )


@app.route("/price-changes")
def price_changes():

    subscriptions = session.get("subscriptions", [])

    price_changes = [
        s for s in subscriptions
        if s.get("price_changed")
    ]

    total_increase = sum(
        s["price_increase"]
        for s in price_changes
    )

    return render_template(
        "feature.html",
        page="price_changes",
        title="Price Changes",
        subtitle="Detected subscription price increases.",
        price_changes=price_changes,
        total_increase=round(total_increase, 2)
    )


@app.route("/unused-subscriptions")
def unused_subscriptions():

    subscriptions = session.get("subscriptions", [])

    unused = [
        s for s in subscriptions
        if s.get("unused")
    ]

    total_unused_savings = sum(
        s["amount"]
        for s in unused
    )

    return render_template(
        "feature.html",
        page="unused",
        title="Unused Subscriptions",
        subtitle="Subscriptions you are paying for but not using.",
        unused_subscriptions=unused,
        total_unused_savings=total_unused_savings
    )
@app.route("/alerts")
def alerts():

    subscriptions = session.get("subscriptions", [])

    alerts = []

    for sub in subscriptions:

        # Price Increase Alert
        if sub.get("price_changed"):
            alerts.append({
                "icon": "🔺",
                "title": f"Price increase detected for {sub['merchant']}",
                "message": f"New amount: ₹{sub['amount']:.2f} (+₹{sub['price_increase']:.2f})",
                "type": "Price Hike",
                "time": "Recently"
            })

        # Unused Subscription Alert
        if sub.get("unused"):
            alerts.append({
                "icon": "⚠️",
                "title": f"{sub['merchant']} appears unused",
                "message": f"You may save ₹{sub['amount']:.2f} every month.",
                "type": "Unused",
                "time": "Recently"
            })

    # High Monthly Spending Alert
    monthly_cost = sum(s["amount"] for s in subscriptions)

    if monthly_cost > 3000:
        alerts.append({
            "icon": "💰",
            "title": "High Monthly Subscription Spend",
            "message": f"You are spending ₹{monthly_cost:.2f} every month.",
            "type": "General",
            "time": "Today"
        })

    # Too Many Subscriptions Alert
    if len(subscriptions) >= 8:
        alerts.append({
            "icon": "📦",
            "title": "Large Number of Active Subscriptions",
            "message": f"You currently have {len(subscriptions)} subscriptions.",
            "type": "General",
            "time": "Today"
        })

    return render_template(
        "feature.html",
        page="alerts",
        title="Alerts",
        subtitle="Important subscription notifications.",
        alerts=alerts
    )
@app.route("/reports")
def reports():

    leak_report = session.get("leak_report", {})

    transactions = session.get(
        "transactions",
        []
    )


    monthly_spending = generate_monthly_spending(
        transactions
    )

    dashboard = leak_report.get(
        "dashboard",
        {}
    )

    subscriptions = leak_report.get(
        "subscriptions",
        []
    )

    category_spending = leak_report.get(
        "category_spending",
        {}
    )


    return render_template(
        "feature.html",

        page="reports",

        title="Reports",

        subtitle="AI powered spending analysis",

        total_spend=dashboard.get(
            "monthly_cost",
            0
        ),

        total_savings=dashboard.get(
            "monthly_savings",
            0
        ),

        yearly_savings=dashboard.get(
            "yearly_savings",
            0
        ),

        active_subscriptions=dashboard.get(
            "total_subscriptions",
            0
        ),

        unused_subscriptions=dashboard.get(
            "unused_subscriptions",
            0
        ),

        leak_score=dashboard.get(
            "leak_score",
            0
        ),

        risk_level=dashboard.get(
            "risk_level",
            "Low"
        ),

        category_spending=category_spending,

        top_expensive=leak_report.get(
            "top_expensive",
            []
        ),

        ai_summary=leak_report.get(
            "ai_summary",
            {}
        ),

        statistics=session.get(
            "statistics",
            {}
        ),

        monthly_spending=monthly_spending
    )

@app.route("/data-sources")
def data_sources():
    return render_template("feature.html", page="data_sources", title="Data Sources", subtitle="Manage your connected data sources.")

@app.route("/add-data-source", methods=["GET", "POST"])
def add_data_source():
    if request.method == "POST":
        statement = request.files.get("statement")
        if not statement or not statement.filename:
            flash("Please choose a subscription statement PDF.", "error")
        allowed_extensions = (".pdf", ".csv")

        if not statement.filename.lower().endswith(allowed_extensions):
            flash("Only PDF or CSV files can be uploaded.", "error")
        else:
            filename = secure_filename(statement.filename)

            filepath = app.config["UPLOAD_FOLDER"] / filename

            statement.save(filepath)

            print("PDF SAVED:", filepath)

            # Parse the uploaded statement
            transactions = parser.parse(filepath)

            # -----------------------------------------
            # Detect recurring subscriptions
            # -----------------------------------------
            subscriptions, summary = detect_recurring(transactions)

            print("\n========== SUBSCRIPTIONS ==========")

            for sub in subscriptions:
                print(sub)

            print(summary)

            # -----------------------------------------
            # Calculate Leak Score
            # -----------------------------------------
            engine = LeakScoreEngine(
                subscriptions,
                summary
            )

            # Add category to each subscription
            for sub in subscriptions:
                sub["category"] = engine.get_category(sub["merchant"])

            report = engine.generate_report()

            print("\n========== LEAK REPORT ==========")
            print(report)

            # -----------------------------------------
            # Store everything in session
            # -----------------------------------------
            session["uploaded_statement"] = filename
            session["transactions"] = transactions
            session["subscriptions"] = subscriptions
            session["leak_report"] = report

            session["dashboard"] = report["dashboard"]
            session["recommendations"] = report["recommendations"]
            session["statistics"] = report["statistics"]
            session["category_spending"] = report["category_spending"]

            flash(
                f"{filename} uploaded and analyzed successfully!",
                "success"
            )

            return redirect(url_for("dashboard"))
    return render_template("add_data_source.html")

@app.route("/download-report")
def download_report():

    leak_report = session.get(
        "leak_report",
        {}
    )


    if not leak_report:

        flash(
            "No report available.",
            "error"
        )

        return redirect(
            url_for("reports")
        )


    dashboard = leak_report["dashboard"]

    subscriptions = leak_report["subscriptions"]

    recommendations = leak_report["recommendations"]


    category_spending = leak_report.get(
        "category_spending",
        {}
    )


    chart = create_category_chart(
        category_spending
    )


    buffer = BytesIO()


    pdf = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )


    styles = getSampleStyleSheet()


    elements=[]


    # ----------------------------
    # TITLE
    # ----------------------------

    title = Paragraph(
        """
        <font size=20 color='#6D28D9'>
        LeakGuard AI
        </font>
        <br/>
        Financial Leak Analysis Report
        """,
        styles["Title"]
    )


    elements.append(title)


    elements.append(
        Spacer(1,20)
    )


    elements.append(
        Paragraph(
            f"""
            Generated on:
            {datetime.now().strftime('%d %B %Y')}
            """,
            styles["Normal"]
        )
    )


    elements.append(
        Spacer(1,25)
    )


    # ----------------------------
    # SCORE CARD
    # ----------------------------


    risk = dashboard.get(
        "risk_level",
        "Low"
    )


    score_table = Table(
        [
            [
                "Leak Score",
                "Risk Level",
                "Monthly Spend",
                "Savings Opportunity"
            ],

            [
                str(
                    dashboard.get(
                        "leak_score",
                        0
                    )
                )+"/100",

                risk,

                f"₹{dashboard.get('monthly_cost',0)}",

                f"₹{dashboard.get('monthly_savings',0)}"

            ]

        ]
    )


    score_table.setStyle(

        TableStyle([

            (
            "GRID",
            (0,0),
            (-1,-1),
            0.5,
            colors.grey
            ),

            (
            "BACKGROUND",
            (0,0),
            (-1,0),
            colors.lightgrey
            ),

            (
            "ALIGN",
            (0,0),
            (-1,-1),
            "CENTER"
            )

        ])

    )


    elements.append(
        score_table
    )


    elements.append(
        Spacer(1,30)
    )


    # ----------------------------
    # CATEGORY CHART
    # ----------------------------


    elements.append(
        Paragraph(
            "Spending Analysis",
            styles["Heading2"]
        )
    )


    elements.append(
        Image(
            chart,
            width=4*inch,
            height=4*inch
        )
    )


    elements.append(
        Spacer(1,25)
    )



    # ----------------------------
    # SUBSCRIPTIONS TABLE
    # ----------------------------


    elements.append(
        Paragraph(
            "Detected Subscriptions",
            styles["Heading2"]
        )
    )


    data=[
        [
            "Merchant",
            "Category",
            "Cycle",
            "Amount"
        ]
    ]


    for sub in subscriptions:

        data.append(
            [
                sub["merchant"],

                sub.get(
                    "category",
                    "Others"
                ),

                sub["frequency"],

                f"₹{sub['amount']}"

            ]
        )


    table = Table(
        data
    )


    table.setStyle(

        TableStyle([

            (
            "GRID",
            (0,0),
            (-1,-1),
            0.5,
            colors.grey
            ),

            (
            "BACKGROUND",
            (0,0),
            (-1,0),
            colors.lightgrey
            )

        ])

    )


    elements.append(
        table
    )


    elements.append(
        Spacer(1,30)
    )


    # ----------------------------
    # AI RECOMMENDATIONS
    # ----------------------------


    elements.append(
        Paragraph(
            "AI Recommendations",
            styles["Heading2"]
        )
    )


    for rec in recommendations:

        elements.append(

            Paragraph(
                "• "+rec,
                styles["BodyText"]
            )

        )

        elements.append(
            Spacer(1,8)
        )



    pdf.build(
        elements
    )


    buffer.seek(0)


    return send_file(

        buffer,

        as_attachment=True,

        download_name=
        "LeakGuard_AI_Report.pdf",

        mimetype=
        "application/pdf"

    )


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

@app.route("/settings")
def settings():
    return render_template("feature.html", page="settings", title="Settings", subtitle="Manage your preferences and account.")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        if name and email and password:
            users[email.lower()] = name.strip()
            session["user_name"] = name.strip()
            flash("Registration successful. Welcome to LeakGuard AI!", "success")
            return redirect(url_for("dashboard"))
        flash("Please complete all fields.", "error")
    return render_template("register.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    """Proxy chat messages to Mistral without exposing the API key to the browser."""
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        return jsonify(error="Chat is not configured yet. Add MISTRAL_API_KEY to the server environment."), 503

    incoming_messages = (request.get_json(silent=True) or {}).get("messages", [])
    if not isinstance(incoming_messages, list):
        return jsonify(error="Messages must be a list."), 400
    messages = []
    for item in incoming_messages[-12:]:
        if not isinstance(item, dict):
            continue
        role, content = item.get("role"), item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content.strip()[:2000]})
    if not messages or messages[-1]["role"] != "user":
        return jsonify(error="Please send a message."), 400

    payload = json.dumps({"model": os.environ.get("MISTRAL_MODEL", "mistral-small-latest"), "messages": [{"role": "system", "content": CHAT_SYSTEM_PROMPT}, *messages], "max_tokens": 400, "temperature": 0.5}).encode("utf-8")
    mistral_request = Request("https://api.mistral.ai/v1/chat/completions", data=payload, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(mistral_request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        reply = result["choices"][0]["message"]["content"]
        if isinstance(reply, list):
            reply = "".join(part.get("text", "") for part in reply if isinstance(part, dict))
        return jsonify(reply=reply or "I wasn't able to generate a response. Please try again.")
    except HTTPError as error:
        app.logger.warning("Mistral API request failed: %s", error.code)
    except (URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError):
        app.logger.exception("Mistral chat request failed")
    return jsonify(error="The chat service is temporarily unavailable. Please try again."), 502

if __name__ == "__main__":
    # Keep one process during local development so configuration changes in
    # .env take effect predictably after restarting the server.
    app.run(debug=True, use_reloader=False)
