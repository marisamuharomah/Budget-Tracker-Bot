import os
from dotenv import load_dotenv 
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
    CallbackQueryHandler,
)
from paddleocr import PaddleOCR
import re
from datetime import datetime

#--DATABASE IMPORT
from datasql import insert_receipt_data
from rekap_perkategori import insert_rekap_perkategori
from hapus import hapus_setruk_total, konfirmasi_hapus
from rekap_total import laporan_bulanan

# Bot setup dan token API
load_dotenv()
bot_token = os.getenv('BOT_TOKEN')

app = ApplicationBuilder().token(bot_token).build()

# State ConversationHandler
pilih_kategori, WAITING_PHOTO, WAITING_REKAP_CODE, WAITING_DELETE_CODE = range(4)

# Inisialisasi OCR
ocr = PaddleOCR(use_angle_cls=True, lang='latin')

# Start command
async def start (update: Update, context: ContextTypes.DEFAULT_TYPE):
    #buttons 
    keyboard = [
        [InlineKeyboardButton("📝 Input Setruk Baru", callback_data='input_setruk')],
        [InlineKeyboardButton("📊 Lihat Rekap Pengeluaran", callback_data='lihat_rekap')],
        [InlineKeyboardButton("🗑️ Hapus Setruk", callback_data='hapus_setruk')],
        [InlineKeyboardButton("❌ Batal", callback_data='batal')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Hai <b>{update.effective_user.first_name}</b>!👋\n"
        "Selamat datang di <b>Budget Tracker Bot</b>.\n\n"
        "Silakan pilih menu di bawah ini:\n"
        "1. 📝 Input Setruk Baru - untuk mencatat pengeluaran baru\n"
        "2. 📊 Lihat Rekap - untuk melihat laporan pengeluaran\n"
        "3. 🗑️ Hapus Setruk - untuk menghapus setruk\n"
        "4. ❌ Batal - untuk membatalkan proses\n\n "
        "Atau gunakan command:\n"
        "• /start - untuk memulai input setruk baru\n"
        "• /rekap - untuk melihat laporan pengeluaran\n"
        "• /hapus [total] - untuk menghapus setruk\n"
        "• /batal - untuk membatalkan operasi",
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    return pilih_kategori

# Pilih kategori
async def pilih_kategori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    categories = {
        "1": "Kebutuhan Sehari-hari",
        "2": "Transportasi",
        "3": "Makan & Minum",
        "4": "Lainnya"
    }

    chosen = categories.get(text)
    if chosen:
        context.user_data["kategori"] = chosen
        await update.message.reply_text(f"Kategori Setruk: {chosen}\nSilahkan kirim foto setruk kamu.")
        return WAITING_PHOTO
    else:
        await update.message.reply_text("Pilihan tidak valid. Pilih angka 1-4.")
        return pilih_kategori

#---PROSES OCR---
#untuk membaca setruk perbaris
def group_lines(lines, threshold=10):
    lines.sort(key=lambda x: x[0][0][1])
    grouped, current = [], []
    for line in lines:
        y = line[0][0][1]
        if not current or abs(y - current[-1][0][0][1]) < threshold:
            current.append(line)
        else:
            grouped.append(current)
            current = [line]
    if current:
        grouped.append(current)
    return grouped

# Dictionary untuk konversi nama bulan ke angka
MONTH_DICT = {
    # Bahasa Indonesia
    'januari': '01', 'jan': '01', 'jan.': '01',
    'februari': '02', 'feb': '02', 'feb.': '02',
    'maret': '03', 'mar': '03', 'mar.': '03',
    'april': '04', 'apr': '04', 'apr.': '04',
    'mei': '05',
    'juni': '06', 'jun': '06', 'jun.': '06',
    'juli': '07', 'jul': '07', 'jul.': '07',
    'agustus': '08', 'agt': '08', 'agt.': '08', 'ags': '08', 'ags.': '08',
    'september': '09', 'sep': '09', 'sep.': '09', 'sept': '09', 'sept.': '09',
    'oktober': '10', 'okt': '10', 'okt.': '10',
    'november': '11', 'nov': '11', 'nov.': '11',
    'desember': '12', 'des': '12', 'des.': '12',

    # Bahasa Inggris
    'january': '01', 'jan': '01', 'jan.': '01',
    'february': '02', 'feb': '02', 'feb.': '02',
    'march': '03', 'mar': '03', 'mar.': '03',
    'april': '04', 'apr': '04', 'apr.': '04',
    'may': '05',
    'june': '06', 'jun': '06', 'jun.': '06',
    'july': '07', 'jul': '07', 'jul.': '07',
    'august': '08', 'aug': '08', 'aug.': '08',
    'september': '09', 'sep': '09', 'sep.': '09', 'sept': '09', 'sept.': '09',
    'october': '10', 'oct': '10', 'oct.': '10',
    'november': '11', 'nov': '11', 'nov.': '11',
    'december': '12', 'dec': '12', 'dec.': '12',

}

def angka_bulan(month_str):
    month_str = month_str.lower().strip('.')
    if len(month_str) < 3:
        return None
    return MONTH_DICT.get(month_str) or MONTH_DICT.get(month_str[:3]) or MONTH_DICT.get(month_str[:4])

# Fungsi ekstraksi tanggal
def ekstraksi_tanggal(text):
    text = text.lower()
    patterns = [
        # Format dd.mm.yy
        r'(?:waktu\s*[:]?\s*)?(\d{1,2})\s*([a-zA-Z]+)\s*(\d{4})',
        r'(\d{2})[-/](\d{2})[-/](\d{4})',
        r'(\d{2})[-/](\d{2})[-/](\d{2})',
        r'(\d{4})[-/](\d{2})[-/](\d{2})',
        r'(\d{2})\.(\d{2})\.(\d{2})',
        r'(\d{2})\.(\d{2})\.(\d{4})',
         r'(\d{1,2})/(\d{1,2})/(\d{4})'
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                day, month, year = groups
                if len(year) == 2:
                    year = '20' + year
                if month.isalpha():
                    month = angka_bulan(month)
                if month:
                    try:
                        # Validasi tanggal
                        hari = int(day)
                        bulan = int(month)
                        tahun = int(year)
                        
                        # memastikan tanggal valid
                        if 1 <= hari <= 31 and 1 <= bulan <= 12:
                            return datetime(tahun, bulan, hari).strftime('%d-%m-%Y')
                    except ValueError:
                        continue
    return "Tidak ada tanggal dikenali"

    
#Fungsi ekstraksi total
def ekstraksi_total(grouped_lines):
    for group in grouped_lines:
        group.sort(key=lambda x: x[0][0][0])
        line_text = " ".join(word[1][0].lower() for word in group)
        if "total" in line_text and not any(x in line_text for x in ["subtotal", "sub total", "total disc"]):
            for word in reversed(group):
                text = word[1][0]
                if any(char.isdigit() for char in text):
                    return text
    return None

#proses OCR pada Gambar
def process_image(image_path, kategori, user_id):
    try:
        hasil = ocr.ocr(image_path, cls=True)[0]
        grouped = group_lines(hasil)
        
        # Extract all text for date processing
        all_text = " ".join([word[1][0] for line in hasil for word in [line]])
        
        # Ekstraksi tanggal and total
        tanggal = ekstraksi_tanggal(all_text)
        total = ekstraksi_total(grouped)
        dt_obj = datetime.strptime(tanggal, "%d-%m-%Y")
        kode_rekap = f"{dt_obj.strftime('%m')}-{dt_obj.year}"
        
        
    # ubah total ke integer
        if total:
            total_clean = re.sub(r'[^\d]', '', total)  # Hanya ambil digit
            try:
                total_int = int(total_clean)
            except ValueError:
                total_int = total  # tetap string kalau gagal konversi
        else:
            print("⚠️ Total tidak ditemukan dalam struk")
            total_int = "Total tidak ditemukan"

        data_setruk = {
            "user_id": user_id, 
            "kategori": kategori,
            "tanggal": tanggal if tanggal else "Tanggal tidak ditemukan",
            "total": total_int,
            "kode_rekap": kode_rekap
        }

        return data_setruk
    except Exception as e:
        return {"message": f"Error: {str(e)}"}

# Handle foto dari user
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    file_path = f"temp_{update.message.from_user.id}.jpg"
    await file.download_to_drive(file_path)

    await update.message.reply_text("Foto setruk diterima! 🧾 Setruk Sedang diproses...")
    kategori = context.user_data.get("kategori", "Tidak diketahui")
    user_id = update.effective_user.id  # Get the user ID from the update object
    
    # Jalankan OCR dan simpan hasil
    data_setruk = process_image(file_path, kategori, user_id)

    # Simpan ke database SQL
    db_status = ""
    try:
        insert_receipt_data(
            user_id=update.effective_user.id,
            nama_kategori=data_setruk['kategori'],
            tanggal=data_setruk.get('tanggal', 'Tidak ditemukan'),
            total=data_setruk.get('total', 'Tidak ditemukan'),
            kode_rekap=data_setruk.get('kode_rekap', 'Tidak ditemukan')
        )
        db_status = "✅ Data berhasil disimpan ke database"
        
        # Update rekap_perkategori hanya untuk user ini
        success, message = insert_rekap_perkategori(user_id=update.effective_user.id)
        if success:
            db_status += "\n✅ Rekap kategori berhasil diupdate"
        else:
            db_status += f"\n⚠️ {message}"
        
    except Exception as e:
        db_status = f"❌ Gagal menyimpan ke database: {str(e)}"
       
    await update.message.reply_text(
        f"✅ Setruk berhasil dicatat!\n"
        f"Kategori: {data_setruk['kategori']}\n"
        f"Tanggal: {data_setruk.get('tanggal', 'Tidak ditemukan')}\n"
        f"Total: {data_setruk.get('total', 'Tidak ditemukan')}\n\n"
        f"{db_status}\n\n"
        "• Kamu bisa kirim /start lagi untuk ke menu awal.\n"
        "• Ketik /rekap jika ingin langsung melihat laporan pengeluaran."
    )

    try:
        os.remove(file_path)
    except OSError:
        pass

    return ConversationHandler.END

#--Command handler for /rekap--
async def rekap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Masukkan kode rekap dalam format mm-yyyy/ bulan-tahun (contoh: 04-2024):"
    )
    return WAITING_REKAP_CODE

# Proses rekap
async def handle_rekap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_input = update.message.text.strip()
    kode_input = text_input
    
    # Validasi format kode mm-yyyy
    if not re.match(r'^\d{2}-\d{4}$', kode_input):
        await update.message.reply_text("Format kode rekap tidak valid. Gunakan format mm-yyyy/ bulan-tahun (contoh: 01-2024).")
        return WAITING_REKAP_CODE
    
    try:
        success, hasil = laporan_bulanan(kode_input, update.effective_user.id)

        if not success:
            await update.message.reply_text(hasil + "\nSilakan masukkan kode rekap lain (format mm-yyyy):")
            return WAITING_REKAP_CODE

        pdf_filename = hasil
        if os.path.exists(pdf_filename):
            with open(pdf_filename, 'rb') as pdf_file:
                await update.message.reply_document(
                    document=pdf_file,
                    caption=f"Laporan pengeluaran Anda untuk periode {kode_input}"
                )
            os.remove(pdf_filename)
        else:
            await update.message.reply_text("Maaf, terjadi kesalahan saat membuat laporan.")

    except Exception as e:
        await update.message.reply_text(f"Terjadi kesalahan: {str(e)}")

    return ConversationHandler.END

# Handle hapus 
async def handle_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_input = update.message.text.strip()

    try:
        total = int(text_input)
        context.user_data['pending_delete_total'] = total

        from hapus import hapus_setruk_total
        await hapus_setruk_total(update, context)
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("❌ Format total harus angka. Contoh: 25000")
        return WAITING_DELETE_CODE

# Handle batal
async def batal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Proses dibatalkan.")
    return ConversationHandler.END

# Handle button callbacks
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'input_setruk':
        await query.edit_message_text(
            "Silakan pilih kategori untuk setruk ini:\n"
            "1. 🛒 Kebutuhan Sehari-hari\n"
            "2. 🚌 Transportasi\n"
            "3. 🍔 Makan & Minum\n"
            "4. 🏠 Lainnya",
            reply_markup=None
        )
        return pilih_kategori
    
    elif query.data == 'lihat_rekap':
        context.user_data.pop('operation_type', None)
        await query.edit_message_text(
            "Masukkan bulan dan tahun yang ingin direkap.\n\nKode rekap dalam format mm-yyyy (bulan-tahun)\nContoh: 04-2024",
            reply_markup=None
        )
        return WAITING_REKAP_CODE
    elif query.data == 'hapus_setruk':
        # Set operation type to delete
        context.user_data['operation_type'] = 'delete'
        await query.edit_message_text(
            "Masukkan nominal total setruk yang ingin dihapus.\n*tidak mengandung huruf, titik dan koma\n"
            "Contoh: 25000\n"
            "⚠️ Pastikan nominal yang dimasukkan sesuai dengan total setruk yang ingin dihapus.",
            reply_markup=None
        )
        return WAITING_DELETE_CODE
    
    elif query.data in ['confirm_delete', 'cancel_delete']:
        from hapus import konfirmasi_hapus
        await konfirmasi_hapus(update, context)
        return  
    
    elif query.data == 'batal':
        context.user_data.pop('operation_type', None)
        await query.edit_message_text(
            "Operasi dibatalkan. Gunakan /start untuk memulai kembali.",
            reply_markup=None
        )
    return ConversationHandler.END

# Main conversation handler
conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler("start", start),
        CommandHandler("rekap", rekap_command),
        CommandHandler("hapus", hapus_setruk_total)
    ],
    states={
        pilih_kategori: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, pilih_kategori),
            CallbackQueryHandler(button_callback)
        ],
        WAITING_PHOTO: [MessageHandler(filters.PHOTO, handle_photo)],
        WAITING_REKAP_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_rekap)],
        WAITING_DELETE_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_delete)],
    },
    fallbacks=[CommandHandler("batal", batal)],
)

app.add_handler(conv_handler)



app.add_handler(CommandHandler("konfirmasi_hapus", konfirmasi_hapus))
# Add callback query handler for all buttons (outside conversation)
app.add_handler(CallbackQueryHandler(button_callback, pattern='^(confirm_delete|cancel_delete)$'))

if __name__ == '__main__':
    print("Bot is running...")
    app.run_polling()
