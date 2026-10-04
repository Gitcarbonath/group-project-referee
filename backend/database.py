import sqlite3

DATABASE = "referee.db"


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            member TEXT NOT NULL,
            update_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id)
                REFERENCES projects(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (project_id)
                REFERENCES projects(id)
        )
    """)

    connection.commit()
    connection.close()


def create_project(name):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO projects (name)
        VALUES (?)
    """, (name,))

    project_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return project_id


def get_project(project_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name
        FROM projects
        WHERE id = ?
    """, (project_id,))

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return dict(row)


def get_projects():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name
        FROM projects
        ORDER BY id DESC
    """)

    projects = [dict(row) for row in cursor.fetchall()]

    connection.close()

    return projects


def add_member(project_id, name):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id
        FROM project_members
        WHERE project_id = ?
        AND LOWER(name) = LOWER(?)
    """, (project_id, name))

    existing = cursor.fetchone()

    if existing:
        connection.close()
        return existing["id"]

    cursor.execute("""
        INSERT INTO project_members
        (project_id, name)
        VALUES (?, ?)
    """, (project_id, name))

    member_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return member_id


def get_members(project_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name
        FROM project_members
        WHERE project_id = ?
        ORDER BY id ASC
    """, (project_id,))

    members = [dict(row) for row in cursor.fetchall()]

    connection.close()

    return members


def delete_member(project_id, member_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM project_members
        WHERE id = ?
        AND project_id = ?
    """, (member_id, project_id))

    connection.commit()
    connection.close()


def add_update(project_id, member, update_text):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO updates
        (
            project_id,
            member,
            update_text
        )
        VALUES (?, ?, ?)
    """, (project_id, member, update_text))

    update_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return update_id


def get_updates(project_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            member,
            update_text,
            created_at
        FROM updates
        WHERE project_id = ?
        ORDER BY created_at ASC
    """, (project_id,))

    updates = [dict(row) for row in cursor.fetchall()]

    connection.close()

    return updates