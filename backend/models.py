from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'admin', 'staff', 'trekker'
    
    # Profile Info (Derived from wireframes)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20)) 
    city = db.Column(db.String(50))
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Bi-directional relationships for clean API queries
    bookings = db.relationship('Booking', backref='trekker', lazy=True, cascade="all, delete-orphan")
    assigned_treks = db.relationship('Trek', backref='staff', lazy=True)

class Trek(db.Model):
    __tablename__ = 'trek'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False) # Easy, Moderate, Hard
    duration = db.Column(db.Integer, nullable=False)
    
    # Capacity Management
    total_capacity = db.Column(db.Integer, nullable=False) 
    available_slots = db.Column(db.Integer, nullable=False)
    
    status = db.Column(db.String(20), default='Pending') # Approved, Open, Closed, Completed
    
    # Use DateTime for Celery job filtering
    start_date = db.Column(db.DateTime, nullable=False) 
    end_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    staff_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    bookings = db.relationship('Booking', backref='trek', lazy=True, cascade="all, delete-orphan")

class Booking(db.Model):
    __tablename__ = 'booking'
    id = db.Column(db.Integer, primary_key=True)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    status = db.Column(db.String(20), default='Booked') # Cancelled, Completed
    payment_status = db.Column(db.String(20), default='Pending') # Mentioned in doc as optional
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    trek_id = db.Column(db.Integer, db.ForeignKey('trek.id'), nullable=False)
    
    # First Principles: Enforce duplicate prevention at the DB layer
    __table_args__ = (
        db.UniqueConstraint('user_id', 'trek_id', name='unique_user_trek_booking'),
    )