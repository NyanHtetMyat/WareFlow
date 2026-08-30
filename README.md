# 🏭 WareFlow

> **WareFlow** is an academic capstone project, a web-based Warehouse Management System (WMS) designed for managing (tracking) warehouse inventory and user operations.

This project was developed for academic purposes and is not intended to represent a production-ready commercial warehouse management system.

## Overview

WareFlow uses a role-based structure where different users have different responsibilities.

## User Roles

### Staff

* Perform inbound and outbound stock operations.
* Submit stock adjustment requests for manager review.

### Manager

* Manage products and suppliers.
* Monitor inventory and stock levels.
* Review and approve/reject stock adjustment requests.
* View warehouse reports.

### Admin

* Create and manage user accounts.
* Activate or deactivate accounts.
* Handle password-reset requests.

> The **Admin** role is dedicated to application-level account management and is separate from Django's technical **Superuser** role.


The **Admin** role is specifically intended for application-level account management. It is separate from Django's technical **Superuser** role.

## Tech Stack

* **Backend:** Python, Django
* **Database:** SQLite3
* **Frontend:** HTML, CSS, JavaScript, Bootstrap
* **Charts:** Chart.js

## Getting Started

### 1. Clone the repository

```bash
git clone <repository-url>
cd WareFlow
```

### 2. Create a virtual environment

Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

Linux/macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Apply database migrations

```bash
python manage.py migrate
```

### 5. Create an initial Django superuser

```bash
python manage.py createsuperuser
```

Follow the prompts to create the account.

> **Important:** New installations do not contain a default WareFlow user account. WareFlow is designed so that application users are created by a WareFlow Admin rather than through public registration.

The Django superuser created above can access Django's technical administration interface. If you want to use this account as a WareFlow Admin during initial setup, open Django Admin and assign its WareFlow role to **ADMIN**.

Alternatively, you can create a separate WareFlow Admin account through Django Admin.

### 6. Start the development server

```bash
python manage.py runserver
```

Then open the address shown by Django in your browser.

## Offline Usage

After the project dependencies have been installed, **WareFlow does not require an active internet connection to run**.

Third-party frontend dependencies used by the application, including Bootstrap, Bootstrap Icons, and Chart.js, are stored locally within the project's static files rather than being loaded from external CDNs.

Therefore, once the Python dependencies have been installed, the application can be run locally without an internet connection.

## User Management

WareFlow does not use public user registration.

Instead, the **Admin** creates Staff and Manager accounts and provides their initial credentials. Users can subsequently manage their own permitted profile information and change their own passwords through the application.

Django's **Superuser** and WareFlow's **Admin** are intentionally separate concepts:

* **Django Superuser** — technical/framework-level administration through Django Admin.
* **WareFlow Admin** — application-level user and account management.

The Django superuser is primarily useful for the initial setup and technical administration of the project.

## Project Structure

The project follows a role-based warehouse management design. The system intentionally keeps each role's responsibilities separated to avoid unnecessary overlap between warehouse daily operations, warehouse management and account administration.
