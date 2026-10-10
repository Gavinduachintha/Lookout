"""
config/db.py — PostgreSQL persistence for Trailside sightings.

Schema (run init_db() once to create the table):

    fieldNotes
      id           SERIAL       PRIMARY KEY
      created_at   TIMESTAMPTZ  DEFAULT now()
      user_hint    TEXT         NOT NULL DEFAULT ''
      notes        TEXT         NOT NULL DEFAULT ''
      file_name    TEXT         NOT NULL DEFAULT ''
      mime_type    TEXT         NOT NULL DEFAULT ''
      image_data   BYTEA        NOT NULL

Usage:
    from config.db import init_db, save_sighting, fetch_sightings, delete_sighting
"""

import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def _conn_params() -> dict:
    """
    Read connection details from environment variables so credentials are
    never hard-coded.  Set these in a .env file or your shell before running:

        DB_HOST     (default: localhost)
        DB_PORT     (default: 5432)
        DB_NAME     (default: postgres)
        DB_USER     (default: postgres)
        DB_PASSWORD (required — no default)
    """
    return {
        "host":     os.environ.get("DB_HOST", "localhost"),
        "port":     int(os.environ.get("DB_PORT", 5432)),
        "dbname":   os.environ.get("DB_NAME", "postgres"),
        "user":     os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", "1234"),
    }


@contextmanager
def _get_conn():
    """Yield a psycopg2 connection, commit on success, rollback on error."""
    conn = psycopg2.connect(**_conn_params())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create the fieldNotes table if it doesn't already exist."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS "fieldNotes" (
                    id           SERIAL       PRIMARY KEY,
                    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
                    user_hint    TEXT         NOT NULL DEFAULT '',
                    notes        TEXT         NOT NULL DEFAULT '',
                    file_name    TEXT         NOT NULL DEFAULT '',
                    mime_type    TEXT         NOT NULL DEFAULT '',
                    image_data   BYTEA        NOT NULL DEFAULT ''
                );
            """)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def save_sighting(
    image_bytes: bytes,
    notes: str,
    user_hint: str = "",
    file_name: str = "photo.jpg",
    mime_type: str = "image/jpeg",
) -> int:
    """
    Persist a sighting. Returns the new row id.

    Parameters
    ----------
    image_bytes : bytes
        Raw image bytes (JPEG).
    notes : str
        Field notes returned by the model.
    user_hint : str
        Optional free-text the user typed before identifying.
    file_name : str
        Original file name (for display / download).
    mime_type : str
        MIME type of the image.
    """
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO "fieldNotes"
                    (user_hint, notes, file_name, mime_type, image_data)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    user_hint.strip(),
                    notes.strip(),
                    file_name,
                    mime_type,
                    psycopg2.Binary(image_bytes),
                ),
            )
            return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def fetch_sightings(limit: int = 100) -> list[dict]:
    """
    Return sightings newest-first so the most recent appears at the top of the LogBook.
    image_data is intentionally excluded to keep payloads small;
    use fetch_image() when you need the raw bytes.
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, created_at, user_hint, notes, file_name, mime_type
                FROM   "fieldNotes"
                ORDER  BY created_at DESC, id DESC
                LIMIT  %s;
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def fetch_image(row_id: int) -> bytes | None:
    """Return the raw image bytes for a single sighting, or None if not found."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT image_data FROM "fieldNotes" WHERE id = %s;',
                (row_id,),
            )
            row = cur.fetchone()
            return bytes(row[0]) if row else None


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_sighting(row_id: int) -> None:
    """Remove a single sighting by id."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM "fieldNotes" WHERE id = %s;', (row_id,))
