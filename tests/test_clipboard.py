import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk, Adw
Adw.init()
cb = Gdk.Display.get_default().get_clipboard()
try:
    cb.set("hello")
    print("set() works")
except Exception as e:
    print(f"set() failed: {e}")
try:
    cb.set_text("hello")
    print("set_text() works")
except Exception as e:
    print(f"set_text() failed: {e}")
