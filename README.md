# CRM Software: Customer & Lead Management System

A full-stack CRM web application built using Python, Flask, SQLite, and Chart.js to track customers, manage leads through a sales pipeline, log interactions, and visualize analytics[cite: 18, 19, 20].

## Features
- **Authentication:** Secure session-based authentication with password hashing[cite: 19].
- **Customer Directory:** Full CRUD operations with phone, email, and company tracking[cite: 18, 19].
- **Sales Pipeline:** Lead management filtered by stage (`New`, `Contacted`, `Qualified`, `Won`, `Lost`)[cite: 18, 19].
- **Interaction Log:** Track calls, emails, and meetings per lead[cite: 18, 19].
- **Executive Dashboard:** Chart.js pipeline metrics and recent activity feeds[cite: 20].
- **Exporting:** Single-click CSV export for customer records[cite: 20].

## Setup & Running
```bash
pip install -r requirements.txt
python app.py