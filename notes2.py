import streamlit as st
import sqlite3
from streamlit_quill import st_quill
import re
import html  # For escaping heading

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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            heading TEXT NOT NULL,
            description TEXT,
            folder_id INTEGER,
            color TEXT DEFAULT '#FFFFE0',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            body_color TEXT DEFAULT '#FFFFFF',
            FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE
        )
    """)
    try:
        cursor.execute("ALTER TABLE notes ADD COLUMN body_color TEXT DEFAULT '#FFFFFF'")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            st.warning(f"Could not add body_color column: {e}")
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

def add_note(heading, description, folder_id=None, banner_color='#FFFFE0', body_color='#FFFFFF'):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cleaned_description = description
    if cleaned_description is None or cleaned_description.strip() in ["", "<p><br></p>"]:
        cleaned_description = ""
    cursor.execute(
        "INSERT INTO notes (heading, description, folder_id, color, body_color) VALUES (?, ?, ?, ?, ?)",
        (heading, cleaned_description, folder_id, banner_color, body_color)
    )
    conn.commit()
    conn.close()

def get_notes_by_folder(folder_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        if folder_id is None:
            cursor.execute("SELECT id, heading, description, color, body_color FROM notes WHERE folder_id IS NULL ORDER BY created_at DESC")
        else:
            cursor.execute("SELECT id, heading, description, color, body_color FROM notes WHERE folder_id = ? ORDER BY created_at DESC", (folder_id,))
        notes = cursor.fetchall()
    except sqlite3.OperationalError as e:
        if "no such column: body_color" in str(e).lower():
            if folder_id is None:
                cursor.execute("SELECT id, heading, description, color FROM notes WHERE folder_id IS NULL ORDER BY created_at DESC")
            else:
                cursor.execute("SELECT id, heading, description, color FROM notes WHERE folder_id = ? ORDER BY created_at DESC", (folder_id,))
            notes_old = cursor.fetchall()
            notes = [(n[0], n[1], n[2], n[3], '#FFFFFF') for n in notes_old]
        else:
            raise
    conn.close()
    return notes

def update_note(note_id, heading, description, banner_color, body_color):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cleaned_description = description
    if cleaned_description is None or cleaned_description.strip() in ["", "<p><br></p>"]:
        cleaned_description = ""
    cursor.execute(
        "UPDATE notes SET heading = ?, description = ?, color = ?, body_color = ? WHERE id = ?",
        (heading, cleaned_description, banner_color, body_color, note_id)
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

# Initialize Session State
if 'editing_note_id' not in st.session_state:
    st.session_state.editing_note_id = None
if 'selected_folder_id' not in st.session_state:
    st.session_state.selected_folder_id = None
if 'show_create_note_form' not in st.session_state:
    st.session_state.show_create_note_form = False
if "new_note_heading_value" not in st.session_state:
    st.session_state["new_note_heading_value"] = ""
if "new_note_quill_value" not in st.session_state:
    st.session_state["new_note_quill_value"] = ""
if 'quill_key_suffix' not in st.session_state:
    st.session_state.quill_key_suffix = 0

# Streamlit Page Setup
st.set_page_config(page_title="QuickScribe", layout="wide")

# Inject Custom CSS
st.markdown("""
<style>
.note-card-display {
    border: 1px solid #eee;
    border-radius: 8px;
    margin-bottom: 0.5rem;
    word-wrap: break-word;
    overflow: hidden;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
}
.note-banner-display {
    height: 10px; width: 100%; margin: 0; padding: 0; line-height: 10px;
}
.note-content-display {
    padding: 0.5rem 1rem 1rem 1rem;
}
.note-heading-display {
    margin-top: 0.5rem; margin-bottom: 0.5rem; padding: 0; font-weight: bold;
}
.note-description-display {
    min-height: 20px;
}
</style>
""", unsafe_allow_html=True)

# Sidebar: Folder Management
with st.sidebar:
    st.title("Folders")
    with st.form("new_folder_form", clear_on_submit=True):
        new_folder_name = st.text_input("New Folder Name")
        add_folder_submitted = st.form_submit_button("Add Folder")
        if add_folder_submitted and new_folder_name:
            add_folder(new_folder_name)
            st.rerun()

    st.divider()
    folders = get_folders()

    if st.button("🏠 Home", use_container_width=True, type="secondary" if st.session_state.selected_folder_id is None else "primary"):
        st.session_state.selected_folder_id = None
        st.session_state.editing_note_id = None
        st.session_state["new_note_heading_value"] = ""
        st.session_state["new_note_quill_value"] = ""
        st.session_state.show_create_note_form = False
        st.session_state.quill_key_suffix += 1
        st.rerun()

    st.write("Your Folders:")
    for folder_id, folder_name in folders:
        folder_cols = st.columns([0.7, 0.3])
        with folder_cols[0]:
            if st.button(folder_name, key=f"select_folder_{folder_id}", use_container_width=True, type="secondary" if st.session_state.selected_folder_id == folder_id else "primary"):
                st.session_state.selected_folder_id = folder_id
                st.session_state.editing_note_id = None
                st.session_state["new_note_heading_value"] = ""
                st.session_state["new_note_quill_value"] = ""
                st.session_state.show_create_note_form = False
                st.session_state.quill_key_suffix += 1
                st.rerun()
        with folder_cols[1]:
            if st.button("🗑️", key=f"delete_folder_{folder_id}", help=f"Delete folder '{folder_name}'"):
                delete_folder(folder_id)
                if st.session_state.selected_folder_id == folder_id:
                    st.session_state.selected_folder_id = None
                st.session_state["new_note_heading_value"] = ""
                st.session_state["new_note_quill_value"] = ""
                st.session_state.show_create_note_form = False
                st.session_state.quill_key_suffix += 1
                st.rerun()

# Main Area
st.title("QuickScribe - Your Notes")

current_folder_name = "Home"
if st.session_state.selected_folder_id is not None:
    selected_folder = next((f for f in folders if f[0] == st.session_state.selected_folder_id), None)
    if selected_folder:
        current_folder_name = selected_folder[1]
    else:
        st.session_state.selected_folder_id = None
        st.rerun()

st.header(f"Notes in: {current_folder_name}")

# "Create Note" Button
if not st.session_state.show_create_note_form:
    if st.button("➕ Create Note"):
        st.session_state.show_create_note_form = True
        st.rerun()

# New Note Form (only if button clicked)
if st.session_state.show_create_note_form:
    _, form_col, _ = st.columns([0.5, 2, 0.5])
    with form_col:
        st.header("Add a New Note")
        with st.form("new_note_form", clear_on_submit=True):
            note_heading = st.text_input("Note Heading", max_chars=100, value=st.session_state["new_note_heading_value"], key="new_note_heading")
            note_description_html = st_quill(
                placeholder="Enter note description...", html=True,
                key=f"new_note_quill_{st.session_state.quill_key_suffix}",
                value=st.session_state["new_note_quill_value"]
            )
            col1, col2 = st.columns(2)
            with col1:
                new_banner_color = st.color_picker("Banner Color", value='#FFFFE0')
            with col2:
                new_body_color = st.color_picker("Body Color", value='#FFFFFF')

            submitted = st.form_submit_button("Add Note")
            if submitted:
                if note_heading:
                    add_note(note_heading, note_description_html, st.session_state.selected_folder_id, new_banner_color, new_body_color)
                    st.success(f"Note added to '{current_folder_name}'!")
                    st.session_state["new_note_heading_value"] = ""
                    st.session_state["new_note_quill_value"] = ""
                    st.session_state.editing_note_id = None
                    st.session_state.show_create_note_form = False
                    st.session_state.quill_key_suffix += 1
                    st.rerun()
                else:
                    st.warning("Note heading cannot be empty.")

st.divider()

# Display Notes
notes = get_notes_by_folder(st.session_state.selected_folder_id)

if not notes:
    st.info(f"No notes in '{current_folder_name}'. Add one above!")
else:
    num_columns = 3
    cols = st.columns(num_columns)
    for i, note_data in enumerate(notes):
        note_id, heading, description, banner_color, body_color = note_data

        col_index = i % num_columns
        with cols[col_index]:
            if st.session_state.editing_note_id == note_id:
                with st.form(f"edit_form_{note_id}"):
                    st.markdown(f'<div style="background-color:{banner_color}; height:10px; margin-bottom: 0.5rem;"></div>', unsafe_allow_html=True)
                    st.subheader("Edit Note")
                    edited_heading = st.text_input("Heading", value=heading, key=f"edit_head_{note_id}")
                    edited_description_html = st_quill(value=description if description else "", html=True, key=f"edit_quill_{note_id}")

                    ecol1, ecol2 = st.columns(2)
                    with ecol1:
                        edited_banner_color = st.color_picker("Banner Color", value=banner_color, key=f"edit_banner_color_{note_id}")
                    with ecol2:
                        edited_body_color = st.color_picker("Body Color", value=body_color, key=f"edit_body_color_{note_id}")

                    edit_cols_btns = st.columns(2)
                    with edit_cols_btns[0]:
                        save_button = st.form_submit_button("Save")
                    with edit_cols_btns[1]:
                        cancel_button = st.form_submit_button("Cancel")

                    if save_button:
                        if edited_heading:
                            update_note(note_id, edited_heading, edited_description_html, edited_banner_color, edited_body_color)
                            st.session_state.editing_note_id = None
                            st.success("Note updated successfully!")
                            st.rerun()
                        else:
                            st.warning("Heading cannot be empty.")
                    if cancel_button:
                        st.session_state.editing_note_id = None
                        st.rerun()
            else:
                safe_heading = html.escape(heading)
                safe_description = description if description else ""
                safe_description = re.sub(r'<script.*?>.*?</script>', '', safe_description, flags=re.IGNORECASE | re.DOTALL)

                card_html = f"""
                <div class="note-card-display" style="background-color: {body_color};">
                    <div class="note-banner-display" style="background-color: {banner_color};"></div>
                    <div class="note-content-display">
                        <h3 class="note-heading-display">{safe_heading}</h3>
                        <div class="note-description-display">{safe_description}</div>
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)

                button_cols = st.columns(2)
                with button_cols[0]:
                    if st.button("✏️ Edit", key=f"edit_note_{note_id}"):
                        st.session_state.editing_note_id = note_id
                        st.session_state["new_note_heading_value"] = ""
                        st.session_state["new_note_quill_value"] = ""
                        st.session_state.quill_key_suffix += 1
                        st.session_state.show_create_note_form = False
                        st.rerun()
                with button_cols[1]:
                    if st.button("🗑️ Delete", key=f"delete_note_{note_id}"):
                        delete_note(note_id)
                        st.success("Note deleted successfully!")
                        st.rerun()
