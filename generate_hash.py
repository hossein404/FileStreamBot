# generate_hash.py
import bcrypt
import sys

def get_password_hash(password: str) -> str:
    """Hashes the password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

if __name__ == "__main__":
    if len(sys.argv) > 1:
        password = sys.argv[1]
    else:
        try:
            password = input("Please enter the password to hash: ")
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.")
            sys.exit(0)

    if not password:
        print("Error: Password cannot be empty.")
    else:
        hashed_password = get_password_hash(password)
        print("\nPassword hashing successful!")
        print("-" * 30)
        print(f"Hashed Password: {hashed_password}")
        print("-" * 30)
        print("Please copy this hashed password and set it as the value for ADMIN_PASSWORD_HASH in your .env file.")