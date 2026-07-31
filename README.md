# Nowhence Clothings

A luxury lehenga e-commerce website built with Django.

## Features

- **Product Catalog** — 58+ luxury lehenga products with categories, filtering, and search
- **Product Detail** — Image gallery, size guide, pincode availability checker
- **Shopping Cart** — Drawer-based cart with localStorage persistence
- **Multi-step Checkout** — Account → Shipping → Review flow
- **Authentication** — Username/password login, Phone OTP login, signup
- **Customer Portal** — Profile management, addresses, order history, order tracking, returns & exchanges
- **Admin Panel** — Django admin for managing products, orders, hero section, collections, and more
- **Dark Mode** — System-aware theme toggle with smooth transitions
- **Responsive Design** — Fully mobile-optimized with hamburger menu, collapsible sections
- **Smooth Animations** — Page transitions, scroll effects, parallax sections

## Tech Stack

- **Backend:** Django 6.0.2, Python 3.14
- **Database:** SQLite (development)
- **Frontend:** Vanilla HTML/CSS/JS, Font Awesome icons
- **Smooth Scroll:** Lenis

## Setup

```bash
# Clone the repo
git clone https://github.com/rahulravindran61/house-of-ambava.git
cd house-of-ambava

# Create virtual environment
python -m venv env
source env/bin/activate   # Linux/Mac
env\Scripts\activate      # Windows

# Install dependencies
pip install django pillow requests

# Run migrations
python manage.py migrate

# Create superuser (admin)
python manage.py createsuperuser

# Populate products
python populate_shop.py

# Run the server
python manage.py runserver
```

## Project Structure

```
├── mysite/              # Django project settings & main views
│   ├── settings.py
│   ├── urls.py
│   ├── views.py
│   └── static/          # CSS, JS, images
├── store/               # Django app — models, admin, migrations
├── templates/           # HTML templates
├── media/               # User-uploaded content (not tracked)
└── manage.py
```
