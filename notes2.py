import streamlit as st
import sqlite3
from streamlit_quill import st_quill
import re
import html  # For escaping heading
import datetime

# Database setup
DB_FILE = "notes.db"

def get_text_color(bg_color):
    try:
        hex_color = bg_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return '#000000' if luminance > 0.5 else '#FFFFFF'
    except:
        return '#000000'


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Folders
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)
    # Notes with optional note_date
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            heading TEXT NOT NULL,
            description TEXT,
            folder_id INTEGER,
            color TEXT DEFAULT '#FFFFE0',
            body_color TEXT DEFAULT '#FFFFFF',
            note_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE
        )
    """)
    # Add body_color if missing
    try:
        cursor.execute("ALTER TABLE notes ADD COLUMN body_color TEXT DEFAULT '#FFFFFF'")
    except sqlite3.OperationalError:
        pass
    # Add note_date if missing
    try:
        cursor.execute("ALTER TABLE notes ADD COLUMN note_date DATE")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def add_folder(name):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO folders (name) VALUES (?)", (name,))
        conn.commit()
    except sqlite3.IntegrityError:
        st.error(f"Folder '{name}' already exists.")
    finally:
        conn.close()


def get_folders():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM folders ORDER BY name")
    folders = cursor.fetchall()
    conn.close()
    return folders


def delete_folder(folder_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
    conn.commit()
    conn.close()


def add_note(heading, description, folder_id=None,
             banner_color='#FFFFE0', body_color='#FFFFFF', note_date=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cleaned = description or ""
    if cleaned.strip() in ["", "<p><br></p>"]:
        cleaned = ""
    if note_date:
        # Insert with specific note_date
        cursor.execute(
            "INSERT INTO notes (heading, description, folder_id, color, body_color, note_date)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (heading, cleaned, folder_id, banner_color, body_color, note_date)
        )
    else:
        # Insert without note_date (NULL)
        cursor.execute(
            "INSERT INTO notes (heading, description, folder_id, color, body_color)"
            " VALUES (?, ?, ?, ?, ?)",
            (heading, cleaned, folder_id, banner_color, body_color)
        )
    conn.commit()
    conn.close()


def get_notes_by_folder(folder_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if folder_id is None:
        cursor.execute(
            "SELECT id, heading, description, color, body_color"
            " FROM notes WHERE folder_id IS NULL AND note_date IS NULL"
            " ORDER BY created_at DESC"
        )
    else:
        cursor.execute(
            "SELECT id, heading, description, color, body_color"
            " FROM notes WHERE folder_id = ? AND note_date IS NULL"
            " ORDER BY created_at DESC",
            (folder_id,)
        )
    notes = cursor.fetchall()
    conn.close()
    return notes


def get_notes_by_date(date_str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, heading, description, color, body_color"
        " FROM notes WHERE note_date = ?"
        " ORDER BY created_at DESC",
        (date_str,)
    )
    notes = cursor.fetchall()
    conn.close()
    return notes


def update_note(note_id, heading, description, banner_color, body_color):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cleaned = description or ""
    if cleaned.strip() in ["", "<p><br></p>"]:
        cleaned = ""
    cursor.execute(
        "UPDATE notes SET heading = ?, description = ?, color = ?, body_color = ? WHERE id = ?",
        (heading, cleaned, banner_color, body_color, note_id)
    )
    conn.commit()
    conn.close()


def delete_note(note_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()

# Initialize DB
init_db()

# Session state defaults
if 'view' not in st.session_state:
    st.session_state.view = 'home'
for key, default in {
    'editing_note_id': None,
    'selected_folder_id': None,
    'show_create_note_form': False,
    'new_note_heading_value': "",
    'new_note_quill_value': "",
    'quill_key_suffix': 0,
    'selected_date': datetime.date.today()
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Page setup & CSS
st.set_page_config(page_title="QuickScribe", layout="wide")
st.markdown("""
<style>
.note-card-display { border:1px solid #eee; border-radius:8px; margin-bottom:0.5rem; overflow:hidden; box-shadow:2px 2px 5px rgba(0,0,0,0.1); }
.note-banner-display { height:10px; width:100%; }
.note-content-display { padding:0.5rem 1rem 1rem 1rem; }
.note-heading-display { margin:0.5rem 0; font-weight:bold; }
.note-description-display { min-height:20px; }
</style>
""", unsafe_allow_html=True)

# Sidebar: Home/Date + Folders
with st.sidebar:
    st.title("QuickScribe")
    # Home
    if st.button("🏠 Home", type="primary" if st.session_state.view=='home' else "secondary"):
        st.session_state.view = 'home'
        st.session_state.editing_note_id = None
        st.session_state.show_create_note_form = False
        st.rerun()
    # By Date
    if st.button("📅 By Date", type="primary" if st.session_state.view=='date' else "secondary"):
        st.session_state.view = 'date'
        st.session_state.editing_note_id = None
        st.session_state.show_create_note_form = False
        st.rerun()

    st.divider()
    st.subheader("Folders")
    with st.form("new_folder_form", clear_on_submit=True):
        nf = st.text_input("New Folder Name")
        if st.form_submit_button("Add Folder") and nf:
            add_folder(nf)
            st.rerun()
    folders = get_folders()
    for fid, fname in folders:
        c1, c2 = st.columns([0.8, 0.2])
        with c1:
            if st.button(fname, key=f"sel_{fid}"):
                st.session_state.selected_folder_id = fid
                st.session_state.view = 'home'
                st.session_state.editing_note_id = None
                st.session_state.show_create_note_form = False
                st.rerun()
        with c2:
            if st.button("🗑️", key=f"del_{fid}"):
                delete_folder(fid)
                if st.session_state.selected_folder_id == fid:
                    st.session_state.selected_folder_id = None
                st.rerun()

# Main area
st.title("QuickScribe - Your Notes")

if st.session_state.view == 'home':
    current = None
    if st.session_state.selected_folder_id:
        fl = [f for f in folders if f[0] == st.session_state.selected_folder_id]
        current = fl[0][1] if fl else None
    st.header(f"Notes in: {current or 'Home'}")

    # Create Note button
    if not st.session_state.show_create_note_form:
        if st.button("➕ Create Note"):
            st.session_state.show_create_note_form = True
            st.rerun()

    # New Note form
    if st.session_state.show_create_note_form:
        _, fc, _ = st.columns([0.5, 2, 0.5])
        with fc:
            st.subheader("Add a New Note")
            with st.form("new_note_form", clear_on_submit=True):
                nh = st.text_input("Heading", value=st.session_state.new_note_heading_value)
                nd = st_quill(
                    placeholder="Description...",
                    html=True,
                    key=f"quill_{st.session_state.quill_key_suffix}",
                    value=st.session_state.new_note_quill_value
                )
                col1, col2 = st.columns(2)
                with col1:
                    bc = st.color_picker("Banner Color", value='#FFFFE0')
                with col2:
                    boc = st.color_picker("Body Color", value='#FFFFFF')
                if st.form_submit_button("Add Note"):
                    if nh:
                        add_note(nh, nd,
                                 folder_id=st.session_state.selected_folder_id,
                                 banner_color=bc,
                                 body_color=boc)
                        st.success("Note added to Home/Folder!")
                        st.session_state.show_create_note_form = False
                        st.session_state.new_note_heading_value = ""
                        st.session_state.new_note_quill_value = ""
                        st.session_state.editing_note_id = None
                        st.session_state.quill_key_suffix += 1
                        st.rerun()
                    else:
                        st.warning("Heading cannot be empty.")

    st.divider()
    notes = get_notes_by_folder(st.session_state.selected_folder_id)

elif st.session_state.view == 'date':
    sd = st.date_input("Select Date", value=st.session_state.selected_date)
    if sd != st.session_state.selected_date:
        st.session_state.selected_date = sd
        st.rerun()
    st.header(f"Notes for: {st.session_state.selected_date}")

    # Create Note in date view
    if not st.session_state.show_create_note_form:
        if st.button("➕ Create Note"):
            st.session_state.show_create_note_form = True
            st.rerun()

    # Date-note form
    if st.session_state.show_create_note_form:
        _, fc, _ = st.columns([0.5, 2, 0.5])
        with fc:
            st.subheader("Add a New Note")
            with st.form("new_note_form_date", clear_on_submit=True):
                nh = st.text_input("Heading", value=st.session_state.new_note_heading_value)
                nd = st_quill(
                    placeholder="Description...",
                    html=True,
                    key=f"quill_date_{st.session_state.quill_key_suffix}",
                    value=st.session_state.new_note_quill_value
                )
                c1, c2 = st.columns(2)
                with c1:
                    bc = st.color_picker("Banner Color", value='#FFFFE0')
                with c2:
                    boc = st.color_picker("Body Color", value='#FFFFFF')
                if st.form_submit_button("Add Note"):
                    if nh:
                        add_note(nh, nd,
                                 folder_id=None,
                                 banner_color=bc,
                                 body_color=boc,
                                 note_date=st.session_state.selected_date.isoformat())
                        st.success("Note added to date!")
                        st.session_state.show_create_note_form = False
                        st.session_state.new_note_heading_value = ""
                        st.session_state.new_note_quill_value = ""
                        st.session_state.editing_note_id = None
                        st.session_state.quill_key_suffix += 1
                        st.rerun()
                    else:
                        st.warning("Heading cannot be empty.")

    st.divider()
    notes = get_notes_by_date(st.session_state.selected_date.isoformat())

# Display notes list
if not notes:
    st.info("No notes found.")
else:
    cols = st.columns(3)
    for i, (nid, hd, desc, banner, body) in enumerate(notes):
        col = cols[i % 3]
        with col:
            if st.session_state.editing_note_id == nid:
                with st.form(f"edit_{nid}"):
                    st.markdown(f'<div style="background-color:{banner};height:10px;margin-bottom:0.5rem;"></div>', unsafe_allow_html=True)
                    eh = st.text_input("Heading", value=hd)
                    ed = st_quill(value=desc or "", html=True)
                    e1, e2 = st.columns(2)
                    with e1:
                        eb = st.color_picker("Banner Color", value=banner)
                    with e2:
                        eboc = st.color_picker("Body Color", value=body)
                    save_col, cancel_col = st.columns(2)
                    with save_col:
                        if st.form_submit_button("Save"):
                            update_note(nid, eh, ed, eb, eboc)
                            st.session_state.editing_note_id = None
                            st.success("Saved!")
                            st.rerun()
                    with cancel_col:
                        if st.form_submit_button("Cancel"):
                            st.session_state.editing_note_id = None
                            st.rerun()
            else:
                safe_h = html.escape(hd)
                safe_d = re.sub(r'<script.*?>.*?</script>', '', desc or "",
                                flags=re.IGNORECASE|re.DOTALL)
                card = f"""
                <div class="note-card-display" style="background-color:{body};">
                  <div class="note-banner-display" style="background-color:{banner};"></div>
                  <div class="note-content-display" style="color:{get_text_color(body)};">
                    <h3 class="note-heading-display">{safe_h}</h3>
                    <div class="note-description-display">{safe_d}</div>
                  </div>
                </div>
                """
                st.markdown(card, unsafe_allow_html=True)
                btn_edit, btn_del = st.columns(2)
                with btn_edit:
                    if st.button("✏️ Edit", key=f"ed_{nid}"):
                        st.session_state.editing_note_id = nid
                        st.rerun()
                with btn_del:
                    if st.button("🗑️ Delete", key=f"dl_{nid}"):
                        delete_note(nid)
                        st.success("Deleted!")
                        st.rerun()
