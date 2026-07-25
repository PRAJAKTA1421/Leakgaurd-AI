import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, jsonify, render_template, redirect, url_for, request, flash, session
from werkzeug.utils import secure_filename


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

app = Flask(__name__)
app.secret_key = "replace-with-a-secure-secret"
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = Path(app.root_path) / "uploads"
app.config["UPLOAD_FOLDER"].mkdir(exist_ok=True)

users = {}

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
    return render_template("dashboard.html")

@app.route("/subscriptions")
def subscriptions():
    return render_template("subscriptions.html")

@app.route("/transactions")
def transactions():
    return render_template("feature.html", page="transactions", title="Transactions", subtitle="View all detected recurring transactions.")

@app.route("/price-changes")
def price_changes():
    return render_template("feature.html", page="price_changes", title="Price Changes", subtitle="Subscriptions with price increases.")

@app.route("/unused-subscriptions")
def unused_subscriptions():
    return render_template("feature.html", page="unused", title="Unused Subscriptions", subtitle="Subscriptions you are paying for but not using.")

@app.route("/alerts")
def alerts():
    return render_template("feature.html", page="alerts", title="Alerts", subtitle="Important alerts and recommendations.")

@app.route("/reports")
def reports():
    return render_template("feature.html", page="reports", title="Reports", subtitle="Analyze your subscription spending.")

@app.route("/data-sources")
def data_sources():
    return render_template("feature.html", page="data_sources", title="Data Sources", subtitle="Manage your connected data sources.")

@app.route("/add-data-source", methods=["GET", "POST"])
def add_data_source():
    if request.method == "POST":
        statement = request.files.get("statement")
        if not statement or not statement.filename:
            flash("Please choose a subscription statement PDF.", "error")
        elif not statement.filename.lower().endswith(".pdf"):
            flash("Only PDF files can be uploaded.", "error")
        else:
            filename = secure_filename(statement.filename)
            statement.save(app.config["UPLOAD_FOLDER"] / filename)
            session["uploaded_statement"] = filename
            flash(f"{filename} uploaded successfully. Your subscriptions are ready to review.", "success")
            return redirect(url_for("dashboard"))
    return render_template("add_data_source.html")

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
    app.run(debug=True)
