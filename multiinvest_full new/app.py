from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector
from mysql.connector import errorcode
import os
import re
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()  # Load .env variables

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecret")

# MySQL connection config from .env
DB_CONFIG = {
    'host': os.getenv("DB_HOST", "RAILWAY_PRIVATE_DOMAIN"),  # Railway's private domain for MySQL
    'user': os.getenv("DB_USER", "root"),  # MySQL user
    'password': os.getenv("DB_PASSWORD", "your_password_here"),  # MySQL password from environment variables
    'database': os.getenv("DB_NAME", "railway"),  # MySQL database name
    'port': int(os.getenv("DB_PORT", 3306)),  # MySQL port
    'auth_plugin': 'mysql_native_password'  # Required for MySQL authentication
}


def get_db_connection():
    """Establish and return a database connection."""
    conn = mysql.connector.connect(**DB_CONFIG)
    return conn

def init_db():
    """Drops and recreates all tables, then seeds initial data."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Drop tables if they exist (in correct order due to foreign keys)
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
    """Retrieve current user from the session."""
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
    """Inject current user into all templates."""
    return dict(user=current_user())

def is_valid_email(email):
    """Check if email is in a valid format."""
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def is_strong_password(password):
    """Check if the password is strong enough."""
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
    """Render the home page."""
    return render_template("index.html")

@app.route("/signup", methods=["GET","POST"])
def signup():
    """Handle user signup."""
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

@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["is_admin"] = bool(user["is_admin"])
            return redirect(url_for("dashboard"))

        flash("Invalid credentials")
        return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    """Log the user out."""
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    """Render the dashboard."""
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
    """Render investment opportunities."""
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
    """Handle investment requests."""
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

if __name__ == "__main__":
    init_db()  # Initialize the database tables and seed data on startup
    app.run(host="0.0.0.0", port=5000, debug=True)
