# database.py
import sqlite3
import os

DB_FILE = "videos.db"

def create_connection():
    """Cria uma conexão com o banco de dados SQLite."""
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        return conn
    except sqlite3.Error as e:
        print(e)
    return conn

def create_table(conn):
    """Cria a tabela de vídeos se ela não existir."""
    sql_create_videos_table = """
    CREATE TABLE IF NOT EXISTS videos (
        id TEXT PRIMARY KEY,
        original_name TEXT NOT NULL,
        original_ext TEXT NOT NULL,
        mime_type TEXT,
        size_bytes INTEGER,
        duration_sec REAL,
        fps REAL,
        width INTEGER,
        height INTEGER,
        filter TEXT,
        created_at TEXT NOT NULL,
        path_original TEXT NOT NULL,
        path_processed TEXT
    );
    """
    try:
        c = conn.cursor()
        c.execute(sql_create_videos_table)
    except sqlite3.Error as e:
        print(e)

def init_db():
    """Inicializa o banco de dados e a tabela."""
    if not os.path.exists(DB_FILE):
        print("Criando banco de dados...")
        conn = create_connection()
        if conn is not None:
            create_table(conn)
            conn.close()
            print("Banco de dados e tabela 'videos' criados com sucesso.")
        else:
            print("Erro! Não foi possível criar a conexão com o banco de dados.")
    else:
        print("Banco de dados já existente.")

if __name__ == '__main__':
    init_db()