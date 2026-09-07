import sys
import time
import os
import threading
import secrets
import random
import colorsys
import json
from typing import List, Tuple, Dict, Any, Optional
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, GLib, Gio

try:
    from .constants import APP_NAME, APP_VERSION, get_css, ENGINES, TYPE_FILTERS, AUTO_LOCK_POLL_SECONDS, DEFAULT_VAULT, PALETTES
    from .engines import ENGINE_FUNCS, estimate_crack_time
    from .crypto import wipe_string, format_relative_time, HAS_CRYPTO, CRYPTO_ERR, VaultManager
except (ImportError, ValueError):
    from constants import APP_NAME, APP_VERSION, get_css, ENGINES, TYPE_FILTERS, AUTO_LOCK_POLL_SECONDS, DEFAULT_VAULT, PALETTES
    from engines import ENGINE_FUNCS, estimate_crack_time
    from crypto import wipe_string, format_relative_time, HAS_CRYPTO, CRYPTO_ERR, VaultManager

class VaultForgeUI(Adw.Application):
    def __init__(self, **kwargs) -> None:
        super().__init__(application_id="com.vaultforge.app", flags=Gio.ApplicationFlags.NON_UNIQUE, **kwargs)
        self.vault = VaultManager() if HAS_CRYPTO else None
        self.is_animating = False
        self._anim_timer = self._auto_lock_tmr = None
        self._anim_target = self._current_type = ""
        self._anim_frame = 0
        self._last_activity = time.time()
        self.bad_auth_count = 0
        self._live_accent = None
        self._history: List[Tuple[str, str, float]] = []
        self._history_idx: int = -1
        self._batch_results: List[str] = []

    def _toast(self, msg: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=msg))

    def _badge(self, text: str, css: str) -> Gtk.Label:
        lbl = Gtk.Label(label=text, valign=Gtk.Align.CENTER)
        lbl.add_css_class("badge")
        lbl.add_css_class(css)
        return lbl

    def do_activate(self) -> None:
        self.css_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._apply_theme()
        if getattr(self, 'vault', None) and self.vault.state.get("rgb_mode", False):
            self._on_rgb_toggled(None, True)
        if getattr(self, 'vault', None) and self.vault.state.get("drunk_mode", False):
            self._on_drunk_toggled(None, True)

        self.win = Adw.ApplicationWindow(application=self, title=APP_NAME, default_width=640, default_height=890)
        self.win.connect("close-request", self._on_shutdown)
        self.win.set_opacity(self.vault.state.get("ui_opacity", 1.0) if getattr(self, "vault", None) else 1.0)

        # track user activity for afk auto-lock
        for ctrl in [Gtk.EventControllerMotion.new(), Gtk.GestureClick.new()]:
            ctrl.connect("motion" if isinstance(ctrl, Gtk.EventControllerMotion) else "pressed",
                         lambda *_: setattr(self, "_last_activity", time.time()))
            self.win.add_controller(ctrl)

        key_ctrl = Gtk.EventControllerKey.new()
        key_ctrl.connect("key-pressed", self._on_window_key_pressed)
        self.win.add_controller(key_ctrl)


        self.toast_overlay = Adw.ToastOverlay()
        self.win.set_content(self.toast_overlay)

        if not HAS_CRYPTO:
            stat = Adw.StatusPage(title="no crypto module? really?", description="run pip install cryptography you absolute melon", icon_name="dialog-error-symbolic")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.append(Gtk.Label(label=CRYPTO_ERR, css_classes=["danger-label"]))
            stat.set_child(box)
            self.toast_overlay.set_child(stat)
            self.win.present()
            return

        toolbar_view = Adw.ToolbarView()
        self.app_stack = Adw.ViewStack()

        for method, tag, title, icon in [
            (self._tab_generator, "gen", "forge", "system-run-symbolic"),
            (self._tab_vault, "vault", "stash", "folder-symbolic"),
            (self._tab_settings, "settings", "under the hood", "preferences-system-symbolic")
        ]:
            self.app_stack.add_titled(method(), tag, title).set_icon_name(icon)

        self.header = Adw.HeaderBar()
        self.header.set_title_widget(Adw.ViewSwitcher(stack=self.app_stack, policy=Adw.ViewSwitcherPolicy.WIDE))

        self.btn_lock = Gtk.Button(icon_name="system-lock-screen-symbolic", tooltip_text="lock this shit down", css_classes=["flat"])
        self.btn_lock.connect("clicked", self._action_lock)
        self.header.pack_start(self.btn_lock)

        toolbar_view.add_top_bar(self.header)
        toolbar_view.set_content(self.app_stack)
        self.toast_overlay.set_child(toolbar_view)
        
        self.win.present()
        self._on_generate(None)

    def _on_window_key_pressed(self, ctrl, keyval, keycode, state) -> bool:
        self._last_activity = time.time()
        is_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        name = Gdk.keyval_name(keyval)
        if is_ctrl and name:
            if name.lower() == "r":
                self._on_generate(None)
                return True
            elif name.lower() == "c":
                focus = self.win.get_focus()
                if not isinstance(focus, (Gtk.Editable, Gtk.TextView)):
                    self._copy_val(self.lbl_output.get_label())
                    return True
            elif name.lower() == "s":
                self._on_save(None)
                return True
            elif name.lower() == "l":
                self._action_lock(None)
                return True
            elif name == "1":
                self.app_stack.set_visible_child_name("gen")
                return True
            elif name == "2":
                self.app_stack.set_visible_child_name("vault")
                return True
            elif name == "3":
                self.app_stack.set_visible_child_name("settings")
                return True
        return False

    def _on_history_prev(self, _btn) -> None:
        if self._history and self._history_idx > 0:
            self._history_idx -= 1
            res, t, ent = self._history[self._history_idx]
            self._display_result(res, t, ent, animate=False)
            self._update_history_buttons()

    def _on_history_next(self, _btn) -> None:
        if self._history and self._history_idx < len(self._history) - 1:
            self._history_idx += 1
            res, t, ent = self._history[self._history_idx]
            self._display_result(res, t, ent, animate=False)
            self._update_history_buttons()

    def _update_history_buttons(self) -> None:
        if hasattr(self, "btn_hist_prev") and hasattr(self, "btn_hist_next"):
            can_prev = self._history_idx > 0
            can_next = 0 <= self._history_idx < len(self._history) - 1
            self.btn_hist_prev.set_sensitive(can_prev)
            self.btn_hist_next.set_sensitive(can_next)

    def _on_roll_batch(self, _btn) -> None:
        count = self.vault.state.get("bulk_count", 10) if self.vault else 10
        mode = self.vault.state.get("engine_mode", 0) if self.vault else 0
        gen_fn = ENGINE_FUNCS[mode]
        items = []
        for _ in range(count):
            res, _, _ = gen_fn(self.vault.state)
            if not res.startswith("ERR"):
                items.append(res)
        self._batch_results = items
        self.bulk_buffer.set_text("\n".join(items))
        self._toast(f"hoarded {len(items)} keys.")

    def _on_copy_batch(self, _btn) -> None:
        txt = "\n".join(self._batch_results)
        if not txt:
            return self._toast("generate some batch shit first.")
        self._copy_val(txt)

    def _on_rgb_toggled(self, sw, state):
        if self.vault: self.vault.set("rgb_mode", state)
        if state:
            self._rgb_hue = 0.0
            GLib.timeout_add(100, self._rgb_tick)
        else:
            self._live_accent = None
            self._apply_theme()
        return False

    def _rgb_tick(self):
        if not getattr(self, 'vault', None) or not self.vault.state.get("rgb_mode", False):
            return False
        self._rgb_hue = (getattr(self, '_rgb_hue', 0) + 0.05) % 1.0
        r, g, b = colorsys.hsv_to_rgb(self._rgb_hue, 1.0, 1.0)
        self._live_accent = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        self._apply_theme()
        return True


    def _on_drunk_toggled(self, sw, state):
        if self.vault: self.vault.set("drunk_mode", state)
        if state:
            GLib.timeout_add(50, self._drunk_tick)
        else:
            self.lbl_output.set_margin_start(0)
            self.lbl_output.set_margin_top(0)
        return False

    def _drunk_tick(self):
        if not getattr(self, 'vault', None) or not self.vault.state.get("drunk_mode", False):
            self.lbl_output.set_margin_start(0)
            self.lbl_output.set_margin_top(0)
            return False
        self.lbl_output.set_margin_start(random.randint(0, 20))
        self.lbl_output.set_margin_top(random.randint(0, 20))
        return True

    def _apply_theme(self) -> None:
        if not hasattr(self, 'css_provider'): return
        theme_map = {0: Adw.ColorScheme.FORCE_DARK, 1: Adw.ColorScheme.FORCE_LIGHT, 2: Adw.ColorScheme.DEFAULT}
        if self.vault:
            theme_idx = self.vault.state.get("ui_theme", 0)
            font_idx = self.vault.state.get("ui_font", 0)
            accent = getattr(self, "_live_accent", None) or self.vault.state.get("ui_accent", "#ff2a5f")
            glow = self.vault.state.get("ui_glow", 8)
            rad = self.vault.state.get("ui_radius", 12)
        else:
            theme_idx, font_idx, accent, glow, rad = 0, 0, "#ff2a5f", 8, 12

        if hasattr(self, 'win') and getattr(self, 'vault', None):
            self.win.set_opacity(self.vault.state.get("ui_opacity", 1.0))
        Adw.StyleManager.get_default().set_color_scheme(theme_map.get(theme_idx, Adw.ColorScheme.FORCE_DARK))
        fonts = ["JetBrains Mono", "Fira Code", "Cascadia Code", "monospace", "Comic Sans MS"]
        font = fonts[font_idx] if 0 <= font_idx < len(fonts) else "monospace"
        
        try:
            self.css_provider.load_from_data(get_css(accent, glow, font, rad))
        except Exception as e:
            self.css_provider.load_from_data(get_css("#ff2a5f", 8, "monospace", 12))

    def _check_auto_lock(self) -> bool:
        if self.vault and self.vault.is_unlocked:
            timeout_sec = self.vault.state.get("auto_lock_mins", 3) * 60
            if time.time() - self._last_activity > timeout_sec:
                self._action_lock(None)
                self._toast("you were afk so i locked it. yw.")
        return True

    def _on_shutdown(self, *_) -> bool:
        if self.vault: self.vault.lock()
        for tid in (self._anim_timer, self._auto_lock_tmr):
            if tid: GLib.source_remove(tid)
        return False

    def _tab_generator(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()

        g_engine = Adw.PreferencesGroup(title="choose your poison")
        self.row_engine = Adw.ComboRow(title="chaos engine", model=Gtk.StringList.new(ENGINES))
        
        def _on_engine_change(combo, _):
            idx = combo.get_selected()
            self.vault.set("engine_mode", idx)
            self.gen_stack.set_visible_child_name(f"mode_{idx}")
            self._on_generate(None)

        self.row_engine.connect("notify::selected", _on_engine_change)
        g_engine.add(self.row_engine)
        page.add(g_engine)

        g_dynamic = Adw.PreferencesGroup(title="knobs &amp; dials")
        self.gen_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.gen_stack.set_vhomogeneous(False)
        self._build_engine_pages()
        g_dynamic.add(self.gen_stack)
        page.add(g_dynamic)

        self.out_grp = Adw.PreferencesGroup(title="the loot")
        out_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)

        self.lbl_output = Gtk.Label(label="...", css_classes=["key-display"], selectable=True, wrap=True, justify=Gtk.Justification.CENTER)
        out_box.append(self.lbl_output)

        ent_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.entropy_bar = Gtk.LevelBar(max_value=4)
        lbl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.entropy_lbl = Gtk.Label(label="strength: literally nothing", css_classes=["dim-label"], halign=Gtk.Align.START, hexpand=True)
        self.crack_lbl = Gtk.Label(label="crack time: 0s", css_classes=["crack-label"], halign=Gtk.Align.END)
        lbl_box.append(self.entropy_lbl)
        lbl_box.append(self.crack_lbl)
        ent_box.append(self.entropy_bar)
        ent_box.append(lbl_box)
        out_box.append(ent_box)

        action_box = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        self.btn_hist_prev = Gtk.Button(icon_name="go-previous-symbolic", tooltip_text="undo / previous roll", css_classes=["pill", "flat"])
        self.btn_hist_prev.connect("clicked", self._on_history_prev)
        self.btn_hist_prev.set_sensitive(False)

        self.btn_gen = Gtk.Button(label="reroll (ctrl+r)", icon_name="view-refresh-symbolic", css_classes=["suggested-action", "pill"])
        self.btn_gen.connect("clicked", self._on_generate)

        self.btn_hist_next = Gtk.Button(icon_name="go-next-symbolic", tooltip_text="next roll", css_classes=["pill", "flat"])
        self.btn_hist_next.connect("clicked", self._on_history_next)
        self.btn_hist_next.set_sensitive(False)

        self.btn_copy_quick = Gtk.Button(label="yoink (ctrl+c)", icon_name="edit-copy-symbolic", css_classes=["pill"])
        self.btn_copy_quick.connect("clicked", lambda _: self._copy_val(self.lbl_output.get_label()))

        action_box.append(self.btn_hist_prev)
        action_box.append(self.btn_gen)
        action_box.append(self.btn_hist_next)
        action_box.append(self.btn_copy_quick)
        out_box.append(action_box)

        self.out_grp.add(out_box)
        page.add(self.out_grp)

        bulk_grp = Adw.PreferencesGroup()
        self.exp_bulk = Adw.ExpanderRow(title="loot hoard (bulk roll)", subtitle="generate a batch of keys at once")
        
        row_bulk_spin = Adw.ActionRow(title="batch size")
        spin_bulk = Gtk.SpinButton.new_with_range(2, 50, 1)
        spin_bulk.set_value(self.vault.state.get("bulk_count", 10) if self.vault else 10)
        spin_bulk.set_valign(Gtk.Align.CENTER)
        spin_bulk.connect("value-changed", lambda s: self.vault.set("bulk_count", int(s.get_value())) if self.vault else None)
        row_bulk_spin.add_suffix(spin_bulk)
        self.exp_bulk.add_row(row_bulk_spin)

        row_bulk_acts = Adw.ActionRow()
        btn_roll_batch = Gtk.Button(label="roll batch", icon_name="view-refresh-symbolic", css_classes=["suggested-action", "pill"], valign=Gtk.Align.CENTER)
        btn_copy_batch = Gtk.Button(label="yoink all", icon_name="edit-copy-symbolic", css_classes=["pill"], valign=Gtk.Align.CENTER)
        btn_roll_batch.connect("clicked", self._on_roll_batch)
        btn_copy_batch.connect("clicked", self._on_copy_batch)
        row_bulk_acts.add_suffix(btn_roll_batch)
        row_bulk_acts.add_suffix(btn_copy_batch)
        self.exp_bulk.add_row(row_bulk_acts)

        self.bulk_buffer = Gtk.TextBuffer()
        bulk_view = Gtk.TextView(buffer=self.bulk_buffer, editable=False, wrap_mode=Gtk.WrapMode.NONE, css_classes=["bulk-mono"])
        scroll_bulk = Gtk.ScrolledWindow(min_content_height=130, max_content_height=180, vexpand=False)
        scroll_bulk.set_child(bulk_view)
        
        row_bulk_display = Adw.ActionRow()
        row_bulk_display.set_child(scroll_bulk)
        self.exp_bulk.add_row(row_bulk_display)
        bulk_grp.add(self.exp_bulk)
        page.add(bulk_grp)

        save_grp = Adw.PreferencesGroup(title="the stash")
        self.entry_label = Adw.EntryRow(title="what is this trash?")
        self.entry_tag = Adw.EntryRow(title="useless tag")
        save_grp.add(self.entry_label)
        save_grp.add(self.entry_tag)
        
        row_btn_save = Adw.ActionRow()
        self.btn_save = Gtk.Button(label="shove it in", icon_name="document-save-symbolic", css_classes=["pill", "accent"], halign=Gtk.Align.END, valign=Gtk.Align.CENTER)
        self.btn_save.connect("clicked", self._on_save)
        row_btn_save.add_suffix(self.btn_save)
        save_grp.add(row_btn_save)
        page.add(save_grp)

        return page

    def _build_engine_pages(self) -> None:
        g0 = Adw.PreferencesGroup()
        r0 = Adw.ActionRow(title="how long?")
        self.spin_pwd_len = Gtk.SpinButton.new_with_range(4, 256, 1)
        self.spin_pwd_len.set_value(self.vault.DEFAULTS["pwd_len"])
        self.spin_pwd_len.set_valign(Gtk.Align.CENTER)
        self.spin_pwd_len.connect("value-changed", lambda s: self.vault.set("pwd_len", int(s.get_value())) or self._on_generate(None))
        r0.add_suffix(self.spin_pwd_len)
        g0.add(r0)

        for key, title in [
            ("pwd_u", "uppercase (A-Z)"),
            ("pwd_l", "lowercase (a-z)"),
            ("pwd_d", "numbers (0-9)"),
            ("pwd_s", "weird symbols (!@#$)"),
            ("pwd_ambig", "no ambiguous shit (1, l, 0, O)")
        ]:
            r = Adw.ActionRow(title=title)
            sw = Gtk.Switch(valign=Gtk.Align.CENTER, active=self.vault.DEFAULTS[key])
            sw.connect("state-set", lambda _, st, k=key: self.vault.set(k, st) or self._on_generate(None) or False)
            r.add_suffix(sw)
            g0.add(r)

        r_ex = Adw.EntryRow(title="ban these chars")
        r_ex.connect("changed", lambda e: self.vault.set("pwd_exclude", e.get_text()) or self._on_generate(None))
        g0.add(r_ex)
        self.gen_stack.add_named(g0, "mode_0")

        g1 = Adw.PreferencesGroup()
        r1 = Adw.ActionRow(title="how many words?")
        self.spin_phrase_len = Gtk.SpinButton.new_with_range(2, 20, 1)
        self.spin_phrase_len.set_value(self.vault.DEFAULTS["phrase_words"])
        self.spin_phrase_len.set_valign(Gtk.Align.CENTER)
        self.spin_phrase_len.connect("value-changed", lambda s: self.vault.set("phrase_words", int(s.get_value())) or self._on_generate(None))
        r1.add_suffix(self.spin_phrase_len)
        g1.add(r1)

        r1_sep = Adw.EntryRow(title="separator", text=self.vault.DEFAULTS["phrase_sep"])
        r1_sep.connect("changed", lambda e: self.vault.set("phrase_sep", e.get_text()) or self._on_generate(None))
        g1.add(r1_sep)

        for key, title in [("phrase_cap", "make em capital"), ("phrase_num", "slap a number on the end")]:
            r = Adw.ActionRow(title=title)
            sw = Gtk.Switch(valign=Gtk.Align.CENTER, active=self.vault.DEFAULTS[key])
            sw.connect("state-set", lambda _, st, k=key: self.vault.set(k, st) or self._on_generate(None) or False)
            r.add_suffix(sw)
            g1.add(r)
        self.gen_stack.add_named(g1, "mode_1")

        g2 = Adw.PreferencesGroup()
        r2 = Adw.ComboRow(title="preset flavor", model=Gtk.StringList.new(["4-digit pin", "6-digit pin", "custom numbers", "custom everything"]))
        r2.connect("notify::selected", lambda o, _: self.vault.set("pin_preset", o.get_selected()) or self.row_pin_len.set_visible(o.get_selected() in (2, 3)) or self._on_generate(None))
        g2.add(r2)

        self.row_pin_len = Adw.ActionRow(title="custom length", visible=False)
        self.spin_pin_len = Gtk.SpinButton.new_with_range(2, 64, 1)
        self.spin_pin_len.set_value(self.vault.DEFAULTS["pin_len"])
        self.spin_pin_len.set_valign(Gtk.Align.CENTER)
        self.spin_pin_len.connect("value-changed", lambda s: self.vault.set("pin_len", int(s.get_value())) or self._on_generate(None))
        self.row_pin_len.add_suffix(self.spin_pin_len)
        g2.add(self.row_pin_len)
        self.gen_stack.add_named(g2, "mode_2")

        g3 = Adw.PreferencesGroup()
        r3 = Adw.ComboRow(title="skid type", model=Gtk.StringList.new(["mac address", "ipv6 ula", "wpa2/3 hex key", "wireguard key"]))
        r3.connect("notify::selected", lambda o, _: self.vault.set("net_mode", o.get_selected()) or self._on_generate(None))
        g3.add(r3)
        self.gen_stack.add_named(g3, "mode_3")

        g4 = Adw.PreferencesGroup()
        r4 = Adw.ComboRow(title="token flavor", model=Gtk.StringList.new(["uuidv4 standard", "fake api secret", "hex secret"]))
        r4.connect("notify::selected", lambda o, _: self.vault.set("uuid_mode", o.get_selected()) or self._on_generate(None))
        g4.add(r4)
        self.gen_stack.add_named(g4, "mode_4")

        g5 = Adw.PreferencesGroup()
        entry_mask = Adw.EntryRow(title="regex nightmare string", text=self.vault.DEFAULTS["mask_fmt"])
        entry_mask.connect("changed", lambda e: self.vault.set("mask_fmt", e.get_text()) or self._on_generate(None))
        g5.add(entry_mask)
        g5.add(Adw.ActionRow(title="wtf do these mean", subtitle="A: Upper, a: Lower, #: Digit, @: Symbol, ?: Any, \\: Escape", activatable=False))
        self.gen_stack.add_named(g5, "mode_5")

        g6 = Adw.PreferencesGroup()
        ckb_char = Adw.EntryRow(title="allowed chars", text=self.vault.DEFAULTS["ckb_charset"])
        ckb_char.connect("changed", lambda e: self.vault.set("ckb_charset", e.get_text()) or self._on_generate(None))
        g6.add(ckb_char)

        for key, title in [("ckb_groups", "how many blocks"), ("ckb_size", "chars per block")]:
            r = Adw.ActionRow(title=title)
            spin = Gtk.SpinButton.new_with_range(1, 16, 1)
            spin.set_value(self.vault.DEFAULTS[key])
            spin.set_valign(Gtk.Align.CENTER)
            spin.connect("value-changed", lambda s, k=key: self.vault.set(k, int(s.get_value())) or self._on_generate(None))
            r.add_suffix(spin)
            g6.add(r)
        
        ckb_sep = Adw.EntryRow(title="block separator", text=self.vault.DEFAULTS["ckb_sep"])
        ckb_sep.connect("changed", lambda e: self.vault.set("ckb_sep", e.get_text()) or self._on_generate(None))
        g6.add(ckb_sep)
        self.gen_stack.add_named(g6, "mode_6")

        g7 = Adw.PreferencesGroup()
        r7 = Adw.ComboRow(title="windows flavor", model=Gtk.StringList.new(["standard", "n edition", "server"]))
        r7.connect("notify::selected", lambda o, _: self.vault.set("b25_edition", o.get_selected()) or self._on_generate(None))
        g7.add(r7)
        self.gen_stack.add_named(g7, "mode_7")

        g8 = Adw.PreferencesGroup()
        r8 = Adw.ComboRow(title="how did you pirate it", model=Gtk.StringList.new(["retail / msdn", "oem", "volume / kms"]))
        r8.connect("notify::selected", lambda o, _: self.vault.set("b24_archetype", o.get_selected()) or self._on_generate(None))
        g8.add(r8)
        self.gen_stack.add_named(g8, "mode_8")

        g9 = Adw.PreferencesGroup()
        r9 = Adw.ComboRow(title="key shape", model=Gtk.StringList.new(["retail (10-digit)", "oem (23-digit)"]))
        r9.connect("notify::selected", lambda o, _: self.vault.set("legacy_mode", o.get_selected()) or self._on_generate(None))
        g9.add(r9)
        self.gen_stack.add_named(g9, "mode_9")
        
        g10 = Adw.PreferencesGroup()
        r10 = Adw.ActionRow(title="how long?", subtitle="length of the emoji soup")
        spin_emoji = Gtk.SpinButton.new_with_range(4, 64, 1)
        spin_emoji.set_value(16)
        spin_emoji.set_valign(Gtk.Align.CENTER)
        spin_emoji.connect("value-changed", lambda s: self.vault.set("pwd_len", int(s.get_value())) or self._on_generate(None))
        r10.add_suffix(spin_emoji)
        g10.add(r10)
        self.gen_stack.add_named(g10, "mode_10")

    def _on_generate(self, _btn) -> None:
        # if this breaks again im quitting
        if self._anim_timer:
            GLib.source_remove(self._anim_timer)
            self._anim_timer = None
            self.is_animating = False

        mode = self.vault.state.get("engine_mode", 0) if self.vault else 0
        result, self._current_type, entropy = ENGINE_FUNCS[mode](self.vault.state)

        if not result.startswith("ERR"):
            if not self._history or self._history[-1][0] != result:
                self._history.append((result, self._current_type, entropy))
                if len(self._history) > 30:
                    self._history.pop(0)
                self._history_idx = len(self._history) - 1
            self._update_history_buttons()

        self._display_result(result, self._current_type, entropy, animate=True)

        if self.vault and self.vault.state.get("auto_copy", False) and not result.startswith("ERR"):
            self._copy_val(result, silent=True)

    def _display_result(self, result: str, type_str: str, entropy: float, animate: bool = True) -> None:
        self._current_type = type_str
        if "ERR" in result or entropy <= 0:
            score, label = 0, "strength: absolutely garbage"
        elif entropy < 45:
            score, label = 1, f"strength: wet paper towel ({int(entropy)} bits)"
        elif entropy < 75:
            score, label = 2, f"strength: mid ({int(entropy)} bits)"
        elif entropy < 110:
            score, label = 3, f"strength: pretty beefy ({int(entropy)} bits)"
        else:
            score, label = 4, f"strength: gigachad ({int(entropy)} bits)"

        self.entropy_bar.set_value(score)
        self.entropy_lbl.set_label(label)
        self.crack_lbl.set_label(f"crack time: {estimate_crack_time(entropy)}")

        if score <= 1 and self.vault and self.vault.state.get("toxic_mode", False) and animate:
            self._toast(random.choice(["are you actually going to use this trash?", "wow. very secure.", "my grandma makes better passwords."]))

        if animate and self.vault and self.vault.state.get("animations", True) and not result.startswith("ERR"):
            self.is_animating = True
            self.btn_gen.set_sensitive(False)
            self.btn_save.set_sensitive(False)
            self._anim_target = result
            self._anim_frame = 0
            self._anim_timer = GLib.timeout_add(25, self._anim_tick)
        else:
            self.lbl_output.set_label(result)

    def _anim_tick(self) -> bool:
        # so i dont get blinded or die by it
        if self._anim_frame < len(self._anim_target):
            revealed = self._anim_target[:self._anim_frame]
            scrambled = "".join(
                secrets.choice("!@#$%&*0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ") if c not in "- :._" else c
                for c in self._anim_target[self._anim_frame:]
            )
            self.lbl_output.set_label(revealed + scrambled)
            speed = self.vault.state.get("anim_speed", 6)
            self._anim_frame += max(1, len(self._anim_target) // speed)
            return True

        self.lbl_output.set_label(self._anim_target)
        self.is_animating = False
        self.btn_gen.set_sensitive(True)
        self.btn_save.set_sensitive(True)
        self._anim_timer = None
        return False

    def _on_save(self, _btn) -> None:
        val = self.lbl_output.get_label()
        if val.startswith("ERR") or val == "...":
            return self._toast("generate some shit first, idiot.")

        if not self.vault.is_unlocked:
            self.app_stack.set_visible_child_name("vault")
            return self._toast("unlock the stash first.")

        lbl = self.entry_label.get_text().strip() or f"{self._current_type} ({time.strftime('%H:%M:%S')})"
        tag = self.entry_tag.get_text().strip()
        self.vault.add_record(lbl, val, self._current_type, tag)
        self._refresh_vault_list()
        self.entry_label.set_text("")
        self.entry_tag.set_text("")
        self._toast("shoved into the vault.")

    def _tab_vault(self) -> Gtk.Widget:
        self.vault_tab_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.vault_tab_stack.set_vhomogeneous(False)
        
        # lock screen view
        clamp = Adw.Clamp(maximum_size=380, valign=Gtk.Align.CENTER)
        box_lock = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20, margin_top=40, margin_bottom=40)
        box_lock.append(Adw.StatusPage(title="the vault of secrets", description="type the magic word or get out", icon_name="dialog-password-symbolic"))
        
        grp_pwd = Adw.PreferencesGroup()
        self.vault_unlock_entry = Adw.PasswordEntryRow(title="magic word")
        self.vault_unlock_entry.connect("entry-activated", self._on_vault_unlock_click)
        grp_pwd.add(self.vault_unlock_entry)
        box_lock.append(grp_pwd)

        row_btn = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        self.btn_unlock_vault = Gtk.Button(label="break in", css_classes=["suggested-action", "pill"])
        self.btn_unlock_vault.connect("clicked", self._on_vault_unlock_click)
        self.spinner_vault_unlock = Gtk.Spinner()
        row_btn.append(self.btn_unlock_vault)
        row_btn.append(self.spinner_vault_unlock)
        box_lock.append(row_btn)
        clamp.set_child(box_lock)
        self.vault_tab_stack.add_named(clamp, "locked")

        # unlocked view
        page_unlocked = Adw.PreferencesPage()
        
        grp_search = Adw.PreferencesGroup(title="find your garbage")
        search_box = Gtk.Box(spacing=8)
        
        self.vault_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        self.vault_list.set_filter_func(self._vault_filter)

        self.vault_search = Gtk.SearchEntry(placeholder_text="search for shit...", hexpand=True)
        self.vault_search.connect("search-changed", lambda _: self.vault_list.invalidate_filter())
        
        self.vault_type_filter = Gtk.DropDown.new_from_strings(TYPE_FILTERS)
        self.vault_type_filter.connect("notify::selected", lambda *_: self.vault_list.invalidate_filter())
        
        self.vault_tag_filter = Gtk.SearchEntry(placeholder_text="tag...")
        self.vault_tag_filter.set_size_request(110, -1)
        self.vault_tag_filter.connect("search-changed", lambda _: self.vault_list.invalidate_filter())
        
        search_box.append(self.vault_search)
        search_box.append(self.vault_type_filter)
        search_box.append(self.vault_tag_filter)
        grp_search.add(search_box)

        row_backup = Adw.ActionRow(title="stash backup &amp; restore")
        btn_export = Gtk.Button(label="export json", icon_name="document-save-symbolic", css_classes=["pill"], valign=Gtk.Align.CENTER)
        btn_export.connect("clicked", self._on_export_stash)
        btn_import = Gtk.Button(label="import json", icon_name="document-open-symbolic", css_classes=["pill"], valign=Gtk.Align.CENTER)
        btn_import.connect("clicked", self._on_import_stash)
        row_backup.add_suffix(btn_export)
        row_backup.add_suffix(btn_import)
        grp_search.add(row_backup)
        page_unlocked.add(grp_search)

        self.grp_vault_items = Adw.PreferencesGroup(title="the hoard")
        
        self.vault_view_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.vault_view_stack.add_named(
            Adw.StatusPage(title="literally nothing here", description="generate some shit first.", icon_name="folder-symbolic"),
            "empty"
        )
        
        scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=420)
        scroll.set_child(self.vault_list)
        self.vault_view_stack.add_named(scroll, "list")

        self.grp_vault_items.add(self.vault_view_stack)
        page_unlocked.add(self.grp_vault_items)
        self.vault_tab_stack.add_named(page_unlocked, "unlocked")

        self.vault_tab_stack.set_visible_child_name("locked")
        return self.vault_tab_stack

    def _on_vault_unlock_click(self, *_) -> None:
        if not (pwd := self.vault_unlock_entry.get_text()): return
        self.vault_unlock_entry.set_sensitive(False)
        self.btn_unlock_vault.set_sensitive(False)
        self.spinner_vault_unlock.start()
        threading.Thread(target=lambda: GLib.idle_add(self._finish_vault_unlock, self.vault.unlock(pwd), pwd), daemon=True).start()

    def _finish_vault_unlock(self, success: bool, pwd: str) -> bool:
        self.vault_unlock_entry.set_sensitive(True)
        self.btn_unlock_vault.set_sensitive(True)
        self.spinner_vault_unlock.stop()
        wipe_string(pwd)

        if success:
            self.vault_unlock_entry.set_text("")
            self.vault_tab_stack.set_visible_child_name("unlocked")
            self._refresh_vault_list()
            self._last_activity = time.time()
            if not self._auto_lock_tmr:
                self._auto_lock_tmr = GLib.timeout_add_seconds(AUTO_LOCK_POLL_SECONDS, self._check_auto_lock)
            self._toast("we are in.")
        else:
            self.vault_unlock_entry.set_text("")
            self.vault_unlock_entry.add_css_class("error")
            if self.vault.state.get("paranoia_mode", False):
                self.bad_auth_count += 1
                if self.bad_auth_count >= 3:
                    self._action_nuke(None)
                    self._toast("3 strikes. VAULT NUKED. goodbye.")
                    self.bad_auth_count = 0
                    return False
            toxic_msg = random.choice(["wrong password bozo.", "do you even remember it?", "typing is hard, huh?", "skill issue."])
            self._toast(toxic_msg if self.vault.state.get("toxic_mode", False) else "wrong password bozo.")
            GLib.timeout_add(1000, lambda: self.vault_unlock_entry.remove_css_class("error") or False)
        return False

    def _vault_filter(self, row: Gtk.ListBoxRow) -> bool:
        c = row.get_child()
        if not isinstance(c, Adw.ActionRow): return True
        q = self.vault_search.get_text().strip().lower()
        t = self.vault_tag_filter.get_text().strip().lower()
        
        selected_idx = self.vault_type_filter.get_selected()
        type_choice = TYPE_FILTERS[selected_idx]
        item_type = getattr(c, "_type", "")

        type_match = True
        is_fav = getattr(c, "_fav", False)
        if type_choice == "favorites ⭐": type_match = bool(is_fav)
        elif type_choice == "passwords": type_match = item_type == "Password"
        elif type_choice == "passphrases": type_match = item_type == "Passphrase"
        elif type_choice == "pins &amp; passcodes": type_match = item_type in ("PIN", "Passcode")
        elif type_choice == "stolen licenses": type_match = "Win" in item_type or "License" in item_type
        elif type_choice == "api tokens": type_match = "Token" in item_type or "UUID" in item_type or "Secret" in item_type or "Key" in item_type
        elif type_choice == "network configs": type_match = item_type in ("Hardware", "Network", "Hardware MAC", "IPv6 ULA", "WPA PSK", "WireGuard Secret")
        elif type_choice == "custom blocks": type_match = "Custom" in item_type
        elif type_choice == "masked shit": type_match = "Masked" in item_type

        title_ok = not q or q in (c.get_title() or "").lower() or q in getattr(c, "_val", "").lower()
        tag_ok = not t or t in getattr(c, "_tag", "").lower()
        return type_match and title_ok and tag_ok

    def _refresh_vault_list(self) -> None:
        while child := self.vault_list.get_first_child():
            self.vault_list.remove(child)
        if not self.vault.records:
            return self.vault_view_stack.set_visible_child_name("empty")
        self.vault_view_stack.set_visible_child_name("list")
        sorted_records = sorted(
            self.vault.records,
            key=lambda r: (1 if r.get("fav", False) else 0, r.get("timestamp", 0)),
            reverse=True
        )
        for item in sorted_records:
            self._append_vault_row(item)

    def _append_vault_row(self, item: Dict[str, Any]) -> None:
        time_str = format_relative_time(item.get("timestamp", time.time()))
        row = Adw.ActionRow(title=item["label"], subtitle=f"••••••••••••  ·  {time_str}")
        row._fav = item.get("fav", False)
        row._id = item["id"]
        row._tag = item.get("tag", "")
        row._val = item["val"]
        row._type = item.get("type", "")

        badge_color = {
            "Password": "badge-green", "Passphrase": "badge-green",
            "Passcode": "badge-amber", "PIN": "badge-amber",
            "Custom Key": "badge-purple", "Masked Key": "badge-purple",
            "Hardware MAC": "badge-cyan", "IPv6 ULA": "badge-cyan", "UUIDv4": "badge-cyan"
        }.get(item["type"], "badge-blue")

        btn_star = Gtk.Button(
            icon_name="starred-symbolic" if row._fav else "non-starred-symbolic",
            tooltip_text="unpin" if row._fav else "pin to top (star)",
            valign=Gtk.Align.CENTER,
            css_classes=["flat"] + (["fav-star"] if row._fav else [])
        )
        def _toggle_star(_btn, uid=item["id"]):
            new_fav = self.vault.toggle_fav(uid)
            self._refresh_vault_list()
            self._toast("pinned to top ⭐" if new_fav else "unpinned.")
        btn_star.connect("clicked", _toggle_star)
        row.add_prefix(btn_star)

        row.add_prefix(self._badge(item["type"], badge_color))
        if item.get("tag"):
            row.add_prefix(self._badge(item["tag"], "badge-purple"))

        rev = Gtk.Button(icon_name="view-conceal-symbolic", tooltip_text="peek", valign=Gtk.Align.CENTER, css_classes=["flat"])
        def _toggle_reveal(btn, r=row):
            is_hidden = "••••••••••••" in r.get_subtitle()
            r.set_subtitle(r._val if is_hidden else f"••••••••••••  ·  {time_str}")
            btn.set_icon_name("view-reveal-symbolic" if is_hidden else "view-conceal-symbolic")
        rev.connect("clicked", _toggle_reveal)
        row.add_suffix(rev)

        edit_btn = Gtk.Button(icon_name="document-edit-symbolic", tooltip_text="edit label/tag", valign=Gtk.Align.CENTER, css_classes=["flat"])
        edit_btn.connect("clicked", lambda _, it=item: self._show_edit_dialog(it))
        row.add_suffix(edit_btn)

        cp = Gtk.Button(icon_name="edit-copy-symbolic", tooltip_text="yoink", valign=Gtk.Align.CENTER, css_classes=["flat"])
        cp.connect("clicked", lambda _, v=item["val"]: self._copy_val(v))
        row.add_suffix(cp)

        dl = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="yeet", valign=Gtk.Align.CENTER, css_classes=["flat"])
        dl.connect("clicked", lambda _, uid=item["id"], rw=row: self._delete_record(uid, rw))
        row.add_suffix(dl)

        self.vault_list.append(row)

    def _show_edit_dialog(self, item: Dict[str, Any]) -> None:
        dialog = Adw.AlertDialog.new("edit stash record", None)
        dialog.add_response("cancel", "cancel")
        dialog.add_response("save", "save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=8, margin_bottom=8)
        grp = Adw.PreferencesGroup()
        e_lbl = Adw.EntryRow(title="label", text=item.get("label", ""))
        e_tag = Adw.EntryRow(title="tag", text=item.get("tag", ""))
        grp.add(e_lbl)
        grp.add(e_tag)
        box.append(grp)
        dialog.set_extra_child(box)

        def _on_resp(d, resp):
            if resp == "save":
                new_lbl = e_lbl.get_text().strip() or item.get("label", "")
                new_tag = e_tag.get_text().strip()
                self.vault.update_record(item["id"], new_lbl, new_tag)
                self._refresh_vault_list()
                self._toast("record updated.")

        dialog.connect("response", _on_resp)
        dialog.present(self.win)

    def _on_export_stash(self, _btn) -> None:
        if not self.vault or not self.vault.is_unlocked:
            return self._toast("unlock the stash first.")
        exported = self.vault.export_vault_json()
        if cb := Gdk.Display.get_default().get_clipboard():
            cb.set(exported)
        self._toast(f"exported {len(self.vault.records)} records to clipboard.")

    def _on_import_stash(self, _btn) -> None:
        if not self.vault or not self.vault.is_unlocked:
            return self._toast("unlock the stash first.")

        dialog = Adw.AlertDialog.new("import stash records", "paste json records array below")
        dialog.add_response("cancel", "cancel")
        dialog.add_response("import", "import")
        dialog.set_response_appearance("import", Adw.ResponseAppearance.SUGGESTED)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=8, margin_bottom=8)
        buf = Gtk.TextBuffer()
        tv = Gtk.TextView(buffer=buf, wrap_mode=Gtk.WrapMode.CHAR, monospace=True)
        tv.set_size_request(-1, 140)
        sc = Gtk.ScrolledWindow(min_content_height=140, max_content_height=220)
        sc.set_child(tv)
        box.append(sc)
        dialog.set_extra_child(box)

        def _on_resp(d, resp):
            if resp == "import":
                raw = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()
                if raw:
                    count = self.vault.import_vault_json(raw)
                    if count > 0:
                        self._refresh_vault_list()
                        self._toast(f"imported {count} records into stash.")
                    else:
                        self._toast("failed to parse json.")

        dialog.connect("response", _on_resp)
        dialog.present(self.win)

    def _delete_record(self, uid: str, rw: Gtk.ListBoxRow) -> None:
        self.vault.delete_record(uid)
        self.vault_list.remove(rw)
        if not self.vault.records:
            self.vault_view_stack.set_visible_child_name("empty")
        self._toast("deleted. it is gone.")

    def _copy_val(self, txt: str) -> None:
        if cb := Gdk.Display.get_default().get_clipboard():
            cb.set(txt)
            ttl = self.vault.state.get("clipboard_ttl", 0)
            if ttl > 0:
                GLib.timeout_add_seconds(ttl, lambda: Gdk.Display.get_default().get_clipboard().set("") or False)
            if self.vault.state.get("toxic_mode", False):
                self._toast(random.choice(["yoinked. try not to paste it in general chat.", "copied. you're gonna lose it anyway.", "stolen. hope nobody is looking.", "clipboard tainted."]) + (f" (nuking in {ttl}s)" if ttl else ""))
            else:
                self._toast(f"yoinked to clipboard." + (f" (self-destructs in {ttl}s)" if ttl else ""))

    def _tab_settings(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()

        g_sec = Adw.PreferencesGroup(title="paranoia settings")
        row_al = Adw.ActionRow(title="afk lock timer", subtitle="how long before i lock you out")
        self.spin_auto_lock = Gtk.SpinButton.new_with_range(1, 60, 1)
        self.spin_auto_lock.set_value(self.vault.DEFAULTS["auto_lock_mins"])
        self.spin_auto_lock.set_valign(Gtk.Align.CENTER)
        self.spin_auto_lock.connect("value-changed", lambda s: self.vault.set("auto_lock_mins", int(s.get_value())))
        row_al.add_suffix(self.spin_auto_lock)
        g_sec.add(row_al)

        self.row_vault_path = Adw.ActionRow(title="where the bodies are buried", subtitle=self.vault.state.get("vault_path", DEFAULT_VAULT))
        btn_browse = Gtk.Button(icon_name="folder-open-symbolic", tooltip_text="move the stash", valign=Gtk.Align.CENTER, css_classes=["flat"])
        btn_browse.connect("clicked", self._on_browse_path)
        self.row_vault_path.add_suffix(btn_browse)
        g_sec.add(self.row_vault_path)

        row_nuke = Adw.ActionRow(title="nuke it from orbit", subtitle="press this to destroy everything forever")
        btn_nuke = Gtk.Button(label="yeet everything", valign=Gtk.Align.CENTER, css_classes=["destructive-action", "pill"])
        btn_nuke.connect("clicked", self._action_nuke)
        row_nuke.add_suffix(btn_nuke)
        g_sec.add(row_nuke)
        row_paranoid = Adw.ActionRow(title="dead man's switch", subtitle="nuke vault after 3 wrong passwords")
        sw_paranoid = Gtk.Switch(valign=Gtk.Align.CENTER, active=self.vault.state.get("paranoia_mode", False))
        sw_paranoid.connect("state-set", lambda _, st: self.vault.set("paranoia_mode", st) or False)
        row_paranoid.add_suffix(sw_paranoid)
        g_sec.add(row_paranoid)
        row_clip = Adw.ActionRow(title="clipboard auto-nuke (seconds)", subtitle="0 to disable. self-destructs your clipboard.")
        spin_clip = Gtk.SpinButton.new_with_range(0, 60, 1)
        spin_clip.set_value(self.vault.state.get("clipboard_ttl", 0))
        spin_clip.set_valign(Gtk.Align.CENTER)
        spin_clip.connect("value-changed", lambda s: self.vault.set("clipboard_ttl", int(s.get_value())))
        row_clip.add_suffix(spin_clip)
        row_clip.add_prefix(Gtk.Image.new_from_icon_name("edit-clear-all-symbolic"))
        g_sec.add(row_clip)
        
        row_panic = Adw.ActionRow(title="PANIC BUTTON", subtitle="instantly locks and shreds the vault from memory")
        btn_panic = Gtk.Button(label="NUKE NOW", valign=Gtk.Align.CENTER, css_classes=["destructive-action", "pill"])
        btn_panic.connect("clicked", self._action_nuke)
        row_panic.add_suffix(btn_panic)
        row_panic.add_prefix(Gtk.Image.new_from_icon_name("system-shutdown-symbolic"))
        g_sec.add(row_panic)


        page.add(g_sec)


        g_vibes = Adw.PreferencesGroup(title="aesthetics &amp; vibes")
        
        row_theme = Adw.ComboRow(title="theme flavor", model=Gtk.StringList.new(["dark mode (based)", "light mode (flashbang)", "system default"]))
        row_theme.set_selected(self.vault.state.get("ui_theme", 0))
        row_theme.connect("notify::selected", lambda o, _: self.vault.set("ui_theme", o.get_selected()) or self._apply_theme())
        row_theme.add_prefix(Gtk.Image.new_from_icon_name("format-text-color-symbolic"))
        g_vibes.add(row_theme)

        row_font = Adw.ComboRow(title="hacker font", model=Gtk.StringList.new(["jetbrains mono", "fira code", "cascadia code", "generic monospace", "comic sans (unhinged)"]))
        row_font.set_selected(self.vault.state.get("ui_font", 0))
        row_font.connect("notify::selected", lambda o, _: self.vault.set("ui_font", o.get_selected()) or self._apply_theme())
        row_font.add_prefix(Gtk.Image.new_from_icon_name("preferences-desktop-font-symbolic"))
        g_vibes.add(row_font)

        palette_names = [p[0] for p in PALETTES]
        row_palette = Adw.ComboRow(title="curated colorways", model=Gtk.StringList.new(palette_names))
        row_palette.set_selected(self.vault.state.get("palette_preset", 1) if self.vault else 1)
        def _on_palette_change(combo, _):
            idx = combo.get_selected()
            if self.vault: self.vault.set("palette_preset", idx)
            if idx > 0 and idx < len(PALETTES):
                color = PALETTES[idx][1]
                if self.vault: self.vault.set("ui_accent", color)
                self.row_accent.set_text(color)
                rgba = Gdk.RGBA()
                if rgba.parse(color):
                    self.btn_color_picker.set_rgba(rgba)
                self._apply_theme()
        row_palette.connect("notify::selected", _on_palette_change)
        row_palette.add_prefix(Gtk.Image.new_from_icon_name("applications-graphics-symbolic"))
        g_vibes.add(row_palette)

        self.row_accent = Adw.EntryRow(title="accent color (hex)")
        self.row_accent.set_text(self.vault.state.get("ui_accent", "#ff2a5f") if self.vault else "#ff2a5f")
        self.row_accent.connect("changed", lambda e: self.vault.set("ui_accent", e.get_text()) or self._apply_theme())
        self.row_accent.add_prefix(Gtk.Image.new_from_icon_name("color-select-symbolic"))

        color_dialog = Gtk.ColorDialog()
        self.btn_color_picker = Gtk.ColorDialogButton(dialog=color_dialog, valign=Gtk.Align.CENTER)
        init_rgba = Gdk.RGBA()
        if init_rgba.parse(self.vault.state.get("ui_accent", "#ff2a5f") if self.vault else "#ff2a5f"):
            self.btn_color_picker.set_rgba(init_rgba)
        def _on_color_picked(btn, _):
            picked = btn.get_rgba()
            hex_str = f"#{int(picked.red*255):02x}{int(picked.green*255):02x}{int(picked.blue*255):02x}"
            if self.vault: self.vault.set("ui_accent", hex_str)
            self.row_accent.set_text(hex_str)
            self._apply_theme()
        self.btn_color_picker.connect("notify::rgba", _on_color_picked)
        self.row_accent.add_suffix(self.btn_color_picker)
        g_vibes.add(self.row_accent)

        row_autocopy = Adw.ActionRow(title="auto-yoink on roll", subtitle="instantly copy each generated key to clipboard")
        sw_autocopy = Gtk.Switch(valign=Gtk.Align.CENTER, active=self.vault.state.get("auto_copy", False) if self.vault else False)
        sw_autocopy.connect("state-set", lambda _, st: self.vault.set("auto_copy", st) or False)
        row_autocopy.add_suffix(sw_autocopy)
        row_autocopy.add_prefix(Gtk.Image.new_from_icon_name("edit-copy-symbolic"))
        g_vibes.add(row_autocopy)

        row_glow = Adw.ActionRow(title="neon glow intensity", subtitle="crank it up so it hurts")
        spin_glow = Gtk.SpinButton.new_with_range(0, 50, 1)
        spin_glow.set_value(self.vault.state.get("ui_glow", 8))
        spin_glow.set_valign(Gtk.Align.CENTER)
        spin_glow.connect("value-changed", lambda s: self.vault.set("ui_glow", int(s.get_value())) or self._apply_theme())
        row_glow.add_suffix(spin_glow)
        g_vibes.add(row_glow)

        row_rad = Adw.ActionRow(title="border radius", subtitle="0px = edgy, 12px = standard, 24px = bubble")
        spin_rad = Gtk.SpinButton.new_with_range(0, 40, 1)
        spin_rad.set_value(self.vault.state.get("ui_radius", 12))
        spin_rad.set_valign(Gtk.Align.CENTER)
        spin_rad.connect("value-changed", lambda s: self.vault.set("ui_radius", int(s.get_value())) or self._apply_theme())
        row_rad.add_suffix(spin_rad)
        g_vibes.add(row_rad)


        row_rgb = Adw.ActionRow(title="rgb gamer mode", subtitle="epilepsy warning")
        sw_rgb = Gtk.Switch(valign=Gtk.Align.CENTER, active=self.vault.state.get("rgb_mode", False))
        sw_rgb.connect("state-set", self._on_rgb_toggled)
        row_rgb.add_suffix(sw_rgb)
        row_rgb.add_prefix(Gtk.Image.new_from_icon_name("video-display-symbolic"))
        g_vibes.add(row_rgb)

        row_opacity = Adw.ActionRow(title="ghost mode (opacity)", subtitle="make the window transparent to hide from your boss")
        spin_op = Gtk.SpinButton.new_with_range(0.1, 1.0, 0.05)
        spin_op.set_value(self.vault.state.get("ui_opacity", 1.0))
        spin_op.set_valign(Gtk.Align.CENTER)
        spin_op.connect("value-changed", lambda s: self.vault.set("ui_opacity", s.get_value()) or self._apply_theme())
        row_opacity.add_suffix(spin_op)
        row_opacity.add_prefix(Gtk.Image.new_from_icon_name("weather-clear-symbolic"))
        g_vibes.add(row_opacity)

        row_drunk = Adw.ActionRow(title="drunk ui mode", subtitle="the layout jiggles uncontrollably")
        sw_drunk = Gtk.Switch(valign=Gtk.Align.CENTER, active=self.vault.state.get("drunk_mode", False))
        sw_drunk.connect("state-set", self._on_drunk_toggled)
        row_drunk.add_suffix(sw_drunk)
        row_drunk.add_prefix(Gtk.Image.new_from_icon_name("face-sick-symbolic"))
        g_vibes.add(row_drunk)

        page.add(g_vibes)

        g_app = Adw.PreferencesGroup(title="eye candy")
        row_ani = Adw.ActionRow(title="schizo matrix animation", subtitle="makes you feel like a hacker")
        self.sw_ani = Gtk.Switch(valign=Gtk.Align.CENTER, active=self.vault.DEFAULTS["animations"])
        self.sw_ani.connect("state-set", lambda _, st: self.vault.set("animations", st) or False)
        row_ani.add_suffix(self.sw_ani)
        g_app.add(row_ani)
        row_toxic = Adw.ActionRow(title="toxic mode", subtitle="the app actively disrespects you")
        sw_toxic = Gtk.Switch(valign=Gtk.Align.CENTER, active=self.vault.state.get("toxic_mode", False))
        sw_toxic.connect("state-set", lambda _, st: self.vault.set("toxic_mode", st) or False)
        row_toxic.add_suffix(sw_toxic)
        row_toxic.add_prefix(Gtk.Image.new_from_icon_name("face-smirk-symbolic"))
        g_app.add(row_toxic)
        row_anim_speed = Adw.ActionRow(title="schizo animation speed", subtitle="lower is faster. breaks the matrix.")
        spin_anim = Gtk.SpinButton.new_with_range(1, 50, 1)
        spin_anim.set_value(self.vault.state.get("anim_speed", 6))
        spin_anim.set_valign(Gtk.Align.CENTER)
        spin_anim.connect("value-changed", lambda s: self.vault.set("anim_speed", int(s.get_value())))
        row_anim_speed.add_suffix(spin_anim)
        row_anim_speed.add_prefix(Gtk.Image.new_from_icon_name("preferences-system-time-symbolic"))
        g_app.add(row_anim_speed)


        page.add(g_app)

        g_about = Adw.PreferencesGroup(title="the guts")
        g_about.add(Adw.ActionRow(title=APP_NAME, subtitle=f"v{APP_VERSION} · AES-256-GCM / PBKDF2-SHA256 (600k rounds)", activatable=False))
        page.add(g_about)
        return page

    def _action_lock(self, _btn=None) -> None:
        if self.vault:
            self.vault.lock()
        if hasattr(self, "vault_tab_stack"):
            self.vault_tab_stack.set_visible_child_name("locked")
        if hasattr(self, "vault_list"):
            while child := self.vault_list.get_first_child():
                self.vault_list.remove(child)
        if self._auto_lock_tmr:
            GLib.source_remove(self._auto_lock_tmr)
            self._auto_lock_tmr = None
        self._toast("locked. safely hidden from the feds.")

    def _action_nuke(self, _btn) -> None:
        # fixing this garbage layout with fire
        path = self.vault.state.get("vault_path", DEFAULT_VAULT)
        if os.path.exists(path):
            os.remove(path)
        self._action_lock(None)
        self._toast("nuked. the feds will find nothing.")

    def _on_browse_path(self, _btn) -> None:
        dlg = Gtk.FileDialog(title="pick a datastore file")
        ff = Gtk.FileFilter()
        ff.set_name("datastore (*.dat)")
        ff.add_pattern("*.dat")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(ff)
        dlg.set_filters(filters)
        dlg.set_default_filter(ff)
        dlg.save(self.win, None, self._finish_browse)

    def _finish_browse(self, dlg: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
        try:
            if f := dlg.save_finish(res):
                new_path = f.get_path()
                if not os.path.isdir(os.path.dirname(new_path)):
                    return self._toast("Invalid directory.")
                self.vault.set("vault_path", new_path)
                self.row_vault_path.set_subtitle(new_path)
                self._action_lock(None)
        except Exception:
            pass

def main():
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = VaultForgeUI()
    try:
        sys.exit(app.run(sys.argv))
    except KeyboardInterrupt:
        sys.exit(130)

if __name__ == "__main__":
    main()

