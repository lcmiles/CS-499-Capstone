from app import app
from models import db

with app.app_context():
    db.drop_all()
    print("Dropped all tables.")

    db.create_all()
    print("Created all tables.")
