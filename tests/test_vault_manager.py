import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import crypto

def test_vault():
    v = crypto.VaultManager()
    assert not v.is_unlocked
    res = v.unlock("testpass123")
    assert res
    assert v.is_unlocked

    v.add_record("test", "testval", "Password")
    assert len(v.records) > 0
    assert any(r["val"] == "testval" for r in v.records)

    v.lock()
    assert not v.is_unlocked

    v2 = crypto.VaultManager()
    res2 = v2.unlock("testpass123")
    assert res2
    assert any(r["val"] == "testval" for r in v2.records)
