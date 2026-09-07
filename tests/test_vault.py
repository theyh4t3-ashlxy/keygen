import sys
sys.path.append("/home/ashley/Projects")
import keygen
import os

print("Testing vault...")
v = keygen.VaultManager()
print(f"Vault unlocked? {v.is_unlocked}")
res = v.unlock("testpass123")
print(f"Unlock result: {res}")
print(f"Vault unlocked? {v.is_unlocked}")
v.add_record("test", "testval", "Password")
print(f"Records: {v.records}")
v.lock()
print(f"Locked? {not v.is_unlocked}")
v2 = keygen.VaultManager()
res2 = v2.unlock("testpass123")
print(f"Unlock 2 result: {res2}")
print(f"Records 2: {v2.records}")
