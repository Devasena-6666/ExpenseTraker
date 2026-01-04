from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret123"

# ---------- DATABASE CONNECTION ----------
def get_db_connection():
    conn = sqlite3.connect("expense.db")
    conn.row_factory = sqlite3.Row
    return conn


# ---------- CREATE TABLES ----------
def create_tables():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            user_id INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            amount REAL,
            category_id INTEGER,
            user_id INTEGER,
            date TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            month TEXT,
            amount REAL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            source TEXT,
            amount REAL,
            date TEXT
        )
    """)

    conn.commit()
    conn.close()


# ---------- INSERT DEFAULT CATEGORIES ----------
def insert_default_categories():
    conn = get_db_connection()
    defaults = ["Food", "Travel", "Rent", "Education", "Medical"]

    existing = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    if existing == 0:
        for cat in defaults:
            conn.execute(
                "INSERT INTO categories (name, user_id) VALUES (?, NULL)",
                (cat,)
            )

    conn.commit()
    conn.close()


# ---------- FETCH CATEGORIES ----------
def get_categories(user_id):
    conn = get_db_connection()
    cats = conn.execute("""
        SELECT * FROM categories 
        WHERE user_id IS NULL OR user_id=?
    """, (user_id,)).fetchall()
    conn.close()
    return cats


# ---------- HOME ----------
@app.route("/")
def home():
    return redirect("/login")


# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (request.form["username"], request.form["password"])
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            return redirect("/dashboard")
        return "Invalid Login"

    return render_template("login.html")


# ---------- REGISTER ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO users (username,password) VALUES (?,?)",
                (request.form["username"], request.form["password"])
            )
            conn.commit()
            conn.close()
            return redirect("/login")
        except:
            return "Username exists"

    return render_template("register.html")


# ---------- DASHBOARD ----------


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    uid = session["user_id"]
    conn = get_db_connection()
    user = conn.execute(
    "SELECT username FROM users WHERE id=?",
    (uid,)
    ).fetchone()

    username = user["username"] if user else ""

    # ---------------- EXPENSE LIST ----------------
    expenses = conn.execute("""
        SELECT expenses.*, categories.name AS category
        FROM expenses
        JOIN categories ON expenses.category_id = categories.id
        WHERE expenses.user_id=?
        ORDER BY date DESC
    """, (uid,)).fetchall()

    # ---------------- TOTAL EXPENSE ----------------
    total = conn.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id=?",
        (uid,)
    ).fetchone()[0] or 0

    # ---------------- MONTH-WISE TOTAL ----------------
    month_totals = conn.execute("""
        SELECT strftime('%Y-%m', date) AS month,
               SUM(amount) AS total
        FROM expenses
        WHERE user_id=?
        GROUP BY month
        ORDER BY month DESC
    """, (uid,)).fetchall()

    # ---------------- CURRENT & PREVIOUS MONTH ----------------
    current_month = conn.execute("""
        SELECT SUM(amount)
        FROM expenses
        WHERE user_id=?
        AND strftime('%Y-%m', date)=strftime('%Y-%m','now')
    """, (uid,)).fetchone()[0] or 0

    previous_month = conn.execute("""
        SELECT SUM(amount)
        FROM expenses
        WHERE user_id=?
        AND strftime('%Y-%m', date)=strftime('%Y-%m','now','-1 month')
    """, (uid,)).fetchone()[0] or 0

    difference = current_month - previous_month

    # ---------------- BUDGET ----------------
    current_month_str = datetime.now().strftime("%Y-%m")

    budget_row = conn.execute("""
        SELECT amount FROM budgets
        WHERE user_id=? AND month=?
    """, (uid, current_month_str)).fetchone()

    budget = budget_row["amount"] if budget_row else 0

    alert = ""
    if budget and current_month > budget:
        alert = "⚠ Budget Exceeded!"

    remaining_budget = budget - current_month if budget else 0
    usage_percent = int((current_month / budget) * 100) if budget else 0

    # ---------------- INCOME & SAVINGS ----------------
    total_income = conn.execute("""
        SELECT SUM(amount) FROM income WHERE user_id=?
    """, (uid,)).fetchone()[0] or 0

    savings = total_income - total

    categories = get_categories(uid)
    alert = None
    if budget and current_month > budget:
        alert = "⚠️ Budget exceeded! Reduce spending."

    conn.close()

    return render_template(
        "index.html",
        username=username,
        expenses=expenses,
        total=total,
        categories=categories,
        month_totals=month_totals,
        current_month=current_month,
        previous_month=previous_month,
        difference=difference,
        budget=budget,
        alert=alert,
        remaining_budget=remaining_budget,
        usage_percent=usage_percent,
        total_income=total_income,
        savings=savings
    )
# ---------- ADD EXPENSE ----------
@app.route("/add", methods=["POST"])
def add_expense():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO expenses (title, amount, category_id, user_id, date)
        VALUES (?, ?, ?, ?, ?)
    """, (
        request.form["title"],
        request.form["amount"],
        request.form["category_id"],
        session["user_id"],
        request.form["date"]
    ))

    conn.commit()
    conn.close()
    return redirect("/dashboard")



# ---------- ADD CUSTOM CATEGORY ----------
@app.route("/add-category", methods=["POST"])
def add_category():
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO categories (name,user_id) VALUES (?,?)",
        (request.form["category"], session["user_id"])
    )
    conn.commit()
    conn.close()
    return redirect("/dashboard")


# ---------- DELETE ----------
@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM expenses WHERE id=? AND user_id=?",
        (id, session["user_id"])
    )
    conn.commit()
    conn.close()
    return redirect("/dashboard")

@app.route("/set-budget", methods=["POST"])
def set_budget():
    uid = session["user_id"]
    month = request.form["month"]  # YYYY-MM
    amount = request.form["amount"]

    conn = get_db_connection()
    conn.execute("""
        DELETE FROM budgets WHERE user_id=? AND month=?
    """, (uid, month))

    conn.execute("""
        INSERT INTO budgets (user_id, month, amount)
        VALUES (?,?,?)
    """, (uid, month, amount))

    conn.commit()
    conn.close()
    return redirect("/dashboard")
@app.route("/add-income", methods=["POST"])
def add_income():
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO income (user_id, source, amount, date)
        VALUES (?,?,?,?)
    """, (
        session["user_id"],
        request.form["source"],
        request.form["amount"],
        request.form["date"]
    ))
    conn.commit()
    conn.close()
    return redirect("/dashboard")
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()

    if request.method == "POST":
        conn.execute("""
            UPDATE expenses
            SET title=?, amount=?, category_id=?, date=?
            WHERE id=? AND user_id=?
        """, (
            request.form["title"],
            request.form["amount"],
            request.form["category_id"],
            request.form["date"],
            id,
            session["user_id"]
        ))
        conn.commit()
        conn.close()
        return redirect("/dashboard")

    # GET → fetch existing expense
    expense = conn.execute("""
        SELECT * FROM expenses
        WHERE id=? AND user_id=?
    """, (id, session["user_id"])).fetchone()

    categories = get_categories(session["user_id"])
    conn.close()

    return render_template(
        "edit.html",
        expense=expense,
        categories=categories
    )

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------- RUN ----------
if __name__ == "__main__":
    create_tables()
    insert_default_categories()
    app.run(debug=True)
