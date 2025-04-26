import streamlit as st
import sqlite3
from streamlit_quill import st_quill
import re # Import regex for cleaning description

# Database setup
DB_FILE = "notes.db"

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
            FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

# Folder Functions
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

# Note Functions
def add_note(heading, description, folder_id=None, color='#FFFFE0'):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Clean description: Treat None, empty string, or quill's empty paragraph as empty
    cleaned_description = description
    if cleaned_description is None or cleaned_description.strip() == "" or cleaned_description.strip() == "<p><br></p>":
        cleaned_description = ""

    cursor.execute(
        "INSERT INTO notes (heading, description, folder_id, color) VALUES (?, ?, ?, ?)",
        (heading, cleaned_description, folder_id, color)
    )
    conn.commit()
    conn.close()

def get_notes_by_folder(folder_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if folder_id is None:
        cursor.execute("SELECT id, heading, description, color FROM notes WHERE folder_id IS NULL ORDER BY created_at DESC")
    else:
        cursor.execute("SELECT id, heading, description, color FROM notes WHERE folder_id = ? ORDER BY created_at DESC", (folder_id,))
    notes = cursor.fetchall()
    conn.close()
    return notes

def update_note(note_id, heading, description, color):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Clean description on update as well
    cleaned_description = description
    if cleaned_description is None or cleaned_description.strip() == "" or cleaned_description.strip() == "<p><br></p>":
        cleaned_description = ""
    cursor.execute(
        "UPDATE notes SET heading = ?, description = ?, color = ? WHERE id = ?",
        (heading, cleaned_description, color, note_id)
    )
    conn.commit()
    conn.close()

def delete_note(note_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Initialize session state
if 'editing_note_id' not in st.session_state:
    st.session_state.editing_note_id = None
if 'selected_folder_id' not in st.session_state:
    st.session_state.selected_folder_id = None
# Initialize form values in session state if they don't exist
if "new_note_heading_value" not in st.session_state:
    st.session_state["new_note_heading_value"] = ""
if "new_note_quill_value" not in st.session_state:
    st.session_state["new_note_quill_value"] = ""
# Initialize dynamic key counter for Quill editor
if 'quill_key_suffix' not in st.session_state:
    st.session_state.quill_key_suffix = 0


# Streamlit Page Setup
st.set_page_config(page_title="QuickScribe", layout="wide")

# Sidebar - Folder Management
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
        # Clear form fields and increment quill key
        st.session_state["new_note_heading_value"] = ""
        st.session_state["new_note_quill_value"] = ""
        st.session_state.quill_key_suffix += 1
        st.rerun()

    st.write("Your Folders:")
    for folder_id, folder_name in folders:
        folder_cols = st.columns([0.7, 0.3])
        with folder_cols[0]:
            if st.button(folder_name, key=f"select_folder_{folder_id}", use_container_width=True, type="secondary" if st.session_state.selected_folder_id == folder_id else "primary"):
                st.session_state.selected_folder_id = folder_id
                st.session_state.editing_note_id = None
                # Clear form fields and increment quill key
                st.session_state["new_note_heading_value"] = ""
                st.session_state["new_note_quill_value"] = ""
                st.session_state.quill_key_suffix += 1
                st.rerun()
        with folder_cols[1]:
            if st.button("🗑️", key=f"delete_folder_{folder_id}", help=f"Delete folder '{folder_name}'"):
                delete_folder(folder_id)
                if st.session_state.selected_folder_id == folder_id:
                    st.session_state.selected_folder_id = None
                    # Optionally clear form if deleting the current folder
                    st.session_state["new_note_heading_value"] = ""
                    st.session_state["new_note_quill_value"] = ""
                    st.session_state.quill_key_suffix += 1
                st.rerun()

# Main Area - Notes
st.title("QuickScribe - Your Notes")

current_folder_name = "Home"
if st.session_state.selected_folder_id is not None:
    selected_folder = next((f for f in folders if f[0] == st.session_state.selected_folder_id), None)
    if selected_folder:
        current_folder_name = selected_folder[1]
    else: # If folder was deleted while selected
        st.session_state.selected_folder_id = None
        st.rerun()

st.header(f"Notes in: {current_folder_name}")

# Form to Add New Note
_, form_col, _ = st.columns([0.5, 2, 0.5])
with form_col:
    st.header("Add a New Note")
    with st.form("new_note_form", clear_on_submit=True):
        note_heading = st.text_input("Note Heading", max_chars=100, value=st.session_state["new_note_heading_value"], key="new_note_heading")
        # Use dynamic key for Quill editor
        note_description_html = st_quill(
            placeholder="Enter note description...",
            html=True,
            key=f"new_note_quill_{st.session_state.quill_key_suffix}",
            value=st.session_state["new_note_quill_value"]
        )
        new_note_color = st.color_picker("Note Color", value='#FFFFE0', key="new_note_color")
        submitted = st.form_submit_button("Add Note")

        if submitted:
            if note_heading:
                add_note(note_heading, note_description_html, st.session_state.selected_folder_id, new_note_color)
                st.success(f"Note added to '{current_folder_name}'!")
                # Explicitly clear session state values for the form
                st.session_state["new_note_heading_value"] = ""
                st.session_state["new_note_quill_value"] = ""
                st.session_state.editing_note_id = None # Ensure not in edit mode
                # Increment dynamic key to force Quill re-render on next load
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
    for i, note in enumerate(notes):
        note_id, heading, description, color = note
        col_index = i % num_columns
        with cols[col_index]:
            # Use a div with dynamic style for background color
            container_style = f"""
                border: 1px solid #e6e6e6;
                border-radius: 0.5rem;
                padding: 1rem;
                margin-bottom: 1rem;
                background-color: {color};
                /* Removed min-height */
                word-wrap: break-word; /* Prevent long text overflow */
            """
            with st.container(): # Outer container for layout
                 st.markdown(f'<div style="{container_style}">', unsafe_allow_html=True) # Start styled div

                 if st.session_state.editing_note_id == note_id:
                     with st.form(f"edit_form_{note_id}"):
                         st.subheader("Edit Note")
                         edited_heading = st.text_input("Heading", value=heading, key=f"edit_head_{note_id}")
                         # Ensure description is not None for Quill editor
                         edited_description_html = st_quill(value=description if description else "", html=True, key=f"edit_quill_{note_id}")
                         edited_color = st.color_picker("Note Color", value=color, key=f"edit_color_{note_id}")

                         edit_cols = st.columns(2)
                         with edit_cols[0]:
                             save_button = st.form_submit_button("Save")
                         with edit_cols[1]:
                             cancel_button = st.form_submit_button("Cancel")

                         if save_button:
                             if edited_heading:
                                 update_note(note_id, edited_heading, edited_description_html, edited_color)
                                 st.session_state.editing_note_id = None
                                 st.success("Note updated successfully!")
                                 st.rerun()
                             else:
                                 st.warning("Heading cannot be empty.")
                         if cancel_button:
                             st.session_state.editing_note_id = None
                             st.rerun()

                 else:
                     st.subheader(heading)
                     # Render description only if it's not empty
                     if description and description.strip() != "":
                         st.markdown(description, unsafe_allow_html=True)
                     else:
                         # Add a non-breaking space to ensure the div takes up space
                         st.markdown("&nbsp;", unsafe_allow_html=True)

                     st.markdown("---") # Add a visual separator before buttons
                     col1, col2 = st.columns(2)
                     with col1:
                         if st.button("✏️ Edit", key=f"edit_btn_{note_id}"):
                             st.session_state.editing_note_id = note_id
                             # Don't increment quill key here, edit form handles its own state
                             st.rerun()
                     with col2:
                         if st.button("🗑️ Delete", key=f"delete_btn_{note_id}"):
                             delete_note(note_id)
                             st.success("Note deleted!")
                             st.rerun()

                 st.markdown('</div>', unsafe_allow_html=True) # End styled div
