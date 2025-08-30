from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector
from mysql.connector import errorcode
import os
import re
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()  # Load .env variables

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

# MySQL connection config from .env
DB_CONFIG = {
    'host': os.getenv("DB_HOST", "trolley.proxy.rlwy.net"),
    'user': os.getenv("DB_USER", "root"),
    'password': os.getenv("DB_PASSWORD", "hExadlRGHJrMvQtAjpKMkRDQLTHeewbj"),
    'database': os.getenv("DB_NAME", "railway"),
    'port': int(os.getenv("DB_PORT", 22558)), 
    'auth_plugin': 'mysql_native_password'
}


def get_db_connection():
    conn = mysql.connector.connect(**DB_CONFIG)
    return conn

def init_db():
    """Drops and recreates all tables, then seeds initial data."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Drop tables if exist (in correct order due to foreign keys)
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    cursor.execute("DROP TABLE IF EXISTS withdrawals;")
    cursor.execute("DROP TABLE IF EXISTS investments;")
    cursor.execute("DROP TABLE IF EXISTS firms;")
    cursor.execute("DROP TABLE IF EXISTS users;")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

    # Create users table
    cursor.execute("""
        CREATE TABLE users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            balance DECIMAL(15,2) DEFAULT 0,
            is_admin TINYINT(1) DEFAULT 0
        )
    """)

    # Create firms table
    cursor.execute("""
        CREATE TABLE firms (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            image_url TEXT
        )
    """)

    # Create investments table
    cursor.execute("""
        CREATE TABLE investments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            firm_id INT,
            transaction_id VARCHAR(255),
            amount DECIMAL(15,2),
            status VARCHAR(50) DEFAULT 'pending',
            created_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (firm_id) REFERENCES firms(id) ON DELETE SET NULL
        )
    """)

    # Create withdrawals table
    cursor.execute("""
        CREATE TABLE withdrawals (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            wallet_address VARCHAR(255),
            amount DECIMAL(15,2),
            status VARCHAR(50) DEFAULT 'pending',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Seed default admin user (password hashed)
    hashed_password = generate_password_hash("admin123")
    cursor.execute("""
        INSERT INTO users (username, email, password, balance, is_admin)
        VALUES (%s, %s, %s, %s, %s)
    """, ("Admin", "admin@multinvest.com", hashed_password, 0, 1))

    # Seed firms
    firms = [
        ("Acme Estates", "Luxury villas and apartments in prime locations.", "https://images.unsplash.com/photo-1505691938895-1758d7feb511"),
        ("BlueSky Realty", "Affordable housing projects for first-time buyers.", "https://images.unsplash.com/photo-1494526585095-c41746248156"),
        ("Summit Homes", "Exclusive high-rise apartments with modern amenities.", "https://images.unsplash.com/photo-1568605114967-8130f3a36994")
    ]
    cursor.executemany("INSERT INTO firms (name, description, image_url) VALUES (%s, %s, %s)", firms)

    conn.commit()
    cursor.close()
    conn.close()

def current_user():
    if "user_id" not in session:
        return None
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (session["user_id"],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user

@app.context_processor
def inject_user():
    return dict(user=current_user())

def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def is_strong_password(password):
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    return True

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        email = request.form.get("email","").strip()
        password = request.form.get("password","")
        confirm = request.form.get("confirm","")

        if not username or not email or not password or not confirm:
            flash("All fields are required.")
            return redirect(url_for("signup"))

        if not is_valid_email(email):
            flash("Invalid email address.")
            return redirect(url_for("signup"))

        if not is_strong_password(password):
            flash("Password must be at least 8 characters long and contain uppercase, lowercase, and digits.")
            return redirect(url_for("signup"))

        if password != confirm:
            flash("Passwords do not match.")
            return redirect(url_for("signup"))

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                         (username, email, hashed_password))
            conn.commit()
            flash("Signup successful. Please log in.")
            return redirect(url_for("login"))
        except mysql.connector.IntegrityError as e:
            if e.errno == errorcode.ER_DUP_ENTRY:
                flash("Email already registered.")
            else:
                flash("An error occurred during signup.")
            return redirect(url_for("signup"))
        finally:
            cursor.close()
            conn.close()

    return render_template("signup.html")

from werkzeug.security import check_password_hash

@app.route("/login", methods=["GET", "POST"])
def login():
    print("Login route reached")  # Debug log
    if request.method == "POST":
        try:
            print("Handling POST request")  # Debug log

            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")

            print(f"Received email: {email}")  # Debug log

            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()

            if user:
                print("User found in DB")
                print(f"Checking password for user {user['id']}")
                if check_password_hash(user["password"], password):
                    session["user_id"] = user["id"]
                    session["is_admin"] = bool(user["is_admin"])
                    print("Login successful. Redirecting to dashboard.")
                    return redirect(url_for("dashboard"))
                else:
                    print("Password mismatch.")
            else:
                print("User not found.")

            flash("Invalid credentials")
            return redirect(url_for("login"))

        except Exception as e:
            print(f"🔥 Error during login: {e}")
            return "Internal Server Error", 500

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    user = current_user()

    cursor.execute("""
        SELECT i.*, f.name as firm_name 
        FROM investments i LEFT JOIN firms f ON i.firm_id = f.id 
        WHERE i.user_id = %s
    """, (session["user_id"],))
    investments = cursor.fetchall()

    cursor.execute("SELECT * FROM withdrawals WHERE user_id = %s", (session["user_id"],))
    withdrawals = cursor.fetchall()

    completed_total = sum(float(row["amount"]) for row in investments if row["status"] == "completed")
    projected_return = completed_total * 1.05

    cursor.close()
    conn.close()

    return render_template("dashboard.html", investments=investments, withdrawals=withdrawals,
                           completed_total=completed_total, projected_return=projected_return)

@app.route("/opportunities")
def opportunities():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM firms")
    firms = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("opportunities.html", firms=firms)

@app.route("/invest", methods=["POST"])
def invest():
    if "user_id" not in session:
        return redirect(url_for("login"))

    firm_id = request.form.get("firm_id")
    transaction_id = request.form.get("transaction_id","").strip()
    amount = request.form.get("amount","").strip()

    if not firm_id or not transaction_id or not amount:
        flash("Please complete all fields for investment.")
        return redirect(url_for("opportunities"))

    try:
        amount_val = float(amount)
        if amount_val <= 0:
            raise ValueError()
    except ValueError:
        flash("Invalid amount.")
        return redirect(url_for("opportunities"))

    created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO investments (user_id, firm_id, transaction_id, amount, status, created_at) 
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (session["user_id"], firm_id, transaction_id, amount_val, "pending", created_at))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Investment submitted and marked pending.")
    return redirect(url_for("opportunities"))

