import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import crypto
import engines

def test_engines():
    state = crypto.VaultManager().state
    for i, func in enumerate(engines.ENGINE_FUNCS):
        res, type_name, entropy = func(state)
        assert isinstance(res, str)
        assert len(res) > 0
        assert isinstance(type_name, str)
        assert len(type_name) > 0
        assert isinstance(entropy, float)
