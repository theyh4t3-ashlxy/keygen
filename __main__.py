import sys
import signal
try:
    from .app import VaultForgeUI
except (ImportError, ValueError):
    from app import VaultForgeUI

def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = VaultForgeUI()
    try:
        sys.exit(app.run(sys.argv))
    except KeyboardInterrupt:
        sys.exit(130)

if __name__ == "__main__":
    main()

