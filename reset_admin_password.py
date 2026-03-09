import sys
import os
import getpass
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to python path to ensure imports work correctly
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def main():
    print("==================================================")
    print("MaaS Admin Password Reset Rescue Script (bcrypt)")
    print("==================================================")

    try:
        import bcrypt
    except ImportError:
        print("❌ CRITICAL: 'bcrypt' library is missing in the current environment.")
        print("Please activate the correct virtual environment or install bcrypt: pip install bcrypt")
        sys.exit(1)

    try:
        from src.database import User, SessionLocal
        from src.api.users import hash_password
    except ImportError as e:
        print(f"❌ CRITICAL: Failed to import project modules: {e}")
        print("Ensure you are running this script from the project root.")
        sys.exit(1)

    db = SessionLocal()
    
    email = input("Enter admin email to reset: ").strip()
    if not email:
        print("Email cannot be empty.")
        sys.exit(1)

    user = db.query(User).filter(User.email == email).first()
    if not user:
        print(f"❌ User with email '{email}' not found in the database.")
        sys.exit(1)

    new_password = getpass.getpass("Enter new password: ")
    confirm_password = getpass.getpass("Confirm new password: ")

    if new_password != confirm_password:
        print("❌ Passwords do not match.")
        sys.exit(1)

    if len(new_password) < 8:
        print("❌ Password must be at least 8 characters long.")
        sys.exit(1)

    try:
        # Securely hash with bcrypt
        user.password_hash = hash_password(new_password)
        db.commit()
        print(f"✅ Password for {email} successfully reset and hashed via bcrypt.")
    except Exception as e:
        db.rollback()
        print(f"❌ Failed to reset password: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
