from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect          # NEW: CSRF protection
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
import os
import re                                      # NEW: for email validation
from flask_mail import Mail, Message


load_dotenv()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///agha_brothers.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Email settings (set these in your .env file)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'          # for Gmail
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'info@aghabrothers.com')

mail = Mail(app)

def send_contact_email(name, email, phone, subject, message):
    try:
        msg = Message(f'New Contact: {subject}',
                      recipients=['shayanshahbaz96@gmail.com'])  # 🔁 change to your email
        msg.body = f"""
Name: {name}
Email: {email}
Phone: {phone or 'Not provided'}
Subject: {subject or 'No subject'}
Message:
{message}
"""
        mail.send(msg)
    except Exception as e:
        print(f"Contact email error: {e}")

def send_order_email(order):
    try:
        customer = order.customer
        items = '\n'.join([f"  • {item.product.name} x{item.quantity} = PKR {item.unit_price * item.quantity}" for item in order.items])
        msg = Message(f'New Order #{order.id}',
                      recipients=['shayanshahbaz96@gmail.com'])  # 🔁 change to your email
        msg.body = f"""
Order #{order.id}
Customer: {customer.name} ({customer.email})
Phone: {customer.phone or 'Not provided'}
Address: {order.shipping_address}
Total: PKR {order.total_amount}

Items:
{items}

Notes: {order.notes or 'None'}
"""
        mail.send(msg)
    except Exception as e:
        print(f"Order email error: {e}")
# NEW: Enable CSRF protection
csrf = CSRFProtect(app)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# ── MODELS ────────────────────────────────────────────────────────────────────

class User(db.Model, UserMixin):
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    phone      = db.Column(db.String(20))
    address    = db.Column(db.Text)
    password   = db.Column(db.String(200), nullable=False)
    is_admin   = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders     = db.relationship('Order', backref='customer', lazy=True)

class Category(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(100), nullable=False)
    icon     = db.Column(db.String(50), default='fa-bolt')
    products = db.relationship('Product', backref='category', lazy=True)

