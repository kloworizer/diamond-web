# Panduan Komparasi Versi Repo (Fork vs Main)

Panduan ini digunakan untuk membandingkan repositori fork Anda (`zcracktz`) dengan repositori utama (`kloworizer`) secara aman, tanpa menimpa atau membuat konflik di folder kerja Anda saat ini. Metode yang digunakan adalah **"Dua Folder Berdampingan"**.

## Langkah 1: Kloning Repositori Utama (Lead)

Kita akan mengunduh versi terbaru dari repositori utama ke dalam folder baru yang terpisah.

1. Di dalam IDE (Antigravity), buka **Terminal baru** (biarkan terminal yang saat ini menjalankan port 8000 tetap hidup).
2. Jalankan perintah berikut secara berurutan:

```bash
# 1. Mundur satu folder ke direktori utama tempat Anda menyimpan project
cd /Volumes/Work-Yuk🔥/PROJECT/

# 2. Kloning repo utama (kloworizer) ke folder baru bernama 'diamond-web-main'
git clone https://github.com/kloworizer/diamond-web diamond-web-main

# 3. Masuk ke folder baru tersebut
cd diamond-web-main
```

## Langkah 2: Jalankan Versi Lead di Port 8001

Karena Anda sekarang berada di folder `diamond-web-main`, jalankan server untuk versi ini agar tidak bertabrakan dengan server utama Anda.

1. Jika proyek menggunakan Virtual Environment (`.venv` atau `env`), aktifkan dulu environment tersebut (sama seperti saat Anda menyalakan server biasanya).
2. Jalankan server dengan menetapkan port **8001**:

```bash
python manage.py runserver 8001
```

## Langkah 3: Bandingkan Tampilan secara Visual (Di Browser)

Sekarang Anda memiliki dua server Django yang berjalan secara paralel di komputer Anda:

- **Buka Tab 1:** `http://127.0.0.1:8000` (Ini adalah hasil kerja Anda di repo fork).
- **Buka Tab 2:** `http://127.0.0.1:8001` (Ini adalah kode terbaru Lead Anda di repo utama).

*Anda kini bisa leluasa berpindah tab untuk membandingkan UI/UX secara real-time.*

## Langkah 4: Bandingkan Kode (Di IDE Antigravity)

Untuk membandingkan struktur kodenya:

1. Di menu Antigravity, pilih opsi **File > New Window**.
2. Di window baru yang terbuka, pilih **File > Open Folder**.
3. Pilih folder repositori lead Anda: `/Volumes/Work-Yuk🔥/PROJECT/diamond-web-main`.
4. Geser posisi window baru ini ke sebelah **kanan** layar Anda, dan letakkan window proyek utama Anda di sebelah **kiri**.

**Tips Tambahan:**
Jika sewaktu-waktu teman/lead Anda melakukan `push` update terbaru lagi di Github utama, Anda cukup masuk ke folder `diamond-web-main` lewat terminal, lalu ketik:
```bash
git pull origin main
```
Cara ini memastikan kode referensi selalu up-to-date tanpa merusak pekerjaan Anda sendiri!
