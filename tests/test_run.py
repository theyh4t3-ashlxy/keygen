import sys
import keygen.app
print("Before run")
app = keygen.app.VaultForgeUI()
res = app.run(sys.argv)
print("After run:", res)