@app.route("/withdraw", methods=["POST"])
def withdraw():
    if "user_id" not in session:
        return redirect(url_for("login"))

    try:
        amount = float(request.form["amount"])
        wallet_address = request.form["wallet"]
    except (KeyError, ValueError):
        flash("Invalid withdrawal request.")
        return redirect(url_for("dashboard"))

    if amount <= 0:
        flash("Withdrawal amount must be greater than zero.")
        return redirect(url_for("dashboard"))

    user = current_user()
    if amount > float(user["balance"]):
        flash("Insufficient balance.")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO withdrawals (user_id, wallet_address, amount, status)
        VALUES (%s, %s, %s, %s)
    """, (session["user_id"], wallet_address, amount, "pending"))
    # Deduct user balance
    cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s", (amount, session["user_id"]))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Withdrawal request submitted.")
    return redirect(url_for("dashboard"))

@app.route("/admin")
def admin():
    if not session.get("is_admin"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # List all investments
    cursor.execute("""
        SELECT i.*, u.username, f.name as firm_name
        FROM investments i
        JOIN users u ON i.user_id = u.id
        LEFT JOIN firms f ON i.firm_id = f.id
        ORDER BY i.created_at DESC
    """)
    investments = cursor.fetchall()

    # List all users
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    # List all withdrawals
    cursor.execute("""
        SELECT w.*, u.username
        FROM withdrawals w
        JOIN users u ON w.user_id = u.id
        ORDER BY w.id DESC
    """)
    withdrawals = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin.html", investments=investments, users=users, withdrawals=withdrawals)

@app.route("/admin/approve_investment/<int:investment_id>")
def approve_investment(investment_id):
    if not session.get("is_admin"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Approve investment: update status and add amount to user balance
    cursor.execute("SELECT user_id, amount FROM investments WHERE id = %s", (investment_id,))
    inv = cursor.fetchone()
    if inv:
        user_id, amount = inv
        cursor.execute("UPDATE investments SET status = %s WHERE id = %s", ("completed", investment_id))
        cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
        conn.commit()

    cursor.close()
    conn.close()
    flash("Investment approved.")
    return redirect(url_for("admin"))

@app.route("/admin/approve_withdrawal/<int:withdrawal_id>")
def approve_withdrawal(withdrawal_id):
    if not session.get("is_admin"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE withdrawals SET status = %s WHERE id = %s", ("completed", withdrawal_id))
    conn.commit()

    cursor.close()
    conn.close()
    flash("Withdrawal approved.")
    return redirect(url_for("admin"))

@app.route("/admin/delete_user/<int:user_id>")
def delete_user(user_id):
    if not session.get("is_admin"):
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash("User deleted.")
    return redirect(url_for("admin"))

@app.route("/contact")
def contact():
    return render_template("contact.html")

# More routes like /contact can be added similarly with MySQL adjustments

if __name__ == "__main__":
    init_db()  # Initialize the database tables and seed data on startup
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
