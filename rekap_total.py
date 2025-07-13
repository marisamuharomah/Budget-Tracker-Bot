from fpdf import FPDF
import mysql.connector
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

def koneksi():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

def laporan_bulanan(kode_rekap_input, user_id):
    query = """
    SELECT 
        k.nama_kategori,
        SUM(r.total_perkategori) AS total_kategori
    FROM 
        rekap_perkategori r
    JOIN 
        kategori k ON r.kategori_id = k.id
    WHERE 
        r.kode_rekap = %s
        AND r.user_id = %s
    GROUP BY 
        k.nama_kategori
    ORDER BY
        k.nama_kategori
    """

    try:
        conn = koneksi()
        cursor = conn.cursor()
        cursor.execute(query, (kode_rekap_input, user_id))
        rows = cursor.fetchall()

        if not rows:
            return False, "Tidak ada data pengeluaran untuk periode tersebut"

        total_semua = sum(row[1] for row in rows)
        tanggal_rekap = datetime.now().strftime("%d %B %Y")

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        # Header Judul
        pdf.set_font("Arial", style="B", size=16)
        pdf.cell(200, 10, f"Laporan Pengeluaran\nPeriode {kode_rekap_input}", ln=True, align="C")
        pdf.cell(200, 10, "By Budget Tracker Bot", ln=True, align="C")
        pdf.ln(10)

        # Tanggal
        pdf.set_font("Arial", size=11)
        pdf.cell(200, 10, f"Tanggal mencetak laporan: {tanggal_rekap}", ln=True)
        pdf.ln(5)

        # Tabel Rekap Per Kategori
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(80, 10, "Kategori", 1)
        pdf.cell(60, 10, "Total", 1)
        pdf.ln()

        pdf.set_font("Arial", size=11)
        for nama_kategori, total in rows:
            pdf.cell(80, 10, nama_kategori, 1)
            pdf.cell(60, 10, f"Rp {total:,}", 1)
            pdf.ln()

        pdf.ln(5)
        # Total Semua Kategori
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(80, 10, "Total Pengeluaran", 1)
        pdf.cell(60, 10, f"Rp {total_semua:,}", 1)

        # Simpan PDF
        output_filename = f"Rekap Pengeluaran Bulan {kode_rekap_input}.pdf"
        pdf.output(output_filename)
        return True, output_filename

    except mysql.connector.Error as err:
        print(f"Error MySQL: {err}")
        return False, f"Error database: {err}"
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


 