from datetime import datetime
import mysql.connector
from dotenv import load_dotenv
import os
import re

load_dotenv()

# koneksi database
def koneksi():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )

def normalize_kategori_name(nama_kategori):
    # Lowercase, strip, replace multiple spaces with single, and standardize dash
    nama = nama_kategori.strip().lower()
    nama = re.sub(r'\s+', ' ', nama)
    nama = nama.replace(' - ', '-').replace('–', '-')
    # Capitalize each word (optional, for display)
    nama = ' '.join([w.capitalize() for w in nama.split(' ')])
    return nama

def insert_data_setruk(user_id, nama_kategori, tanggal, total, kode_rekap):
    conn = koneksi()
    cursor = conn.cursor()
    try:
        # Normalisasi nama kategori
        nama_kategori = normalize_kategori_name(nama_kategori)
        # kategori
        cursor.execute("SELECT id FROM kategori WHERE nama_kategori = %s", (nama_kategori,))
        hasil_kategori = cursor.fetchone()
        
        if not hasil_kategori:
            print(f"❌ Kategori '{nama_kategori}' tidak ditemukan dalam database")
            # Insert the category if it doesn't exist
            cursor.execute("INSERT INTO kategori (nama_kategori) VALUES (%s)", (nama_kategori,))
            conn.commit()
            print(f"✅ Kategori '{nama_kategori}' berhasil ditambahkan")
            # Get the new category ID
            cursor.execute("SELECT id FROM kategori WHERE nama_kategori = %s", (nama_kategori,))
            hasil_kategori = cursor.fetchone()
        
        kategori_id = hasil_kategori[0]

        # Ubah tanggal ke format YYYY-MM-DD jika berupa string DD-MM-YYYY
        if isinstance(tanggal, str):
            try:
                tanggal = datetime.strptime(tanggal, "%d-%m-%Y").strftime("%Y-%m-%d")
            except ValueError:
                print(f"❌ Format tanggal tidak valid: {tanggal}")
                return False, None

        # Convert total to integer if it's a string
        if isinstance(total, str):
            try:
                total = int(''.join(filter(str.isdigit, total)))
            except ValueError:
                print(f"❌ Format total tidak valid: {total}")
                return False, None

        # Check if total is None or invalid
        if total is None or total <= 0:
            print(f"❌ Total tidak valid: {total}")
            return False, None

        # Tambahkan tgl_upload
        tgl_upload = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"📝 Mencoba menyimpan data:  user_id={user_id}, kategori_id={kategori_id}, tanggal={tanggal}, total={total}, kode_rekap={kode_rekap}, tgl_upload={tgl_upload}")
        
        cursor.execute("""
            INSERT INTO EKSTRAKSI_SETRUK (user_id, kategori_id, tanggal, total, kode_rekap, tgl_upload)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, kategori_id, tanggal, total, kode_rekap, tgl_upload))
        
        # Get the auto-increment ID
        inserted_id = cursor.lastrowid
        
        conn.commit()
        print("✅ Data berhasil disimpan ke database")
        return True, inserted_id
        
    except mysql.connector.Error as err:
        print(f"❌ Database error: {err}")
        conn.rollback()
        return False, None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        conn.rollback()
        return False, None
    finally:
        cursor.close()
        conn.close()
