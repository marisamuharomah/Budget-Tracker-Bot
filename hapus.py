from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import mysql.connector
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Fungsi untuk koneksi database
def koneksi():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# Fungsi untuk menghapus data berdasarkan user_id, id data, dan total
def hapus_data(user_id, data_id=None):
    """
    Menghapus data berdasarkan ID data
    Args:
        user_id: ID user yang datanya akan dihapus
        data_id: ID data spesifik
    Returns:
        tuple: (success, message, deleted_count)
    """
    try:
        conn = koneksi()
        cursor = conn.cursor(dictionary=True)

        # Query untuk mencari data yang akan dihapus
        if data_id:
            query = """
                SELECT es.id, es.user_id, es.tanggal, k.nama_kategori, es.total, es.kode_rekap 
                FROM ekstraksi_setruk es
                JOIN kategori k ON es.kategori_id = k.id
                WHERE es.user_id = %s AND es.id = %s
            """
            cursor.execute(query, (user_id, data_id))
        else:
            return False, "❌ Minimal harus ada ID data untuk penghapusan", 0
        
        result = cursor.fetchall()
        
        if not result:
            return False, "❌ Tidak ada data yang ditemukan dengan kriteria tersebut", 0
        
        # Simpan kode_rekap untuk penghapusan di rekap_perkategori
        rekap_list = list(set([item['kode_rekap'] for item in result if item['kode_rekap']]))
        
        # Hapus data dari ekstraksi_setruk
        delete_query = "DELETE FROM ekstraksi_setruk WHERE user_id = %s AND id = %s"
        cursor.execute(delete_query, (user_id, data_id))
        
        rows_deleted = cursor.rowcount
        
        # Hapus dari rekap_perkategori untuk kode_rekap yang terkait
        for kode_rekap in rekap_list:
            if kode_rekap:
                delete_rekap_query = "DELETE FROM rekap_perkategori WHERE user_id = %s AND kode_rekap = %s"
                cursor.execute(delete_rekap_query, (user_id, kode_rekap))
        
        conn.commit()
        
        return True, f"{rows_deleted} data berhasil dihapus", rows_deleted
        
    except Exception as e:
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
        return False, f"❌ Gagal menghapus data: {str(e)}", 0
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn.is_connected():
            conn.close()

# Fungsi baru untuk menghapus berdasarkan ID data
async def hapus_setruk_by_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Ambil ID dari context
    data_id = context.user_data.get("pending_delete_id")
    if not data_id:
        await update.message.reply_text("❌ ID data tidak valid atau tidak ditemukan.")
        return

    try:
        conn = koneksi()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT es.id, es.user_id, es.tanggal, k.nama_kategori, es.total, es.kode_rekap, es.tgl_upload
            FROM ekstraksi_setruk es
            JOIN kategori k ON es.kategori_id = k.id
            WHERE es.user_id = %s AND es.id = %s
        """
        cursor.execute(query, (user_id, data_id))
        result = cursor.fetchall()

        if not result:
            await update.message.reply_text(
                "❌ Maaf, tidak ada setruk dengan ID tersebut.\n"
                "Silahkan masukkan ID kembali."
                )
            return

        # Simpan data di context untuk konfirmasi
        context.user_data["delete_candidates"] = result

        keyboard = [
            [InlineKeyboardButton("✅ Ya, hapus", callback_data="confirm_delete")],
            [InlineKeyboardButton("❌ Batal", callback_data="cancel_delete")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        item = result[0]
        # Format tanggal ke dd-mm-yyyy
        try:
            tanggal_obj = item['tanggal']
            if isinstance(tanggal_obj, str):
                tanggal_obj = datetime.strptime(tanggal_obj, '%Y-%m-%d')
            tanggal_str = tanggal_obj.strftime('%d-%m-%Y')
        except Exception:
            tanggal_str = str(item['tanggal'])
        # Format tgl_upload ke dd-mm-yyyy HH:MM:SS
        try:
            tgl_upload_obj = item['tgl_upload']
            if isinstance(tgl_upload_obj, str):
                tgl_upload_obj = datetime.strptime(tgl_upload_obj, '%Y-%m-%d %H:%M:%S')
            tgl_upload_str = tgl_upload_obj.strftime('%d-%m-%Y %H:%M:%S')
        except Exception:
            tgl_upload_str = str(item['tgl_upload'])
        text = f"Setruk ditemukan:\nID: {item['id']}\nTanggal: {tanggal_str}\nKategori: {item['nama_kategori']}\nTotal: Rp {item['total']:,}\nTanggal Input Setruk: {tgl_upload_str}\n\nApakah kamu yakin ingin menghapus data ini?"

        await update.message.reply_text(text, reply_markup=reply_markup)

    except Exception as e:
        await update.message.reply_text(f"❌ Terjadi kesalahan: {str(e)}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

# Konfirmasi hapus
async def konfirmasi_hapus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_delete":
        delete_list = context.user_data.get("delete_candidates", [])
        if not delete_list:
            await query.edit_message_text("❌ Tidak ada data untuk dihapus.")
            return

        try:
            user_id = delete_list[0]['user_id']
            
            # Hapus berdasarkan ID spesifik
            success, message, deleted_count = hapus_data(
                user_id=user_id,
                data_id=delete_list[0]['id']
            )
            
            if success:
                await query.edit_message_text(f"✅ {message}")
                
                # Update rekap setelah penghapusan
                try:
                    from rekap_perkategori import insert_rekap_perkategori
                    success_rekap, message_rekap = insert_rekap_perkategori(user_id=user_id)
                    if success_rekap:
                        await query.message.reply_text("✅ Rekap kategori berhasil diperbarui.\n Kamu bisa kirim /start lagi untuk ke menu awal.")
                    else:
                        await query.message.reply_text(f"⚠️ Gagal update rekap: {message_rekap}")
                except Exception as e:
                    await query.message.reply_text(f"⚠️ Gagal update rekap: {e}")
            else:
                await query.edit_message_text(f"❌ {message}")

        except Exception as e:
            await query.edit_message_text(f"❌ Gagal menghapus data: {str(e)}")
        finally:
            context.user_data.pop("delete_candidates", None)

    elif query.data == "cancel_delete":
        await query.edit_message_text("Penghapusan dibatalkan.")
        context.user_data.pop("delete_candidates", None)

