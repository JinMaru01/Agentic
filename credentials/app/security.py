from cryptography.fernet import Fernet
import os

KEY = os.getenv("SECRET_KEY") or Fernet.generate_key()
cipher = Fernet(KEY)

def encrypt(text: str) -> str:
    return cipher.encrypt(text.encode()).decode()

def decrypt(text: str) -> str:
    return cipher.decrypt(text.encode()).decode()