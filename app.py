from pathlib import Path

from flask import Flask, render_template, redirect, url_for, request, flash, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "replace-with-a-secure-secret"
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = Path(app.root_path) / "uploads"
app.config["UPLOAD_FOLDER"].mkdir(exist_ok=True)

users = {}


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

if __name__ == "__main__":
    app.run(debug=True)
