import sys
sys.path.append("/home/ashley/Projects")
import keygen
import pprint

print("Testing engines...")
state = keygen.VaultManager().state
for i, func in enumerate(keygen.ENGINE_FUNCS):
    try:
        res = func(state)
        print(f"Engine {i}: {res}")
    except Exception as e:
        print(f"Engine {i} FAILED: {e}")
