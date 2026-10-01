import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app

def test_app_init():
    ui = app.VaultForgeUI()
    assert ui is not None
