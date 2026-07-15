from app import app, db
from models import User, Trek
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

def seed_database():
    with app.app_context():
        # Check if we already have treks so we don't accidentally add duplicates if run twice
        if Trek.query.first():
            print("Database already has treks. Skipping seed.")
            return

        print("Seeding database with staff, trekkers, and treks...")

        # 1. Add Staff
        staff_pw = generate_password_hash("staff123")
        staff1 = User(email="guide1@tma.com", password_hash=staff_pw, role="staff", name="Raju Guide", phone="9876543210", city="Manali")
        staff2 = User(email="guide2@tma.com", password_hash=staff_pw, role="staff", name="Sita Sharma", phone="9876543211", city="Dehradun")
        
        # Add to session and commit immediately so they get an ID (we need their ID for the treks)
        db.session.add_all([staff1, staff2])
        db.session.commit() 

        # 2. Add Users (Trekkers)
        trekker_pw = generate_password_hash("user123")
        user1 = User(email="trekker1@tma.com", password_hash=trekker_pw, role="trekker", name="Aarav", phone="1112223334", city="Bangalore")
        user2 = User(email="trekker2@tma.com", password_hash=trekker_pw, role="trekker", name="Riya", phone="2223334445", city="Mumbai")
        user3 = User(email="trekker3@tma.com", password_hash=trekker_pw, role="trekker", name="Joyce", phone="3334445556", city="Vijayanagar")
        db.session.add_all([user1, user2, user3])

        # 3. Add Treks (Using different dates and difficulties)
        today = datetime.utcnow()
        treks = [
            Trek(
                name="Hampta Pass Trek",
                location="Himachal Pradesh",
                difficulty="Moderate",
                duration=5,
                total_capacity=15,
                available_slots=15,
                status="Open",
                start_date=today + timedelta(days=10),
                end_date=today + timedelta(days=15),
                staff_id=staff1.id
            ),
            Trek(
                name="Kedarkantha Trek",
                location="Uttarakhand",
                difficulty="Easy",
                duration=6,
                total_capacity=20,
                available_slots=20,
                status="Open",
                start_date=today + timedelta(days=5),
                end_date=today + timedelta(days=11),
                staff_id=staff2.id
            ),
            Trek(
                name="Everest Base Camp",
                location="Nepal",
                difficulty="Hard",
                duration=14,
                total_capacity=10,
                available_slots=10,
                status="Pending",
                start_date=today + timedelta(days=30),
                end_date=today + timedelta(days=44),
                staff_id=staff1.id
            ),
            Trek(
                name="Roopkund Trek",
                location="Uttarakhand",
                difficulty="Hard",
                duration=8,
                total_capacity=12,
                available_slots=12,
                status="Closed",
                start_date=today - timedelta(days=10), # A past trek
                end_date=today - timedelta(days=2),
                staff_id=staff2.id
            )
        ]
        
        # Add all treks and commit everything
        db.session.add_all(treks)
        db.session.commit()
        
        print("Done! Data seeded successfully.")

if __name__ == "__main__":
    seed_database()
    