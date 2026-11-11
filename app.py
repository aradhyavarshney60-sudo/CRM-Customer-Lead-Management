import os
import sqlite3
import csv
import io
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "crm_super_secret_production_key"
DB_NAME = "crm_database.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'sales_rep'
        )
    """)
    
    # 2. Customers Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            company TEXT,
            notes TEXT,
            created_at TEXT NOT NULL
        )
    """)
    
    # 3. Leads Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            assigned_to INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES Customers (id) ON DELETE CASCADE,
            FOREIGN KEY (assigned_to) REFERENCES Users (id)
        )
    """)
    
    # 4. Interactions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            interaction_type TEXT NOT NULL,
            description TEXT NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (lead_id) REFERENCES Leads (id) ON DELETE CASCADE
        )
    """)
    
    # Create default demo admin user if not exists
    cursor.execute("SELECT * FROM Users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO Users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            ("admin", "admin@crm.local", generate_password_hash("admin123"), "admin")
        )
    
    conn.commit()
    conn.close()

init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# --- Auth Routes ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "danger")
            
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        
        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))
            
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO Users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, generate_password_hash(password))
            )
            conn.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username or Email already registered.", "danger")
        finally:
            conn.close()
            
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

# --- Dashboard ---
@app.route("/")
@login_required
def dashboard():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM Customers")
    total_customers = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM Leads")
    total_leads = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM Interactions")
    total_interactions = cursor.fetchone()[0]
    
    cursor.execute("SELECT status, COUNT(*) FROM Leads GROUP BY status")
    lead_status_rows = cursor.fetchall()
    status_counts = {"New": 0, "Contacted": 0, "Qualified": 0, "Won": 0, "Lost": 0}
    for row in lead_status_rows:
        if row[0] in status_counts:
            status_counts[row[0]] = row[1]
            
    cursor.execute("""
        SELECT i.*, c.name as customer_name 
        FROM Interactions i
        JOIN Leads l ON i.lead_id = l.id
        JOIN Customers c ON l.customer_id = c.id
        ORDER BY i.id DESC LIMIT 5
    """)
    recent_interactions = cursor.fetchall()
    conn.close()
    
    return render_template(
        "dashboard.html",
        total_customers=total_customers,
        total_leads=total_leads,
        total_interactions=total_interactions,
        status_counts=status_counts,
        recent_interactions=recent_interactions
    )

# --- Customers CRUD ---
@app.route("/customers")
@login_required
def customers():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Customers ORDER BY id DESC")
    customer_list = cursor.fetchall()
    conn.close()
    return render_template("customers.html", customers=customer_list)

@app.route("/customers/add", methods=["GET", "POST"])
@login_required
def add_customer():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        company = request.form.get("company", "").strip()
        notes = request.form.get("notes", "").strip()
        date_now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Customers (name, email, phone, company, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, phone, company, notes, date_now)
        )
        conn.commit()
        conn.close()
        flash("Customer added successfully!", "success")
        return redirect(url_for("customers"))
    return render_template("customer_form.html", action="Add")

