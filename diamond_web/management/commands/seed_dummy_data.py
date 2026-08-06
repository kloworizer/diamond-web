import random
from datetime import date, datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from diamond_web.models import (
    ILAP, KategoriILAP, KategoriWilayah, JenisDataILAP, JenisTabel,
    Kanwil, KPP, PIC, Tiket, StatusData, StatusPenelitian,
    BentukData, CaraPenyampaian, PeriodePengiriman, PeriodeJenisData, TiketPIC
)

User = get_user_model()

class Command(BaseCommand):
    help = "Seed dummy data for testing UI/UX"

    def handle(self, *args, **options):
        self.stdout.write("Seeding dummy data...")

        # 1. Base Master
        kat, _ = KategoriILAP.objects.get_or_create(id_kategori="K1", defaults={"nama_kategori": "Kementerian / Lembaga"})
        kwil, _ = KategoriWilayah.objects.get_or_create(deskripsi="Nasional")
        sd_tersedia, _ = StatusData.objects.get_or_create(deskripsi="Data Tersedia")
        sd_tidak, _ = StatusData.objects.get_or_create(deskripsi="Data Tidak Tersedia")
        jtabel, _ = JenisTabel.objects.get_or_create(deskripsi="Tabel Transaksi")
        bentuk, _ = BentukData.objects.get_or_create(deskripsi="Softcopy / Hardcopy")
        cara, _ = CaraPenyampaian.objects.get_or_create(deskripsi="Surat / Email")

        p_kirim, _ = PeriodePengiriman.objects.get_or_create(
            periode_penyampaian="Bulanan",
            periode_penerimaan="Bulanan"
        )

        # 2. ILAP & SubJenisData
        ilap_list = []
        for i in range(1, 6):
            ilap, _ = ILAP.objects.get_or_create(
                id_ilap=f"IL00{i}",
                defaults={
                    "nama_ilap": f"Instansi ILAP Sample {i}",
                    "id_kategori": kat,
                    "id_kategori_wilayah": kwil,
                }
            )
            ilap_list.append(ilap)

        jd_list = []
        pjd_list = []
        for idx, ilap in enumerate(ilap_list):
            jd, _ = JenisDataILAP.objects.get_or_create(
                id_sub_jenis_data=f"SJD00{idx+1}01",
                defaults={
                    "id_ilap": ilap,
                    "id_jenis_data": f"JD00{idx+1}",
                    "nama_jenis_data": f"Jenis Data Perpajakan {idx+1}",
                    "nama_sub_jenis_data": f"Sub Jenis Data Detail {idx+1}.1",
                    "nama_tabel_I": f"TABEL_I_{idx+1}",
                    "nama_tabel_U": f"TABEL_U_{idx+1}",
                    "id_jenis_tabel": jtabel,
                    "id_status_data": sd_tersedia
                }
            )
            jd_list.append(jd)

            pjd, _ = PeriodeJenisData.objects.get_or_create(
                id_sub_jenis_data_ilap=jd,
                id_periode_pengiriman=p_kirim,
                defaults={"start_date": date(2025, 1, 1), "akhir_penyampaian": 31}
            )
            pjd_list.append(pjd)

        # 3. Master Wilayah & PIC
        kanwil, _ = Kanwil.objects.get_or_create(kode_kanwil="K01", defaults={"nama_kanwil": "Kanwil DJP Jakarta Selatan"})
        kpp, _ = KPP.objects.get_or_create(kode_kpp="P01", defaults={"nama_kpp": "KPP Pratama Kebayoran Baru", "id_kanwil": kanwil})

        admin_user = User.objects.filter(username="admin").first()

        # 4. Seed Tiket (Berbagai Status: 1 s.d 8)
        statuses = [1, 2, 3, 4, 5, 6, 7, 8]

        for i in range(1, 16):
            st_code = random.choice(statuses)
            pjd = random.choice(pjd_list)

            t, created = Tiket.objects.get_or_create(
                nomor_tiket=f"TKT202607{i:04d}",
                defaults={
                    "status_tiket": st_code,
                    "id_periode_data": pjd,
                    "periode": 7,
                    "tahun": 2026,
                    "nomor_surat_pengantar": f"S-{1000+i}/IPJ/2026",
                    "tanggal_surat_pengantar": datetime.now() - timedelta(days=i),
                    "nama_pengirim": f"Pengirim Instansi {i}",
                    "id_bentuk_data": bentuk,
                    "id_cara_penyampaian": cara,
                    "status_ketersediaan_data": (i % 4 != 0),
                    "alasan_ketidaktersediaan": "Instansi belum menerbitkan laporan resmi periode ini" if i % 4 == 0 else "",
                    "baris_diterima": random.randint(10000, 500000),
                    "baris_lengkap": random.randint(8000, 490000),
                    "baris_tidak_lengkap": random.randint(0, 1000),
                    "baris_cde": random.randint(0, 500),
                    "special_request": (i % 3 == 0),
                    "tgl_terima_dip": datetime.now() - timedelta(days=i+1)
                }
            )

            if created:
                TiketPIC.objects.create(id_tiket=t, id_user=admin_user, role=1, timestamp=datetime.now(), active=True)
                TiketPIC.objects.create(id_tiket=t, id_user=admin_user, role=2, timestamp=datetime.now(), active=True)
                TiketPIC.objects.create(id_tiket=t, id_user=admin_user, role=3, timestamp=datetime.now(), active=True)

        self.stdout.write("✓ Seed dummy data berhasil dimuat!")
