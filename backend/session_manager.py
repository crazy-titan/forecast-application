import uuid
import os
import tempfile
import shutil
from typing import Dict, Any

# In-memory session storage (suitable for development)
_sessions: Dict[str, Dict[str, Any]] = {}

def create_session() -> str:
    """Create a new session with a unique temporary folder."""
    session_id = str(uuid.uuid4())
    folder = tempfile.mkdtemp(prefix="chaincast_")
    _sessions[session_id] = {
        "folder": folder,
        "df_path": None,          # path to uploaded CSV
        "mapping": None,          # column mapping dict
        "validation": None,       # validation results
        "results": None,          # forecast results
        "dataset_name": None,     # original filename
    }
    return session_id

def get_session(session_id: str) -> Dict[str, Any]:
    """Retrieve session data. Raises KeyError if not found."""
    if session_id not in _sessions:
        raise KeyError(f"Session {session_id} not found")
    return _sessions[session_id]

def update_session(session_id: str, key: str, value: Any) -> None:
    """Update a specific key in the session."""
    sess = get_session(session_id)
    sess[key] = value

def delete_session(session_id: str) -> None:
    """Delete session and remove its temporary folder."""
    sess = _sessions.pop(session_id, None)
    if sess and sess.get("folder") and os.path.exists(sess["folder"]):
        shutil.rmtree(sess["folder"], ignore_errors=True)