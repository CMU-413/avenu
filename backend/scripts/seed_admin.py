import sys
import os

# Add backend directory to path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.user_service import find_user_by_email, create_user
from errors import APIError

def seed_admin():
    email = "admin@avenu.com"
    print(f"Checking for user {email}...")
    
    user = find_user_by_email(email)
    if user:
        print(f"User {email} already exists.")
        return

    print(f"User {email} not found. Creating...")
    
    payload = {
        "optixId": 999999,
        "isAdmin": True,
        "fullname": "Admin User",
        "email": email,
        "phone": None,
        "teamIds": [],
        "notifPrefs": []
    }
    
    try:
        created = create_user(payload)
        print(f"Successfully created user: {created['email']} (ID: {created['_id']})")
    except Exception as e:
        print(f"Failed to create user: {e}")

def list_admins():
    from config import users_collection
    admins = list(users_collection.find({"isAdmin": True}))
    print("Listing all admin users:")
    for a in admins:
        print(f"- {a.get('email')} (ID: {a.get('_id')})")

if __name__ == "__main__":
    seed_admin()
    list_admins()
