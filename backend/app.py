from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Trek, Booking
from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab
import csv
import os
import json
import redis
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart



app = Flask(__name__)

# Basic Config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tma.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = "I_rather_keep_it_stupid_simple-this-is-gonna-be-hard-to-crack-bcs-751751685"

# Initialize Extensions
db.init_app(app)
CORS(app)
jwt = JWTManager(app)

# Initialize Redis for caching (using database 1 to keep it separate from Celery on db 0)
cache = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)

# Database Seeding: The Programmatic Admin
def setup_database():
    with app.app_context():
        db.create_all()
        # Check if admin already exists to prevent duplicate constraint errors on reboot
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            print("No admin found. Seeding default admin account...")
            hashed_pw = generate_password_hash('admin123')
            new_admin = User(
                email='admin@tma.com',
                password_hash=hashed_pw,
                role='admin',
                name='Super Admin',
                phone='0000000000',
                city='System'
            )
            db.session.add(new_admin)
            db.session.commit()
            print("Admin seeded successfully (admin@tma.com / admin123)")

# --- ROUTES ---

# --- TREK ROUTES ---

@app.route('/api/treks', methods=['POST'])
@jwt_required()
def create_trek():
    # 1. Verify the user is an Admin
    claims = get_jwt()
    if claims.get("role") != "admin":
        return jsonify({"msg": "Unauthorized. Only admins can create treks."}), 403
        
    data = request.get_json()
    
    try:
        # Convert string dates from frontend to Python DateTime objects
        start = datetime.strptime(data['start_date'], '%Y-%m-%d')
        end = datetime.strptime(data['end_date'], '%Y-%m-%d')
        
        new_trek = Trek(
            name=data['name'],
            location=data['location'],
            difficulty=data['difficulty'],
            duration=data['duration'],
            total_capacity=data['total_capacity'],
            available_slots=data['total_capacity'], # initially matches total capacity
            start_date=start,
            end_date=end,
            status='Open'
        )
        
        db.session.add(new_trek)
        db.session.commit()
        cache.delete('all_treks_v2')
        return jsonify({"msg": "Trek created successfully", "id": new_trek.id}), 201
        
    except Exception as e:
        return jsonify({"msg": "Error creating trek", "error": str(e)}), 400


@app.route('/api/treks', methods=['GET'])
def get_treks():
    # Let's change the cache key slightly to force a fresh fetch
    cached_treks = cache.get('all_treks_v2')
    if cached_treks:
        return jsonify(json.loads(cached_treks)), 200
    
    treks = Trek.query.all()
    results = []
    for t in treks:
        results.append({
            "id": t.id, 
            "name": t.name, 
            "location": t.location, 
            "difficulty": t.difficulty,
            "duration": t.duration, 
            "available_slots": t.available_slots, 
            "total_capacity": t.total_capacity, # ADDED THIS
            "staff_id": t.staff_id,             # ADDED THIS
            "status": t.status,
            "start_date": t.start_date.strftime('%Y-%m-%d'), 
            "end_date": t.end_date.strftime('%Y-%m-%d')
        })
        
    cache.setex('all_treks_v2', 60, json.dumps(results))
    
    return jsonify(results), 200

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    if user and check_password_hash(user.password_hash, password):
        if not user.is_active:
            return jsonify({"msg": "Account deactivated. Please contact support."}), 403
            
        # Bake the user's role and ID directly into the token payload
        access_token = create_access_token(
            identity=str(user.id), 
            additional_claims={"role": user.role, "name": user.name}
        )
        return jsonify(access_token=access_token, role=user.role, name=user.name, user_id=user.id), 200

    return jsonify({"msg": "Bad email or password"}), 401

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    required = ['email', 'password', 'name']
    if not data or any(f not in data or not data[f] for f in required):
        return jsonify({"msg": "Missing required fields"}), 400
        
    # Check if email already exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"msg": "Email already registered"}), 400

    hashed_pw = generate_password_hash(data['password'])
    new_trekker = User(
        email=data['email'],
        password_hash=hashed_pw,
        role='trekker', # Hardcoded because only trekkers self-register
        name=data['name'],
        phone=data.get('phone', ''),
        city=data.get('city', '')
    )
    
    db.session.add(new_trekker)
    db.session.commit()
    
    return jsonify({"msg": "Registration successful! You can now log in."}), 201

