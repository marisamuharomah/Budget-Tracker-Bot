import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

def koneksi():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )

def insert_rekap_perkategori(user_id=None):
    conn = None
    cursor = None
    try:
        conn = koneksi()
        cursor = conn.cursor()

        # Cek data yang ada di ekstraksi_setruk
        if user_id:
            check_query = "SELECT COUNT(*) FROM ekstraksi_setruk WHERE user_id = %s"
            cursor.execute(check_query, (user_id,))
            count = cursor.fetchone()[0]
            print(f"📊 User {user_id} memiliki {count} data di ekstraksi_setruk")
        else:
            check_query = "SELECT user_id, COUNT(*) FROM ekstraksi_setruk GROUP BY user_id"
            cursor.execute(check_query)
            user_counts = cursor.fetchall()
            print(f"📊 Total data per user: {user_counts}")

        # INSERT ... ON DUPLICATE KEY UPDATE untuk menghindari REPLACE INTO
        insert_query = """
        INSERT INTO rekap_perkategori 
            (user_id, kode_rekap, kategori_id, nama_kategori, total_perkategori)
        SELECT 
            es.user_id,
            es.kode_rekap,
            es.kategori_id,
            k.nama_kategori,
            SUM(es.total) AS total_perkategori
        FROM ekstraksi_setruk es
        JOIN kategori k ON es.kategori_id = k.id
        """

        if user_id:
            insert_query += " WHERE es.user_id = %s"
            insert_params = (user_id,)
            print(f"🔍 Query untuk user {user_id}")
        else:
            insert_params = None
            print("🔍 Query untuk semua user")

        insert_query += """
        GROUP BY es.user_id, es.kode_rekap, es.kategori_id, k.nama_kategori
        ON DUPLICATE KEY UPDATE 
            nama_kategori = VALUES(nama_kategori),
            total_perkategori = VALUES(total_perkategori)
        """

        print(f"📝 Query: {insert_query}")
        print(f"📝 Parameters: {insert_params}")

        if insert_params:
            cursor.execute(insert_query, insert_params)
        else:
            cursor.execute(insert_query)

        conn.commit()
        rows = cursor.rowcount
        print(f"✅ {rows} baris berhasil diproses.")

        # Verifikasi hasil
        if user_id:
            verify_query = "SELECT COUNT(*) FROM rekap_perkategori WHERE user_id = %s"
            cursor.execute(verify_query, (user_id,))
            verify_count = cursor.fetchone()[0]

            check_es_query = "SELECT COUNT(*) FROM ekstraksi_setruk WHERE user_id = %s"
            cursor.execute(check_es_query, (user_id,))
            es_count = cursor.fetchone()[0]

            print(f"✅ Verifikasi: {verify_count} data di rekap_perkategori, {es_count} data di ekstraksi_setruk untuk user {user_id}")
        else:
            verify_query = "SELECT user_id, COUNT(*) FROM rekap_perkategori GROUP BY user_id"
            cursor.execute(verify_query)
            verify_result = cursor.fetchall()
            print(f"✅ Verifikasi hasil: {verify_result}")

        if user_id:
            return True, f"Data berhasil diproses: {rows} baris. Verifikasi: {verify_count} di rekap_perkategori, {es_count} di ekstraksi_setruk."
        else:
            return True, f"Data berhasil diproses: {rows} baris. Verifikasi: {verify_result}"

    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        return False, f"❌ Terjadi kesalahan: {err}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def update_all_users_rekap():
    """Fungsi khusus untuk update rekap semua user"""
    return insert_rekap_perkategori(user_id=None)
