import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Keybinder", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango, Keybinder
import sqlite3
from datetime import datetime
import os
import sys


class ExpandableTextRenderer(Gtk.CellRendererText):

    def __init__(self):
        super().__init__()
        self.props.ellipsize = Pango.EllipsizeMode.END
        self.props.wrap_mode = Pango.WrapMode.WORD_CHAR
        self.expanded = {}

    def set_expanded(self, path, is_expanded):
        self.expanded[path] = is_expanded

    def is_expanded(self, path):
        return self.expanded.get(path, False)


class ClipboardManager:

    def __init__(self):
        # Initialize database
        self.db_path = os.path.expanduser("~/.clipboard_history.db")
        self.init_database()
        self.create_autostart()
        # Initialize clipboard
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        # Init window
        self.window = Gtk.Window(title="Clipboard History")
        self.window.set_default_size(600, 500)
        self.window.connect("delete-event", self.on_window_delete)

        # Dark theme
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True)

        # CSS for dark theme and column sizes
        css_provider = Gtk.CssProvider()
        css = """
        window {
            background-color: #2d2d2d;
            color: #ffffff;
        }
        treeview {
            background-color: #333333;
            color: #ffffff;
        }
        treeview:selected {
            background-color: #4a4a4a;
        }
        entry {
            background: #3d3d3d;
            color: white;
            padding: 5px;
        }
        """
        css_provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        # Main layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.window.add(vbox)

        # Search entry
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Search clipboard history...")
        self.search_entry.connect("changed", self.on_search_changed)
        search_box.pack_start(self.search_entry, True, True, 5)
        vbox.pack_start(search_box, False, False, 5)

        # Date selector
        date_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.date_combo = Gtk.ComboBoxText()
        self.update_date_combo()
        date_box.pack_start(self.date_combo, True, True, 5)
        self.date_combo.connect("changed", self.on_date_changed)
        vbox.pack_start(date_box, False, False, 0)

        # Clipboard history list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        vbox.pack_start(scrolled, True, True, 0)

        self.liststore = Gtk.ListStore(str, str, str)  # id, time, text
        self.treeview = Gtk.TreeView(model=self.liststore)

        # Time column (auto-sizing)
        time_renderer = Gtk.CellRendererText()
        time_column = Gtk.TreeViewColumn("Time", time_renderer, text=1)
        time_column.set_spacing(10)
        time_column.set_resizable(True)
        time_column.set_min_width(80)
        self.treeview.append_column(time_column)

        # Text column (expands to fill space)
        self.text_renderer = ExpandableTextRenderer()
        text_column = Gtk.TreeViewColumn("Text", self.text_renderer, text=2)
        text_column.set_spacing(10)
        text_column.set_resizable(True)
        text_column.set_expand(True)
        text_column.set_min_width(300)
        self.treeview.append_column(text_column)

        copy_renderer = Gtk.CellRendererPixbuf()
        copy_renderer.set_property("icon-name", "edit-copy-symbolic")
        copy_column = Gtk.TreeViewColumn("", copy_renderer)
        copy_column.set_fixed_width(30)
        self.treeview.append_column(copy_column)

        # Delete column (fixed small width)
        delete_renderer = Gtk.CellRendererPixbuf()
        delete_renderer.set_property("icon-name", "user-trash-symbolic")
        delete_column = Gtk.TreeViewColumn("", delete_renderer)
        delete_column.set_fixed_width(30)
        self.treeview.append_column(delete_column)

        # Connect handlers
        self.treeview.connect("button-press-event", self.on_button_press)

        scrolled.add(self.treeview)

        # Setup hotkey (Ctrl+Alt+V)
        Keybinder.init()
        Keybinder.bind("<Ctrl>grave", self.show_at_cursor)  # Ctrl+` (backtick)

        # Start monitoring
        GLib.timeout_add(100, self.check_clipboard)

        self.last_text = None
        today = datetime.now().strftime("%Y-%m-%d")
        self.update_history_list(today)
        self.window.show_all()

    def on_window_delete(self, window, event):
        window.hide()
        return True

    def show_at_cursor(self, keystring):

        display = Gdk.Display.get_default()
        seat = display.get_default_seat()
        pointer = seat.get_pointer()

        # Get the pointer position
        _, x, y = pointer.get_position()

        # Get window size
        window_width, window_height = self.window.get_size()

        # Get monitor at cursor position
        monitor = display.get_monitor_at_point(x, y)
        geometry = monitor.get_geometry()

        # Keep window within monitor bounds
        x = min(max(x, geometry.x), geometry.x + geometry.width - window_width)
        y = min(max(y, geometry.y), geometry.y + geometry.height - window_height)

        # Adjust position to be near cursor but not under it
        window_x = x - (window_width // 2)  # Center horizontally relative to cursor
        window_y = y + 20  # Slightly below cursor

        # Final bounds check
        window_x = max(
            geometry.x, min(window_x, geometry.x + geometry.width - window_width)
        )
        window_y = max(
            geometry.y, min(window_y, geometry.y + geometry.height - window_height)
        )

        self.window.move(window_x, window_y)
        self.window.present()
        self.window.grab_focus()

    def on_search_changed(self, entry):
        search_text = entry.get_text().lower()
        current_date = self.date_combo.get_active_text()
        if current_date:
            self.update_history_list(current_date, search_text)

    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS clipboard_history
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    content TEXT NOT NULL)"""
        )
        conn.commit()
        conn.close()

    def update_date_combo(self):
        current_selection = self.date_combo.get_active_text()

        self.date_combo.remove_all()
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            "SELECT DISTINCT date(timestamp) FROM clipboard_history ORDER BY timestamp DESC"
        )
        dates = c.fetchall()
        conn.close()

        for date in dates:
            self.date_combo.append_text(date[0])

        if dates:
            self.date_combo.set_active(0)

    def on_date_changed(self, combo):
        selected_date = combo.get_active_text()
        search_text = self.search_entry.get_text().lower()
        if selected_date:
            self.update_history_list(selected_date, search_text)

    def update_history_list(self, date, search_text=""):
        self.liststore.clear()
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        try:
            if search_text:
                c.execute(
                    """
                    SELECT id, time(timestamp), content 
                    FROM clipboard_history 
                    WHERE date(timestamp) = ? 
                    AND lower(content) LIKE ?
                    ORDER BY timestamp DESC
                """,
                    (date, "%" + search_text + "%"),
                )
            else:
                c.execute(
                    """
                    SELECT id, time(timestamp), content 
                    FROM clipboard_history 
                    WHERE date(timestamp) = ? 
                    ORDER BY timestamp DESC""",
                    (date,),
                )

            for row in c.fetchall():
                display_text = row[2][:50] + "..." if len(row[2]) > 50 else row[2]
                self.liststore.append([str(row[0]), row[1], display_text])
        except Exception as e:
            print("Error updating history list:", e, file=sys.stderr)
        finally:
            conn.close()

    def toggle_text_expansion(self, path):
        model = self.treeview.get_model()
        item_id = model[path][0]

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT content FROM clipboard_history WHERE id = ?", (item_id,))
        result = c.fetchone()
        conn.close()

        if result:
            full_text = result[0]
            if self.text_renderer.is_expanded(str(path)):
                model[path][2] = (
                    full_text[:50] + "..." if len(full_text) > 50 else full_text
                )
                self.text_renderer.set_expanded(str(path), False)
            else:
                model[path][2] = full_text
                self.text_renderer.set_expanded(str(path), True)

    def on_button_press(self, treeview, event):
        if event.button == 1:  # Left click
            path_info = treeview.get_path_at_pos(int(event.x), int(event.y))
            if path_info:
                path, column, _, _ = path_info
                if column == self.treeview.get_columns()[1]:  # Text column
                    self.toggle_text_expansion(path)
                    return True
                elif column == self.treeview.get_columns()[2]:  # Copy column
                    self.copy_item(path)
                    return True
                elif column == self.treeview.get_columns()[3]:  # Delete column
                    self.delete_item(path)
                    return True
        return False

    def copy_item(self, path):
        model = self.treeview.get_model()
        item_id = model[path][0]

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT content FROM clipboard_history WHERE id = ?", (item_id,))
        result = c.fetchone()
        conn.close()

        if result:
            self.clipboard.set_text(result[0], -1)

    def delete_item(self, path):
        model = self.treeview.get_model()
        item_id = model[path][0]

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM clipboard_history WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()

        model.remove(model.get_iter(path))

    def check_clipboard(self):
        try:
            today = datetime.now().strftime("%Y-%m-%d")

            text = self.clipboard.wait_for_text()
            if text and text != self.last_text:
                self.last_text = text
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()

                # First, check if we have any entries for today
                c.execute(
                    "SELECT COUNT(*) FROM clipboard_history WHERE date(timestamp) = ?",
                    (today,),
                )
                had_entries = c.fetchone()[0] > 0

                # Insert new entry
                c.execute(
                    "INSERT INTO clipboard_history (timestamp, content) VALUES (?, ?)",
                    (timestamp, text),
                )
                conn.commit()
                conn.close()

                # If this was the first entry for today, refresh the date list
                if not had_entries:
                    self.update_date_combo()

                # Update the list view
                current_date = self.date_combo.get_active_text()
                if current_date == today:
                    search_text = self.search_entry.get_text().lower()
                    self.update_history_list(today, search_text)

        except Exception as e:
            print("Error checking clipboard:", e, file=sys.stderr)
        return True

    def create_autostart(self):
        autostart_dir = os.path.expanduser("~/.config/autostart")
        desktop_file = os.path.join(autostart_dir, "clipboard-manager.desktop")

        if not os.path.exists(autostart_dir):
            os.makedirs(autostart_dir)

        # Get the path to the script
        script_path = os.path.abspath(sys.argv[0])

        desktop_content = f"""[Desktop Entry]
        Type=Application
        Name=Clipboard Manager
        Exec=python3 {script_path}
        Hidden=false
        NoDisplay=false
        X-GNOME-Autostart-enabled=true
    """

        with open(desktop_file, "w") as f:
            f.write(desktop_content)


def main():
    try:
        app = ClipboardManager()
        Gtk.main()
    except Exception as e:
        print("Error in main:", e, file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
