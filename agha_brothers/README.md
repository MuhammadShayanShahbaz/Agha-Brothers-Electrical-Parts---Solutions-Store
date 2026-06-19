# Agha Brothers – Electrical Parts & Solutions
## Complete Website User Guide

---

## SETUP (One Time Only)

### Step 1 – Install Python dependencies
```
pip install -r requirements.txt
```

### Step 2 – Run the website
```
python app.py
```

### Step 3 – Open browser
```
http://localhost:5000
```

The database is created automatically with 25 products across 10 categories on first run.

---

## ADMIN LOGIN
| Field    | Value                        |
|----------|------------------------------|
| URL      | http://localhost:5000/login  |
| Email    | admin@aghabrothers.com       |
| Password | admin123                     |

After login → auto-redirects to Admin Dashboard at /admin

---

## WEBSITE PAGES

### Customer Side
| Page         | URL              | What it does                          |
|--------------|------------------|---------------------------------------|
| Home         | /                | Hero, featured products, categories   |
| Products     | /products        | Browse all products, filter, search   |
| Product      | /product/<id>    | Full details, add to cart             |
| Cart         | /cart            | View/edit cart items                  |
| Checkout     | /checkout        | Enter address, place order            |
| My Orders    | /my-orders       | View all past orders with status      |
| Order Detail | /order/<id>      | Full order breakdown                  |
| Profile      | /profile         | Update name, phone, address           |
| About        | /about           | Company info                          |
| Contact      | /contact         | Contact form + info                   |
| Register     | /register        | Create new account                    |
| Login        | /login           | Sign in                               |

### Admin Side (login as admin first)
| Page       | URL                | What it does                              |
|------------|--------------------|-------------------------------------------|
| Dashboard  | /admin             | Stats: orders, revenue, low stock alerts  |
| Orders     | /admin/orders      | View all orders, update status            |
| Products   | /admin/products    | View/add/edit/deactivate products         |
| Inventory  | /admin/inventory   | Stock levels with visual bars, update qty |
| Customers  | /admin/users       | All registered customer accounts          |

---

## HOW TO TEST – QUICK WALKTHROUGH

1. Open http://localhost:5000
2. Click Sign Up → create a test account
3. Browse Products → click Add to Cart on any item
4. Go to Cart → click Checkout
5. Enter any delivery address → Place Order
6. Click My Orders → see your order with "Pending" status

Then as Admin:
7. Logout → Login as admin@aghabrothers.com / admin123
8. Go to Admin → Orders → change status to "Delivered"
9. Go to Inventory → update a stock number → Save
10. Go to Dashboard → see updated revenue and stats

---

## CHATBOT
- Click the blue headset icon (bottom-right corner)
- Type questions like:
  - "What cables do you have?"
  - "Schneider products"
  - "How to place an order?"
  - "Delivery info"
  - "Warranty"
  - "Contact"
- Or click the quick-reply buttons

---

## PRODUCT CATEGORIES (10 total, 25 products)
1. Circuit Breakers – Schneider iC60N, Siemens 5SL6, GE THED, Siemens SENTRON
2. Cables & Wires – Pakistan Cables, Azmat Cables (copper, armoured, control)
3. Switchgear – Schneider NSX, GE disconnectors, Siemens contactors
4. Motors & Drives – Siemens SIMOTICS motors, Schneider ATV VFDs
5. Lighting – Philips LED highbay, floodlights
6. Power Distribution – Schneider PRISMA DB, busbar trunking
7. Automation & PLCs – Siemens S7-1200, Schneider Modicon M221
8. Protection Relays – Schneider Sepam, Siemens SIPROTEC
9. Sockets & Switches – Legrand Belanko range
10. Earthing & Safety – Copper earth rods, RCDs

---

## DEPLOYMENT (Production)

Install gunicorn:
```
pip install gunicorn
gunicorn -w 4 app:app
```

Free hosting options:
- PythonAnywhere.com (easiest for beginners)
- Railway.app
- Render.com
- DigitalOcean App Platform
