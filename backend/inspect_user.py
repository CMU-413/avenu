import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import users_collection

user = users_collection.find_one({"email": "admin@avenu.com"})
print(user)
