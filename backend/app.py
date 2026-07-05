from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Trek, Booking
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt
from datetime import datetime
from flask_jwt_extended import get_jwt_identity
from celery import Celery
import csv
import os



app = Flask(__name__)

# Basic Config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tma.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = "I_rather_keep_it_stupid_simple-this-is-gonna-be-hard-to-crack-bcs-751751685"

# Initialize Extensions
db.init_app(app)
CORS(app)
jwt = JWTManager(app)

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
            end_date=end
        )
        
        db.session.add(new_trek)
        db.session.commit()
        return jsonify({"msg": "Trek created successfully", "id": new_trek.id}), 201
        
    except Exception as e:
        return jsonify({"msg": "Error creating trek", "error": str(e)}), 400


@app.route('/api/treks', methods=['GET'])
def get_treks():
    # Returns all treks (you can add filters here later)
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
            "status": t.status,
            "start_date": t.start_date.strftime('%Y-%m-%d'),
            "end_date": t.end_date.strftime('%Y-%m-%d')
        })
        
    return jsonify(results), 200

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    if user and check_password_hash(user.password_hash, password):
        # Bake the user's role and ID directly into the token payload
        access_token = create_access_token(
            identity=user.id, 
            additional_claims={"role": user.role, "name": user.name}
        )
        return jsonify(access_token=access_token, role=user.role, name=user.name), 200

    return jsonify({"msg": "Bad email or password"}), 401

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Check if email already exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"msg": "Email already registered"}), 400

    hashed_pw = generate_password_hash(data['password'])
    new_trekker = User(
        email=data['email'],
        password_hash=hashed_pw,
        role='trekker', # Hardcoded because only trekkers self-register
        name=data.get('name'),
        phone=data.get('phone', ''),
        city=data.get('city', '')
    )
    
    db.session.add(new_trekker)
    db.session.commit()
    
    return jsonify({"msg": "Registration successful! You can now log in."}), 201

@app.route('/api/book/<int:trek_id>', methods=['POST'])
@jwt_required()
def book_trek(trek_id):
    user_id = get_jwt_identity()
    trek = Trek.query.get(trek_id)
    
    if not trek or trek.available_slots <= 0:
        return jsonify({"msg": "Trek full or not found"}), 400
        
    # Check for duplicate booking
    existing = Booking.query.filter_by(user_id=user_id, trek_id=trek_id).first()
    if existing:
        return jsonify({"msg": "You already booked this"}), 400
        
    trek.available_slots -= 1
    new_booking = Booking(user_id=user_id, trek_id=trek_id)
    db.session.add(new_booking)
    db.session.commit()
    
    return jsonify({"msg": "Successfully booked!"}), 200

# --- CELERY CONFIG ---
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

def make_celery(app):
    celery = Celery(app.import_name, broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = make_celery(app)


# --- ASYNC TASKS ---

@celery.task
def export_bookings_csv(user_id):
    # Ensure exports folder exists
    if not os.path.exists('exports'):
        os.makedirs('exports')
        
    bookings = Booking.query.filter_by(user_id=user_id).all()
    filename = f"exports/user_{user_id}_history.csv"
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Booking ID', 'Trek ID', 'Date', 'Status'])
        for b in bookings:
            writer.writerow([b.id, b.trek_id, b.booking_date.strftime('%Y-%m-%d'), b.status])
            
    return filename

@app.route('/api/export', methods=['POST'])
@jwt_required()
def trigger_export():
    user_id = get_jwt_identity()
    # .delay() pushes it to the Redis queue instead of locking up the server
    task = export_bookings_csv.delay(user_id)
    return jsonify({"msg": "Export started", "task_id": task.id}), 202

if __name__ == '__main__':
    setup_database()
    app.run(debug=True)