@app.route('/api/staff', methods=['POST'])
@jwt_required()
def create_staff():
    # Only Admin can create staff
    if get_jwt().get("role") != "admin":
        return jsonify({"msg": "Unauthorized"}), 403
        
    data = request.get_json()
    required = ['email', 'password', 'name']
    if not data or any(f not in data or not data[f] for f in required):
        return jsonify({"msg": "Missing required fields"}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"msg": "Email already exists"}), 400

    new_staff = User(
        email=data['email'],
        password_hash=generate_password_hash(data['password']),
        role='staff',
        name=data['name']
    )
    
    db.session.add(new_staff)
    db.session.commit()
    
    return jsonify({"msg": "Trek Staff created successfully!"}), 201

@app.route('/api/book/<int:trek_id>', methods=['POST'])
@jwt_required()
def book_trek(trek_id):
    user_id = int(get_jwt_identity())
    trek = Trek.query.get(trek_id)
    
    # Spec requirement: Only allow booking when status is "Open"
    if not trek or trek.status != 'Open' or trek.available_slots <= 0:
        return jsonify({"msg": "Trek is not Open or is full"}), 400
        
    existing = Booking.query.filter_by(user_id=user_id, trek_id=trek_id).first()
    if existing:
        return jsonify({"msg": "You already booked this"}), 400
        
    trek.available_slots -= 1
    new_booking = Booking(user_id=user_id, trek_id=trek_id)
    db.session.add(new_booking)
    db.session.commit()
    cache.delete('all_treks_v2')
    return jsonify({"msg": "Successfully booked!"}), 200

# --- ADMIN ROUTE: Get Staff List ---
@app.route('/api/staff_list', methods=['GET'])
@jwt_required()
def get_staff_list():
    if get_jwt().get("role") != "admin":
        return jsonify({"msg": "Unauthorized"}), 403
    staff = User.query.filter_by(role='staff').all()
    return jsonify([{"id": s.id, "name": s.name, "email": s.email} for s in staff]), 200

# --- ADMIN ROUTE: Assign Staff to Trek ---
@app.route('/api/treks/<int:trek_id>/assign', methods=['PUT'])
@jwt_required()
def assign_staff(trek_id):
    if get_jwt().get("role") != "admin":
        return jsonify({"msg": "Unauthorized"}), 403
        
    data = request.get_json()
    trek = Trek.query.get(trek_id)
    
    if not trek:
        return jsonify({"msg": "Trek not found"}), 404
        
    trek.staff_id = data.get('staff_id')
    db.session.commit()
    cache.delete('all_treks_v2')
    return jsonify({"msg": "Staff assigned successfully!"}), 200

# --- ADMIN ROUTE: View All Users & Staff ---
@app.route('/api/users', methods=['GET'])
@jwt_required()
def get_all_users():
    if get_jwt().get("role") != "admin":
        return jsonify({"msg": "Unauthorized"}), 403
    
    # Get everyone except the admin
    users = User.query.filter(User.role != 'admin').all()
    results = [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "is_active": u.is_active} for u in users]
    return jsonify(results), 200

# --- ADMIN ROUTE: Deactivate/Activate User ---
@app.route('/api/users/<int:user_id>/toggle', methods=['PUT'])
@jwt_required()
def toggle_user_active(user_id):
    if get_jwt().get("role") != "admin":
        return jsonify({"msg": "Unauthorized"}), 403
        
    user = User.query.get(user_id)
    if not user:
        return jsonify({"msg": "User not found"}), 404
        
    user.is_active = not user.is_active
    db.session.commit()
    
    status = "activated" if user.is_active else "deactivated"
    return jsonify({"msg": f"User {status} successfully."}), 200

# --- ADMIN ROUTE: Delete Trek ---
@app.route('/api/treks/<int:trek_id>', methods=['DELETE'])
@jwt_required()
def delete_trek(trek_id):
    if get_jwt().get("role") != "admin":
        return jsonify({"msg": "Unauthorized"}), 403
        
    trek = Trek.query.get(trek_id)
    if not trek:
        return jsonify({"msg": "Trek not found"}), 404
        
    db.session.delete(trek)
    db.session.commit()
    
    # Flush cache so deleted trek disappears instantly
    cache.delete('all_treks_v2')
    return jsonify({"msg": "Trek removed successfully."}), 200