@app.route("/customers/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_customer(id):
    conn = get_db()
    cursor = conn.cursor()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        company = request.form.get("company", "").strip()
        notes = request.form.get("notes", "").strip()
        
        cursor.execute(
            "UPDATE Customers SET name = ?, email = ?, phone = ?, company = ?, notes = ? WHERE id = ?",
            (name, email, phone, company, notes, id)
        )
        conn.commit()
        conn.close()
        flash("Customer updated successfully!", "success")
        return redirect(url_for("customers"))
        
    cursor.execute("SELECT * FROM Customers WHERE id = ?", (id,))
    customer = cursor.fetchone()
    conn.close()
    return render_template("customer_form.html", customer=customer, action="Edit")

@app.route("/customers/delete/<int:id>")
@login_required
def delete_customer(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Customers WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Customer deleted successfully.", "info")
    return redirect(url_for("customers"))

# --- Leads CRUD ---
@app.route("/leads")
@login_required
def leads():
    status_filter = request.args.get("status", "")
    conn = get_db()
    cursor = conn.cursor()
    
    query = """
        SELECT l.*, c.name as customer_name, c.company as customer_company, u.username as rep_name
        FROM Leads l
        JOIN Customers c ON l.customer_id = c.id
        LEFT JOIN Users u ON l.assigned_to = u.id
    """
    params = []
    if status_filter:
        query += " WHERE l.status = ?"
        params.append(status_filter)
    query += " ORDER BY l.id DESC"
    
    cursor.execute(query, tuple(params))
    lead_list = cursor.fetchall()
    conn.close()
    return render_template("leads.html", leads=lead_list, selected_status=status_filter)

@app.route("/leads/add", methods=["GET", "POST"])
@login_required
def add_lead():
    conn = get_db()
    cursor = conn.cursor()
    if request.method == "POST":
        customer_id = request.form.get("customer_id")
        status = request.form.get("status")
        assigned_to = session["user_id"]
        notes = request.form.get("notes", "").strip()
        date_now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        cursor.execute(
            "INSERT INTO Leads (customer_id, status, assigned_to, notes, created_at) VALUES (?, ?, ?, ?, ?)",
            (customer_id, status, assigned_to, notes, date_now)
        )
        conn.commit()
        conn.close()
        flash("Lead created successfully!", "success")
        return redirect(url_for("leads"))
        
    cursor.execute("SELECT id, name, company FROM Customers ORDER BY name")
    customers = cursor.fetchall()
    conn.close()
    return render_template("lead_form.html", customers=customers, action="Add")

@app.route("/leads/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_lead(id):
    conn = get_db()
    cursor = conn.cursor()
    if request.method == "POST":
        status = request.form.get("status")
        notes = request.form.get("notes", "").strip()
        cursor.execute("UPDATE Leads SET status = ?, notes = ? WHERE id = ?", (status, notes, id))
        conn.commit()
        conn.close()
        flash("Lead updated successfully!", "success")
        return redirect(url_for("leads"))
        
    cursor.execute("SELECT * FROM Leads WHERE id = ?", (id,))
    lead = cursor.fetchone()
    cursor.execute("SELECT id, name, company FROM Customers ORDER BY name")
    customers = cursor.fetchall()
    conn.close()
    return render_template("lead_form.html", lead=lead, customers=customers, action="Edit")

@app.route("/leads/delete/<int:id>")
@login_required
def delete_lead(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Leads WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Lead deleted.", "info")
    return redirect(url_for("leads"))

# --- Interactions CRUD ---
@app.route("/interactions", methods=["GET", "POST"])
@login_required
def interactions():
    conn = get_db()
    cursor = conn.cursor()
    if request.method == "POST":
        lead_id = request.form.get("lead_id")
        interaction_type = request.form.get("interaction_type")
        description = request.form.get("description", "").strip()
        date_now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        cursor.execute(
            "INSERT INTO Interactions (lead_id, interaction_type, description, date) VALUES (?, ?, ?, ?)",
            (lead_id, interaction_type, description, date_now)
        )
        conn.commit()
        flash("Interaction logged successfully!", "success")
        return redirect(url_for("interactions"))
        
    cursor.execute("""
        SELECT i.*, c.name as customer_name 
        FROM Interactions i
        JOIN Leads l ON i.lead_id = l.id
        JOIN Customers c ON l.customer_id = c.id
        ORDER BY i.id DESC
    """)
    all_interactions = cursor.fetchall()
    
    cursor.execute("""
        SELECT l.id, c.name, l.status 
        FROM Leads l 
        JOIN Customers c ON l.customer_id = c.id
    """)
    leads_available = cursor.fetchall()
    conn.close()
    return render_template("interactions.html", interactions=all_interactions, leads=leads_available)

# --- CSV Export Route ---
@app.route("/export-customers")
@login_required
def export_customers():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, phone, company, notes, created_at FROM Customers")
    rows = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Email", "Phone", "Company", "Notes", "Created At"])
    for r in rows:
        writer.writerow(list(r))
        
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=crm_customers.csv"}
    )

if __name__ == "__main__":
    app.run(debug=True, port=5000)