class Product(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price       = db.Column(db.Float, nullable=False)
    stock       = db.Column(db.Integer, default=0)
    brand       = db.Column(db.String(100))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    image_url   = db.Column(db.String(500))
    sku         = db.Column(db.String(50), unique=True)
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, db.ForeignKey('user.id'))
    status           = db.Column(db.String(50), default='Pending')
    total_amount     = db.Column(db.Float)
    shipping_address = db.Column(db.Text)
    notes            = db.Column(db.Text)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow)
    items            = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    order_id   = db.Column(db.Integer, db.ForeignKey('order.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity   = db.Column(db.Integer)
    unit_price = db.Column(db.Float)
    product    = db.relationship('Product')

class CartItem(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity   = db.Column(db.Integer, default=1)
    product    = db.relationship('Product')

class Contact(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(120), nullable=False)
    phone      = db.Column(db.String(20))
    subject    = db.Column(db.String(200))
    message    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))

@app.template_filter('cart_count')
def cart_count_filter(user_id):
    return CartItem.query.filter_by(user_id=user_id).count()

# ── SEED DATA ─────────────────────────────────────────────────────────────────

def seed():
    if Category.query.count():
        return

    cats = [
        Category(name='Circuit Breakers',     icon='fa-bolt'),
        Category(name='Cables & Wires',       icon='fa-plug'),
        Category(name='Switchgear',           icon='fa-toggle-on'),
        Category(name='Motors & Drives',      icon='fa-cog'),
        Category(name='Lighting Solutions',   icon='fa-lightbulb'),
        Category(name='Power Distribution',   icon='fa-sitemap'),
        Category(name='Automation & PLCs',    icon='fa-robot'),
        Category(name='Protection Relays',    icon='fa-shield-alt'),
        Category(name='Sockets & Switches',   icon='fa-power-off'),
        Category(name='Earthing & Safety',    icon='fa-exclamation-triangle'),
    ]
    db.session.add_all(cats)
    db.session.commit()

    wire_img = '/static/images/prod_wire.png'
    mcb_img  = '/static/images/prod_mcb.png'

    products = [
        # ── Circuit Breakers ──
        Product(name='Schneider iC60N 4-Pole 63A MCB', description='4-pole miniature circuit breaker, 63A, 6kA breaking capacity, Curve C. DIN rail mount. IEC 60898-1 certified. Ideal for commercial panels.', price=4200, stock=85, brand='Schneider Electric', category_id=1, image_url=mcb_img, sku='SCH-IC60N-4P-63A'),
        Product(name='Schneider iC60N 2-Pole 32A MCB', description='2-pole MCB 32A, 6kA, Curve C. Compact design for residential distribution boards. Easy installation on DIN rail.', price=1800, stock=150, brand='Schneider Electric', category_id=1, image_url=mcb_img, sku='SCH-IC60N-2P-32A'),
        Product(name='Siemens 5SL6 1-Pole 16A MCB',   description='Single pole MCB 16A, Type B, 6kA. For lighting and socket circuits in homes and offices. DIN rail mounted.', price=750,  stock=200, brand='Siemens',            category_id=1, image_url='https://images.unsplash.com/photo-1621905252507-b35492cc74b4?w=500&q=80', sku='SIE-5SL6-1P-16A'),
        Product(name='GE THED 3-Pole 100A MCCB',      description='Molded Case Circuit Breaker 100A, 3-pole, 65kA. Thermal-magnetic trip. For industrial panel protection.', price=14500, stock=22, brand='GE',               category_id=1, image_url='https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=500&q=80', sku='GE-THED-3P-100A'),
        Product(name='Siemens SENTRON 3WL 1600A ACB',  description='Air Circuit Breaker 1600A, 3-pole, Icu=85kA. Electronic trip unit. Full protection (L/S/I/G). SENTRON series.', price=285000, stock=4, brand='Siemens',   category_id=1, image_url='https://images.unsplash.com/photo-1581092580497-e0d23cbdffd?w=500&q=80', sku='SIE-3WL-1600A'),

        # ── Cables & Wires ──
        Product(name='Copper Flexible Wire 2.5mm² (100m Roll)', description='2.5mm² single core flexible copper wire, PVC insulated. 100m roll. Suitable for domestic and light commercial wiring. Available in red, black, green.', price=3800, stock=120, brand='Pakistan Cables', category_id=2, image_url=wire_img, sku='PAK-CU-2.5-100M'),
        Product(name='Copper Wire 4mm² Single Core (100m)',      description='4mm² solid copper conductor, PVC insulation. 100m roll. For sub-mains and final circuits. Heat resistant up to 70°C.', price=6200, stock=80,  brand='Pakistan Cables', category_id=2, image_url=wire_img, sku='PAK-CU-4-100M'),
        Product(name='Armoured Cable 3-Core 6mm² (50m)',         description='3-core SWA armoured cable, 6mm² copper, XLPE insulated, PVC sheathed. 50m drum. For underground and outdoor installations.', price=18500, stock=30, brand='Azmat Cables', category_id=2, image_url=wire_img, sku='AZM-SWA-3C-6-50M'),
        Product(name='Multicore Control Cable 1.5mm² 12C (per m)', description='12-core control cable, 1.5mm² copper, PVC insulated and sheathed. Per metre. For instrumentation and panel wiring.', price=180, stock=600,  brand='Azmat Cables', category_id=2, image_url=wire_img, sku='AZM-CC-12C-1.5M'),
        Product(name='Twin & Earth Cable 2.5mm² (100m)',          description='2.5mm² Twin & Earth flat cable, PVC insulated. 100m roll. Standard for UK/Pakistan wiring regulations. For power circuits.', price=5500, stock=90, brand='Pakistan Cables', category_id=2, image_url=wire_img, sku='PAK-T&E-2.5-100M'),

        # ── Switchgear ──
        Product(name='Schneider NSX160B 3P 160A MCCB', description='Compact NSX 160A, 3-pole, 25kA. Micrologic 2.2 trip unit (LI). For industrial panels. Plug-in ready.', price=22000, stock=18, brand='Schneider Electric', category_id=3, image_url='https://images.unsplash.com/photo-1581092580497-e0d23cbdffd?w=500&q=80', sku='SCH-NSX160B'),
        Product(name='GE 400A 3-Pole Switch Disconnector', description='400A 3-pole switch disconnector, IP65 rated. Load break switch for main incomer. Suitable for outdoor use.', price=17500, stock=12, brand='GE', category_id=3, image_url='https://images.unsplash.com/photo-1560472354-b33ff0c44a43?w=500&q=80', sku='GE-SD-400A'),
        Product(name='Siemens 3RT Contactor 32A', description='Siemens 3RT2026 contactor 32A, 3-pole, 230V AC coil. For motor starting and industrial control applications.', price=3200, stock=45, brand='Siemens', category_id=3, image_url='https://images.unsplash.com/photo-1518770660439-4636190af475?w=500&q=80', sku='SIE-3RT-32A'),

        # ── Motors & Drives ──
        Product(name='Siemens SIMOTICS 7.5kW IE3 Motor',  description='7.5kW IE3 efficiency 3-phase induction motor. 4-pole, 1450 RPM, Frame 132S. B3 foot mounting. IP55. F class insulation.', price=45000, stock=8, brand='Siemens', category_id=4, image_url='https://images.unsplash.com/photo-1581092335397-9583eb92d232?w=500&q=80', sku='SIE-MOT-7.5KW'),
        Product(name='Schneider ATV320 VFD 11kW 3-Phase', description='Variable Frequency Drive 11kW, 400V 3-phase input/output. IP20. Built-in EMC filter. Modbus RTU. For pump and fan control.', price=55000, stock=6, brand='Schneider Electric', category_id=4, image_url='https://images.unsplash.com/photo-1581092580497-e0d23cbdffd?w=500&q=80', sku='SCH-ATV320-11KW'),

        # ── Lighting ──
        Product(name='LED High Bay Light 100W IP65', description='100W LED High Bay, 5000K daylight, 12000 lumens. IP65 waterproof. Die-cast aluminium. For warehouses, factories, garages.', price=4500, stock=60, brand='Philips', category_id=5, image_url='https://images.unsplash.com/photo-1524484485831-a92ffc0de03f?w=500&q=80', sku='PHI-HB-100W'),
        Product(name='LED Floodlight 200W Outdoor', description='200W LED Floodlight, 6500K, 20000lm. IP66, IK08. Die-cast aluminium housing. For construction sites and outdoor areas.', price=7200, stock=40, brand='Philips', category_id=5, image_url='https://images.unsplash.com/photo-1524484485831-a92ffc0de03f?w=500&q=80', sku='PHI-FL-200W'),

        # ── Power Distribution ──
        Product(name='Schneider PRISMA G 12-Way 3Ph DB', description='12-way 3-phase distribution board, 125A busbar, IP31, DIN rail fitted, transparent door with lock. For commercial buildings.', price=11500, stock=20, brand='Schneider Electric', category_id=6, image_url='https://images.unsplash.com/photo-1545259742-89e4905c3b86?w=500&q=80', sku='SCH-PRIS-12W'),
        Product(name='Busbar Trunking 400A Aluminium (per m)', description='400A aluminium busbar trunking system. IP55. Joint units available. Tap-off boxes at 1m intervals. For main distribution.', price=8500, stock=50, brand='Siemens', category_id=6, image_url='https://images.unsplash.com/photo-1560472354-b33ff0c44a43?w=500&q=80', sku='SIE-BBT-400A-1M'),

        # ── Automation ──
        Product(name='Siemens SIMATIC S7-1200 CPU 1214C PLC', description='S7-1200 PLC, CPU 1214C DC/DC/DC. 14DI/10DO/2AI. 100KB work memory. PROFINET port. For industrial automation projects.', price=32000, stock=10, brand='Siemens', category_id=7, image_url='https://images.unsplash.com/photo-1518770660439-4636190af475?w=500&q=80', sku='SIE-S7-1214C'),
        Product(name='Schneider Modicon M221 PLC 16 I/O', description='M221 compact PLC, 16 I/O (9DI+7DO), 24VDC. Ethernet + serial. EcoStruxure Machine Expert Basic. For small machines.', price=17500, stock=15, brand='Schneider Electric', category_id=7, image_url='https://images.unsplash.com/photo-1518770660439-4636190af475?w=500&q=80', sku='SCH-M221-16IO'),

        # ── Protection Relays ──
        Product(name='Schneider Sepam Series 20 Protection Relay', description='Sepam S20 protection relay. ANSI 50/51/50N/51N overcurrent functions. For MV transformers and feeders. RS485 Modbus.', price=27500, stock=9, brand='Schneider Electric', category_id=8, image_url='https://images.unsplash.com/photo-1581092580497-e0d23cbdffd?w=500&q=80', sku='SCH-SEP20'),
        Product(name='Siemens 7SJ85 Overcurrent Relay',            description='SIPROTEC 5 overcurrent relay 7SJ85. Comprehensive protection for distribution feeders. IEC 61850, GOOSE messaging.', price=45000, stock=5, brand='Siemens', category_id=8, image_url='https://images.unsplash.com/photo-1560472354-b33ff0c44a43?w=500&q=80', sku='SIE-7SJ85'),

        # ── Sockets & Switches ──
        Product(name='Legrand Belanko 13A Single Socket',      description='13A switched single socket outlet, white. BS1363 standard. Includes safety shutters. Screwless terminal connections.', price=320, stock=300, brand='Legrand', category_id=9, image_url='https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?w=500&q=80', sku='LEG-BEL-SS-13A'),
        Product(name='Legrand Belanko 20A Double Pole Switch', description='20A double pole switch for water heaters and AC units. Surface/flush mount. IP2X. White finish. UK standard.', price=480, stock=200, brand='Legrand', category_id=9, image_url='https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?w=500&q=80', sku='LEG-BEL-DPS-20A'),

        # ── Earthing & Safety ──
        Product(name='Copper Earth Rod 1.2m x 14mm',           description='14mm dia solid copper earth rod, 1.2m length. For grounding systems. Includes stainless steel driving head and coupler.', price=850, stock=150, brand='Generic', category_id=10, image_url='https://images.unsplash.com/photo-1621905252507-b35492cc74b4?w=500&q=80', sku='GEN-ER-14-1.2M'),
        Product(name='RCD 63A 30mA 2-Pole Residual Current Device', description='63A 2-pole RCD, 30mA sensitivity, Type A. For personal protection in residential and commercial installations. DIN rail.', price=2200, stock=80, brand='Schneider Electric', category_id=10, image_url=mcb_img, sku='SCH-RCD-63A-30MA'),
    ]
    db.session.add_all(products)

    # NEW: Warn about default admin password
    admin = User(
        name='Admin',
        email='admin@aghabrothers.com',
        phone='0300-1234567',
        password=bcrypt.generate_password_hash('admin123').decode('utf-8'),
        is_admin=True
    )
    db.session.add(admin)
    db.session.commit()
    print("✅ Database seeded. **IMPORTANT:** Change the default admin password immediately!")

# ── DECORATORS ────────────────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated

# ── PUBLIC ROUTES ─────────────────────────────────────────────────────────────

@app.route('/')
def home():
    featured   = Product.query.filter_by(is_active=True).order_by(Product.id.desc()).limit(8).all()
    categories = Category.query.all()
    return render_template('home.html', featured=featured, categories=categories)

@app.route('/products')
def products():
    cat_id  = request.args.get('category', type=int)
    brand   = request.args.get('brand', '')
    search  = request.args.get('q', '')
    page    = request.args.get('page', 1, type=int)
    q       = Product.query.filter_by(is_active=True)
    if cat_id: q = q.filter_by(category_id=cat_id)
    if brand:  q = q.filter_by(brand=brand)
    if search: q = q.filter(Product.name.ilike(f'%{search}%'))
    prods  = q.paginate(page=page, per_page=12)
    cats   = Category.query.all()
    brands = ['Schneider Electric','Siemens','GE','Azmat Cables','Pakistan Cables','Philips','Legrand']
    return render_template('products.html', products=prods, categories=cats, brands=brands,
                           selected_cat=cat_id, selected_brand=brand, search=search)

@app.route('/product/<int:id>')
def product_detail(id):
    p       = Product.query.get_or_404(id)
    related = Product.query.filter_by(category_id=p.category_id, is_active=True).filter(Product.id != id).limit(4).all()
    return render_template('product_detail.html', product=p, related=related)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name    = request.form.get('name', '').strip()
        email   = request.form.get('email', '').strip()
        phone   = request.form.get('phone', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()

        if not name or not email or not message:
            flash('Please fill in all required fields.', 'danger')
            return redirect(url_for('contact'))

        # Save to database
        new_msg = Contact(name=name, email=email, phone=phone, subject=subject, message=message)
        db.session.add(new_msg)
        db.session.commit()

        # Send email notification (see section 2)
        send_contact_email(name, email, phone, subject, message)

        flash('✅ Thank you! We will contact you within 24 hours.', 'success')
        return redirect(url_for('contact'))

    return render_template('contact.html')

# ── AUTH ──────────────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET','POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('home'))
    if request.method == 'POST':
        # NEW: Email validation
        email = request.form['email'].strip()
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            flash('Invalid email address.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered.','danger')
            return redirect(url_for('register'))

        # NEW: Password strength check
        password = request.form['password']
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return redirect(url_for('register'))

        u = User(
            name=request.form['name'].strip(),
            email=email,
            phone=request.form.get('phone',''),
            address=request.form.get('address',''),
            password=bcrypt.generate_password_hash(password).decode('utf-8')
        )
        db.session.add(u); db.session.commit()
        flash('Account created! Please log in.','success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('home'))
    if request.method == 'POST':
        u = User.query.filter_by(email=request.form['email']).first()
        if u and bcrypt.check_password_hash(u.password, request.form['password']):
            login_user(u)
            return redirect(url_for('admin_dashboard') if u.is_admin else url_for('home'))
        flash('Invalid email or password.','danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user(); return redirect(url_for('home'))

# ── CART ──────────────────────────────────────────────────────────────────────

@app.route('/cart')
@login_required
def cart():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(i.product.price * i.quantity for i in items)
    return render_template('cart.html', items=items, total=total)

@app.route('/cart/add/<int:pid>', methods=['POST'])
@login_required
def add_to_cart(pid):
    qty  = int(request.form.get('quantity', 1))
    item = CartItem.query.filter_by(user_id=current_user.id, product_id=pid).first()
    if item: item.quantity += qty
    else:    db.session.add(CartItem(user_id=current_user.id, product_id=pid, quantity=qty))
    db.session.commit()
    flash('Added to cart!','success')
    return redirect(request.referrer or url_for('products'))

@app.route('/cart/update/<int:iid>', methods=['POST'])
@login_required
def update_cart(iid):
    item = CartItem.query.get_or_404(iid)

    if item.user_id != current_user.id:
        abort(403)

    qty = int(request.form.get('quantity',1))

    if qty <= 0:
        db.session.delete(item)
    else:
        item.quantity = qty

    db.session.commit()
    return redirect(url_for('cart'))

@app.route('/cart/remove/<int:iid>', methods=['POST'])   # ✅ Added methods
@login_required
def remove_from_cart(iid):
    item = CartItem.query.get_or_404(iid)

    if item.user_id != current_user.id:
        abort(403)

    db.session.delete(item)
    db.session.commit()

    return redirect(url_for('cart'))

# ── ORDERS ────────────────────────────────────────────────────────────────────

@app.route('/checkout', methods=['GET','POST'])
@login_required
def checkout():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not items: flash('Cart is empty.','warning'); return redirect(url_for('cart'))
    total = sum(i.product.price * i.quantity for i in items)
    if request.method == 'POST':
        order = Order(user_id=current_user.id, total_amount=total,
                      shipping_address=request.form['address'],
                      notes=request.form.get('notes',''))
        db.session.add(order); db.session.flush()
        for i in items:
            db.session.add(OrderItem(order_id=order.id, product_id=i.product_id,
                                     quantity=i.quantity, unit_price=i.product.price))
            i.product.stock = max(0, i.product.stock - i.quantity)
            db.session.delete(i)
        db.session.commit()
        send_order_email(order)
        flash(f'Order #{order.id} placed successfully! We will confirm shortly.','success')
        return redirect(url_for('my_orders'))
    return render_template('checkout.html', items=items, total=total)

@app.route('/my-orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('my_orders.html', orders=orders)

@app.route('/order/<int:id>')
@login_required
def order_detail(id):
    order = Order.query.get_or_404(id)
    if order.user_id != current_user.id and not current_user.is_admin:
        flash('Access denied.','danger'); return redirect(url_for('home'))
    return render_template('order_detail.html', order=order)

@app.route('/profile', methods=['GET','POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.name    = request.form['name']
        current_user.phone   = request.form.get('phone','')
        current_user.address = request.form.get('address','')
        db.session.commit(); flash('Profile updated!','success')
    return render_template('profile.html')

# ── CHATBOT ───────────────────────────────────────────────────────────────────
@csrf.exempt   # <-- this line is essential
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'response': 'Please ask a question.'}), 400
    msg = data['message'].lower()
    return jsonify({'response': get_bot_response(msg)})

def get_bot_response(msg):
    msg = msg.lower()
    
    # Keywords detection
    greet   = any(w in msg for w in ['hello','hi','hey','salam','assalam','good morning','good evening'])
    price   = any(w in msg for w in ['price','cost','rate','how much','kitna','dam'])
    cable   = any(w in msg for w in ['cable','wire','azmat','pakistan cable','copper'])
    breaker = any(w in msg for w in ['breaker','mcb','mccb','circuit','acb','rcd'])
    schneider = 'schneider' in msg
    siemens   = 'siemens' in msg
    order   = any(w in msg for w in ['order','buy','purchase','kharidna','checkout'])
    delivery= any(w in msg for w in ['delivery','shipping','deliver','courier'])
    motor   = any(w in msg for w in ['motor','drive','vfd','inverter'])
    plc     = any(w in msg for w in ['plc','automation','simatic','modicon','s7'])
    contact = any(w in msg for w in ['contact','phone','email','address','location','where'])
    light   = any(w in msg for w in ['light','led','bulb','flood','highbay','lumen'])
    switchg = any(w in msg for w in ['switchgear','contactor','panel','mcc','distribution'])
    warranty= any(w in msg for w in ['warranty','guarantee','return'])
    thanks  = any(w in msg for w in ['thank','thanks','shukriya','jazak'])
    track   = any(w in msg for w in ['track','status','where is my','my order'])

    if greet:
        return ("👋 As-salamu alaykum! Welcome to <strong>Agha Brothers Electrical Parts & Solutions</strong>!\n\n"
                "I'm your virtual assistant. I can help you with:\n"
                "• Product information & prices\n• Order placement & tracking\n"
                "• Brand information\n• Delivery details\n\nHow can I help you today? ⚡")
    if track:
        return ("📦 To track your order:\n1. Log in to your account\n2. Click <strong>My Orders</strong> in the navigation\n"
                "3. You'll see real-time status: Pending → Confirmed → Processing → Shipped → Delivered\n\n"
                "Need help logging in? Just ask!")
    if price:
        return ("💰 Our prices are very competitive! Some examples:\n"
                "• MCBs from <strong>PKR 750</strong>\n• Copper Wire from <strong>PKR 180/m</strong>\n"
                "• LED High Bay from <strong>PKR 4,500</strong>\n• PLCs from <strong>PKR 17,500</strong>\n\n"
                "Visit our <strong>Products</strong> page for full pricing. Bulk discounts available — call us!")
    if cable:
        return ("🔌 We stock a wide range of cables:\n"
                "• <strong>Pakistan Cables</strong> – 2.5mm², 4mm², 6mm² copper wire (100m rolls)\n"
                "• <strong>Azmat Cables</strong> – SWA armoured, control cables, multicore\n"
                "• Twin & Earth, flexible, single core available\n\n"
                "All cables are certified and Pakistan Standards compliant!")
    if breaker:
        return ("⚡ Our circuit breaker range:\n"
                "• <strong>MCBs</strong>: Schneider iC60N (6A–63A), Siemens 5SL6\n"
                "• <strong>MCCBs</strong>: GE THED (100A), Schneider NSX (160A–630A)\n"
                "• <strong>ACBs</strong>: Siemens SENTRON 3WL (up to 6300A)\n"
                "• <strong>RCDs</strong>: 30mA, 100mA, 300mA\n\n"
                "All genuine manufacturer products with warranty!")
    if schneider:
        return ("🟢 <strong>Schneider Electric</strong> products we stock:\n"
                "• iC60N / Easy9 MCBs\n• Compact NSX MCCBs\n"
                "• ATV320/630 Variable Frequency Drives\n• Modicon M221/M241 PLCs\n"
                "• PRISMA distribution boards\n• Sepam protection relays\n\n"
                "Authorised Schneider dealer. All products genuine & warranted!")
    if siemens:
        return ("🔵 <strong>Siemens</strong> products we stock:\n"
                "• 5SL6 MCBs & SENTRON ACBs\n• SIMOTICS motors (IE3)\n"
                "• SIMATIC S7-1200/1500 PLCs\n• SIPROTEC protection relays\n"
                "• Busbar trunking systems\n\n"
                "Authorised Siemens partner. Genuine products with full warranty!")
    if motor:
        return ("⚙️ Our motor & drive selection:\n"
                "• <strong>Siemens SIMOTICS</strong> IE3 motors – 0.37kW to 355kW\n"
                "• <strong>Schneider ATV320</strong> VFDs – 0.18kW to 15kW\n"
                "• <strong>Schneider ATV630</strong> VFDs – 11kW to 630kW\n\n"
                "We also help with motor sizing and drive selection. Contact our engineers!")
    if plc:
        return ("🤖 Our automation products:\n"
                "• <strong>Siemens S7-1200</strong> (CPU 1211C to 1217C)\n"
                "• <strong>Siemens S7-1500</strong> (high-end)\n"
                "• <strong>Schneider Modicon M221/M241/M251</strong>\n\n"
                "We also offer basic PLC programming support. Interested in a project?")
    if light:
        return ("💡 Our lighting solutions:\n"
                "• <strong>LED High Bay</strong> – 100W, 150W, 200W (IP65)\n"
                "• <strong>LED Floodlights</strong> – 100W to 400W (IP66)\n"
                "• <strong>LED Street Lights</strong> – 50W to 200W\n\n"
                "All energy-efficient, 3-5 year warranty. Huge savings vs fluorescent!")
    if switchg:
        return ("🏭 Switchgear & panel products:\n"
                "• Contactors: Siemens 3RT, Schneider TeSys\n"
                "• Distribution boards: Schneider PRISMA, GE\n"
                "• Busbar trunking up to 6300A\n"
                "• Complete MCC panel building service available!\n\nCall us for a quote.")
    if delivery:
        return ("🚚 Delivery information:\n"
                "• <strong>Lahore</strong>: Same day or next day\n"
                "• <strong>Major cities</strong> (Karachi, Islamabad, Faisalabad): 2-3 days\n"
                "• <strong>Other areas</strong>: 3-5 working days via TCS/Leopards\n\n"
                "Free delivery on orders above <strong>PKR 25,000</strong>!")
    if order:
        return ("🛒 How to place an order:\n"
                "1. <strong>Create an account</strong> or log in\n"
                "2. Browse products and click <strong>Add to Cart</strong>\n"
                "3. Go to <strong>Cart</strong> → Proceed to Checkout\n"
                "4. Enter your delivery address → <strong>Place Order</strong>\n\n"
                "Payment: Cash on Delivery (COD). We confirm within 2 hours!")
    if contact:
        return ("📍 <strong>Agha Brothers Electrical Parts & Solutions</strong>\n"
                "📍 Lahore, Punjab, Pakistan\n"
                "📞 +92-300-1234567\n"
                "📧 info@aghabrothers.com\n"
                "🕐 Monday–Saturday: 9:00 AM – 7:00 PM\n\n"
                "WhatsApp available on the same number!")
    if warranty:
        return ("🛡️ Warranty policy:\n"
                "• Siemens: <strong>2 years</strong>\n• Schneider Electric: <strong>2 years</strong>\n"
                "• GE: <strong>1 year</strong>\n• Cables: <strong>1 year</strong>\n• Lighting: <strong>2-3 years</strong>\n\n"
                "Keep your invoice as proof of purchase. We handle all warranty claims!")
    if thanks:
        return "You're welcome! It's our pleasure. Agha Brothers — <strong>Electrical Parts & Solutions</strong>! ⚡ Feel free to ask anything anytime."

    # 👇 FALLBACK – this is the crucial line that returns a response for any unrecognized message
    return ("I'm here to help! You can ask me about:\n"
            "⚡ <strong>Products</strong> – cables, breakers, motors, PLCs, lighting\n"
            "🏷️ <strong>Prices & brands</strong> – Schneider, Siemens, GE, Azmat\n"
            "🛒 <strong>How to order</strong>\n"
            "🚚 <strong>Delivery</strong>\n"
            "📞 <strong>Contact & location</strong>\n\n"
            "What would you like to know?")

# ── ADMIN ROUTES ──────────────────────────────────────────────────────────────

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    total_orders   = Order.query.count()
    pending        = Order.query.filter_by(status='Pending').count()
    total_products = Product.query.filter_by(is_active=True).count()
    total_users    = User.query.filter_by(is_admin=False).count()
    revenue        = db.session.query(db.func.sum(Order.total_amount)).filter_by(status='Delivered').scalar() or 0
    recent_orders  = Order.query.order_by(Order.created_at.desc()).limit(8).all()
    low_stock      = Product.query.filter(Product.stock < 10, Product.is_active==True).order_by(Product.stock).all()
    return render_template('admin/dashboard.html', total_orders=total_orders, pending=pending,
        total_products=total_products, total_users=total_users, revenue=revenue,
        recent_orders=recent_orders, low_stock=low_stock)

@app.route('/admin/orders')
@login_required
@admin_required
def admin_orders():
    status = request.args.get('status','')
    q      = Order.query
    if status: q = q.filter_by(status=status)
    orders = q.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders, status=status)

@app.route('/admin/order/<int:id>/status', methods=['POST'])
@login_required
@admin_required
def update_order_status(id):
    order = Order.query.get_or_404(id)
    order.status     = request.form['status']
    order.updated_at = datetime.utcnow()
    db.session.commit()
    flash('Order status updated.','success')
    return redirect(url_for('admin_orders'))

@app.route('/admin/products')
@login_required
@admin_required
def admin_products():
    cat_id = request.args.get('cat', type=int)
    q      = Product.query
    if cat_id: q = q.filter_by(category_id=cat_id)
    prods  = q.order_by(Product.created_at.desc()).all()
    cats   = Category.query.all()
    return render_template('admin/products.html', products=prods, categories=cats, selected_cat=cat_id)

@app.route('/admin/product/add', methods=['GET','POST'])
@login_required
@admin_required
def admin_add_product():
    cats = Category.query.all()
    if request.method == 'POST':
        p = Product(name=request.form['name'], description=request.form['description'],
                    price=float(request.form['price']), stock=int(request.form['stock']),
                    brand=request.form['brand'], category_id=int(request.form['category_id']),
                    image_url=request.form['image_url'], sku=request.form['sku'])
        db.session.add(p); db.session.commit()
        flash('Product added!','success')
        return redirect(url_for('admin_products'))
    return render_template('admin/product_form.html', categories=cats, product=None)

@app.route('/admin/product/<int:id>/edit', methods=['GET','POST'])
@login_required
@admin_required
def admin_edit_product(id):
    p    = Product.query.get_or_404(id)
    cats = Category.query.all()
    if request.method == 'POST':
        p.name=request.form['name']; p.description=request.form['description']
        p.price=float(request.form['price']); p.stock=int(request.form['stock'])
        p.brand=request.form['brand']; p.category_id=int(request.form['category_id'])
        p.image_url=request.form['image_url']; p.sku=request.form['sku']
        p.is_active='is_active' in request.form
        db.session.commit()
        flash('Product updated!','success')
        return redirect(url_for('admin_products'))
    return render_template('admin/product_form.html', categories=cats, product=p)

@app.route('/admin/product/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_product(id):
    p = Product.query.get_or_404(id)
    p.is_active = False; db.session.commit()
    flash('Product deactivated.','info')
    return redirect(url_for('admin_products'))

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/inventory')
@login_required
@admin_required
def admin_inventory():
    cat_id   = request.args.get('cat', type=int)
    search   = request.args.get('q','')
    q        = Product.query
    if cat_id:  q = q.filter_by(category_id=cat_id)
    if search:  q = q.filter(Product.name.ilike(f'%{search}%'))
    products = q.order_by(Product.stock.asc()).all()
    cats     = Category.query.all()
    return render_template('admin/inventory.html', products=products, categories=cats,
                           selected_cat=cat_id, search=search)

@app.route('/admin/inventory/update/<int:id>', methods=['POST'])
@login_required
@admin_required
def update_inventory(id):
    p = Product.query.get_or_404(id)
    p.stock = int(request.form['stock'])
    db.session.commit()
    flash(f'Stock updated for {p.name}.','success')
    return redirect(url_for('admin_inventory'))

@app.route('/admin/inventory/bulk', methods=['POST'])
@login_required
@admin_required
def bulk_update_inventory():
    data = request.get_json()
    for item in data.get('updates', []):
        p = Product.query.get(item['id'])
        if p: p.stock = int(item['stock'])
    db.session.commit()
    return jsonify({'ok': True})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed()
    # 🔥 FIX: Disable debug mode for production
    app.run(debug=False, host='0.0.0.0', port=5000)  # or use waitress/gunicorn