# --- STAFF ROUTE: Manage Trek Slots & Status ---
@app.route('/api/treks/<int:trek_id>/manage', methods=['PUT'])
@jwt_required()
def manage_trek_staff(trek_id):
    if get_jwt().get("role") != "staff":
        return jsonify({"msg": "Unauthorized"}), 403
    
    trek = Trek.query.get(trek_id)
    if not trek or trek.staff_id != int(get_jwt_identity()):
        return jsonify({"msg": "Unauthorized to manage this trek"}), 403
        
    data = request.get_json()
    if 'status' in data:
        trek.status = data['status']
    if 'available_slots' in data:
        trek.available_slots = int(data['available_slots'])
        
    db.session.commit()
    cache.delete('all_treks_v2')
    return jsonify({"msg": "Trek updated successfully"}), 200

# --- STAFF/ADMIN ROUTE: View Registered Participants ---
@app.route('/api/treks/<int:trek_id>/participants', methods=['GET'])
@jwt_required()
def get_participants(trek_id):
    role = get_jwt().get("role")
    trek = Trek.query.get(trek_id)
    if not trek or (role == 'staff' and trek.staff_id != int(get_jwt_identity())):
        return jsonify({"msg": "Unauthorized"}), 403
        
    participants = [{"name": b.trekker.name, "email": b.trekker.email, "phone": b.trekker.phone, "date": b.booking_date.strftime('%Y-%m-%d')} for b in trek.bookings]
    return jsonify(participants), 200

# --- USER ROUTE: Profile Editing ---
@app.route('/api/profile', methods=['GET', 'PUT'])
@jwt_required()
def handle_profile():
    user = User.query.get(int(get_jwt_identity()))
    if not user:
        return jsonify({"msg": "User not found"}), 404
        
    if request.method == 'GET':
        return jsonify({"name": user.name, "phone": user.phone, "city": user.city}), 200
        
    data = request.get_json()
    user.name = data.get('name', user.name)
    user.phone = data.get('phone', user.phone)
    user.city = data.get('city', user.city)
    db.session.commit()
    return jsonify({"msg": "Profile updated successfully!"}), 200

# --- ADMIN ROUTE: View All Bookings ---
@app.route('/api/all_bookings', methods=['GET'])
@jwt_required()
def get_all_bookings():
    if get_jwt().get("role") != "admin":
        return jsonify({"msg": "Unauthorized"}), 403
    bookings = Booking.query.all()
    res = [{"id": b.id, "user_name": b.trekker.name, "trek_name": b.trek.name, "date": b.booking_date.strftime('%Y-%m-%d'), "status": b.status} for b in bookings]
    return jsonify(res), 200

# --- USER ROUTE: Cancel Booking ---
@app.route('/api/bookings/<int:booking_id>/cancel', methods=['PUT'])
@jwt_required()
def cancel_booking(booking_id):
    user_id = int(get_jwt_identity())
    booking = Booking.query.get(booking_id)
    
    if not booking or booking.user_id != user_id:
        return jsonify({"msg": "Booking not found or unauthorized"}), 404
        
    if booking.status == 'Cancelled':
        return jsonify({"msg": "Booking is already cancelled"}), 400
        
    # Free up the slot and update status
    booking.status = 'Cancelled'
    booking.trek.available_slots += 1
    
    db.session.commit()
    cache.delete('all_treks_v2')
    return jsonify({"msg": "Booking cancelled successfully!"}), 200

# --- USER ROUTE: Booking History ---
@app.route('/api/history', methods=['GET'])
@jwt_required()
def get_history():
    user_id = int(get_jwt_identity())
    bookings = Booking.query.filter_by(user_id=user_id).all()
    results = [{"id": b.id, "trek_name": b.trek.name, "date": b.booking_date.strftime('%Y-%m-%d'), "status": b.status} for b in bookings]
    return jsonify(results), 200

# --- ADMIN ROUTE: Statistics ---
@app.route('/api/stats', methods=['GET'])
@jwt_required()
def get_stats():
    if get_jwt().get("role") != "admin":
        return jsonify({"msg": "Unauthorized"}), 403
    return jsonify({
        "total_treks": Trek.query.count(),
        "total_users": User.query.filter_by(role='trekker').count(),
        "total_staff": User.query.filter_by(role='staff').count(),
        "total_bookings": Booking.query.count()
    }), 200

# --- CELERY CONFIG ---
app.config['broker_url'] = 'redis://localhost:6379/0'
app.config['result_backend'] = 'redis://localhost:6379/0'

def make_celery(app):
    celery = Celery(app.import_name, broker=app.config['broker_url'])
    celery.conf.update(
        broker_url=app.config['broker_url'],
        result_backend=app.config['result_backend']
    )
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = make_celery(app)

# --- CELERY BEAT SCHEDULE ---
celery.conf.timezone = 'Asia/Kolkata'

celery.conf.beat_schedule = {
    'daily-reminders': {
        'task': 'app.send_daily_reminders',
        # Runs every day at 8:00 AM
        'schedule': crontab(hour=8, minute=0), 
    },
    'monthly-activity-report': {
        'task': 'app.send_monthly_report',
        # Runs on the 1st of every month at midnight
        'schedule': crontab(day_of_month='1', hour=0, minute=0), 
    }
}

# --- EMAIL DELIVERY SCRIPT VIA MAILHOG ---
def send_email(to_email, subject, html_body):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = "admin@tma.com"
    msg['To'] = to_email
    msg.attach(MIMEText(html_body, 'html'))
    try:
        # Default local SMTP / MailHog port is 1025
        with smtplib.SMTP('localhost', 1025) as server:
            server.sendmail("admin@tma.com", to_email, msg.as_string())
    except Exception as e:
        print(f"[MAIL DELIVERY ERROR] MailHog failed to send email: {e}")

# --- SCHEDULED TASKS LOGIC ---

@celery.task(name='app.send_daily_reminders')
def send_daily_reminders():
    # Find treks starting exactly tomorrow
    tomorrow = datetime.utcnow() + timedelta(days=1)
    
    # Query database for matching treks
    treks = Trek.query.filter(db.func.date(Trek.start_date) == tomorrow.date()).all()
    
    for trek in treks:
        for booking in trek.bookings:
            body = f"""
            <html>
                <body>
                    <p>Dear {booking.trekker.name},</p>
                    <p>This is a reminder that your trek <strong>{trek.name}</strong> at {trek.location} is starting tomorrow!</p>
                    <p>Safe travels,<br>TMA Team</p>
                </body>
            </html>
            """
            send_email(booking.trekker.email, f"Trek Reminder: {trek.name} Starts Tomorrow!", body)
            print(f"[MAIL SENT] Sent reminder to {booking.trekker.email} for trek {trek.name}")
            
    return "Daily reminders processed."

@celery.task(name='app.send_monthly_report')
def send_monthly_report():
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        return "No admin user found to send report to."
        
    # Generate statistics
    total_treks = Trek.query.count()
    total_users = User.query.filter_by(role='trekker').count()
    total_bookings = Booking.query.count()
    
    # Generate HTML report
    html_content = f"""
    <html>
        <body>
            <h2>TMA Monthly Activity Report</h2>
            <p><strong>Total Treks Created:</strong> {total_treks}</p>
            <p><strong>Total Registered Trekkers:</strong> {total_users}</p>
            <p><strong>Total Bookings Processed:</strong> {total_bookings}</p>
        </body>
    </html>
    """
    
    send_email(admin.email, "TMA Monthly Activity Report", html_content)
    print(f"[MAIL SENT] Sent monthly activity report to admin at {admin.email}")
    return "Monthly report processed."


# --- ASYNC TASKS ---

@celery.task(name='app.export_bookings_csv')
def export_bookings_csv(user_id):
    # Ensure exports folder exists
    if not os.path.exists('exports'):
        os.makedirs('exports')
        
    bookings = Booking.query.filter_by(user_id=user_id).all()
    filename = f"exports/user_{user_id}_history.csv"
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        # Spec format: User ID, Trek Name, Location, Booking Status, Booking Date
        writer.writerow(['User ID', 'Trek Name', 'Location', 'Booking Status', 'Booking Date'])
        for b in bookings:
            writer.writerow([b.user_id, b.trek.name, b.trek.location, b.status, b.booking_date.strftime('%Y-%m-%d')])
            
    return filename

@app.route('/api/export', methods=['POST'])
@jwt_required()
def trigger_export():
    user_id = int(get_jwt_identity())
    # .delay() pushes it to the Redis queue instead of locking up the server
    task = export_bookings_csv.delay(user_id)
    return jsonify({"msg": "Export started", "task_id": task.id}), 202

@app.route('/api/export/status/<task_id>', methods=['GET'])
@jwt_required()
def get_export_status(task_id):
    task = export_bookings_csv.AsyncResult(task_id)
    if task.state == 'SUCCESS':
        return jsonify({"status": "SUCCESS", "file": task.result}), 200
    return jsonify({"status": task.state}), 200

@app.route('/api/download/<path:filename>', methods=['GET'])
@jwt_required()
def download_file(filename):
    # Ensure the user only downloads files from exports to prevent directory traversal
    if not filename.startswith('exports/'):
        return jsonify({"msg": "Unauthorized file access"}), 403
    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    setup_database()
    app.run(debug=True)