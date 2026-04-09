# Generated migration - Seed database with initial data

from django.db import migrations

KATEGORI_ILAP_DATA = [
    {"kode": "AS", "nama": "ASOSIASI"},
    {"kode": "BI", "nama": "BANK SENTRAL"},
    {"kode": "BU", "nama": "BADAN USAHA MILIK NEGARA"},
    {"kode": "EI", "nama": "EXCHANGE OF INFORMATION"},
    {"kode": "KM", "nama": "KEMENTERIAN"},
    {"kode": "LK", "nama": "LEMBAGA KEUANGAN"},
    {"kode": "LM", "nama": "LEMBAGA"},
    {"kode": "PD", "nama": "PEMERINTAH DAERAH KABUPATEN/KOTA"},
    {"kode": "PK", "nama": "KPP ATAU KANWIL DJP"},
    {"kode": "PL", "nama": "PIHAK LAIN"},
    {"kode": "PV", "nama": "PEMERINTAH DAERAH PROVINSI"},
]

KATEGORI_WILAYAH_DATA = [
    {"deskripsi": "Regional"},
    {"deskripsi": "Nasional"},
    {"deskripsi": "Internasional"},
]

KANWIL_DATA = [
    {"kode_kanwil": "010", "nama_kanwil": "Kanwil DJP Sumatera Utara"},
    {"kode_kanwil": "020", "nama_kanwil": "Kanwil DJP Sumatera Barat"},
    {"kode_kanwil": "030", "nama_kanwil": "Kanwil DJP Riau"},
    {"kode_kanwil": "040", "nama_kanwil": "Kanwil DJP Jambi"},
    {"kode_kanwil": "050", "nama_kanwil": "Kanwil DJP Sumatera Selatan"},
    {"kode_kanwil": "060", "nama_kanwil": "Kanwil DJP Lampung"},
    {"kode_kanwil": "070", "nama_kanwil": "Kanwil DJP Bangka Belitung"},
    {"kode_kanwil": "080", "nama_kanwil": "Kanwil DJP DKI Jakarta"},
    {"kode_kanwil": "090", "nama_kanwil": "Kanwil DJP Jawa Barat"},
    {"kode_kanwil": "100", "nama_kanwil": "Kanwil DJP Jawa Tengah"},
    {"kode_kanwil": "110", "nama_kanwil": "Kanwil DJP Yogyakarta"},
    {"kode_kanwil": "120", "nama_kanwil": "Kanwil DJP Jawa Timur"},
    {"kode_kanwil": "130", "nama_kanwil": "Kanwil DJP Madura"},
    {"kode_kanwil": "140", "nama_kanwil": "Kanwil DJP Bali"},
    {"kode_kanwil": "150", "nama_kanwil": "Kanwil DJP Nusa Tenggara Barat"},
    {"kode_kanwil": "160", "nama_kanwil": "Kanwil DJP Nusa Tenggara Timur"},
    {"kode_kanwil": "170", "nama_kanwil": "Kanwil DJP Kalimantan Barat"},
    {"kode_kanwil": "180", "nama_kanwil": "Kanwil DJP Kalimantan Tengah"},
    {"kode_kanwil": "190", "nama_kanwil": "Kanwil DJP Kalimantan Selatan"},
    {"kode_kanwil": "200", "nama_kanwil": "Kanwil DJP Kalimantan Timur"},
    {"kode_kanwil": "210", "nama_kanwil": "Kanwil DJP Kalimantan Utara"},
    {"kode_kanwil": "220", "nama_kanwil": "Kanwil DJP Sulawesi Utara"},
    {"kode_kanwil": "230", "nama_kanwil": "Kanwil DJP Sulawesi Tengah"},
    {"kode_kanwil": "240", "nama_kanwil": "Kanwil DJP Sulawesi Selatan"},
    {"kode_kanwil": "250", "nama_kanwil": "Kanwil DJP Sulawesi Tenggara"},
    {"kode_kanwil": "260", "nama_kanwil": "Kanwil DJP Gorontalo"},
    {"kode_kanwil": "270", "nama_kanwil": "Kanwil DJP Sulawesi Barat"},
    {"kode_kanwil": "280", "nama_kanwil": "Kanwil DJP Maluku"},
    {"kode_kanwil": "290", "nama_kanwil": "Kanwil DJP Papua Barat"},
    {"kode_kanwil": "300", "nama_kanwil": "Kanwil DJP Papua"},
]

KPP_DATA = [
    {"kode_kpp": "001", "nama_kpp": "KPP Medan", "kode_kanwil": "010"},
    {"kode_kpp": "002", "nama_kpp": "KPP Pematangsiantar", "kode_kanwil": "010"},
    {"kode_kpp": "003", "nama_kpp": "KPP Padang", "kode_kanwil": "020"},
    {"kode_kpp": "004", "nama_kpp": "KPP Pekanbaru", "kode_kanwil": "030"},
    {"kode_kpp": "005", "nama_kpp": "KPP Jambi", "kode_kanwil": "040"},
    {"kode_kpp": "006", "nama_kpp": "KPP Palembang", "kode_kanwil": "050"},
    {"kode_kpp": "007", "nama_kpp": "KPP Lampung", "kode_kanwil": "060"},
    {"kode_kpp": "008", "nama_kpp": "KPP Bangka Belitung", "kode_kanwil": "070"},
    {"kode_kpp": "009", "nama_kpp": "KPP Jakarta Pusat", "kode_kanwil": "080"},
    {"kode_kpp": "010", "nama_kpp": "KPP Jakarta Selatan", "kode_kanwil": "080"},
    {"kode_kpp": "011", "nama_kpp": "KPP Jakarta Utara", "kode_kanwil": "080"},
    {"kode_kpp": "012", "nama_kpp": "KPP Jakarta Timur", "kode_kanwil": "080"},
    {"kode_kpp": "013", "nama_kpp": "KPP Jakarta Barat", "kode_kanwil": "080"},
    {"kode_kpp": "014", "nama_kpp": "KPP Bandung", "kode_kanwil": "090"},
    {"kode_kpp": "015", "nama_kpp": "KPP Bogor", "kode_kanwil": "090"},
    {"kode_kpp": "016", "nama_kpp": "KPP Cirebon", "kode_kanwil": "090"},
    {"kode_kpp": "017", "nama_kpp": "KPP Tasikmalaya", "kode_kanwil": "090"},
    {"kode_kpp": "018", "nama_kpp": "KPP Semarang", "kode_kanwil": "100"},
    {"kode_kpp": "019", "nama_kpp": "KPP Surakarta", "kode_kanwil": "100"},
    {"kode_kpp": "020", "nama_kpp": "KPP Yogyakarta", "kode_kanwil": "110"},
    {"kode_kpp": "021", "nama_kpp": "KPP Surabaya", "kode_kanwil": "120"},
    {"kode_kpp": "022", "nama_kpp": "KPP Malang", "kode_kanwil": "120"},
    {"kode_kpp": "023", "nama_kpp": "KPP Sidoarjo", "kode_kanwil": "120"},
    {"kode_kpp": "024", "nama_kpp": "KPP Madura", "kode_kanwil": "130"},
    {"kode_kpp": "025", "nama_kpp": "KPP Denpasar", "kode_kanwil": "140"},
    {"kode_kpp": "026", "nama_kpp": "KPP Mataram", "kode_kanwil": "150"},
    {"kode_kpp": "027", "nama_kpp": "KPP Kupang", "kode_kanwil": "160"},
    {"kode_kpp": "028", "nama_kpp": "KPP Pontianak", "kode_kanwil": "170"},
    {"kode_kpp": "029", "nama_kpp": "KPP Palangkaraya", "kode_kanwil": "180"},
    {"kode_kpp": "030", "nama_kpp": "KPP Banjarmasin", "kode_kanwil": "190"},
    {"kode_kpp": "031", "nama_kpp": "KPP Samarinda", "kode_kanwil": "200"},
    {"kode_kpp": "032", "nama_kpp": "KPP Tarakan", "kode_kanwil": "210"},
    {"kode_kpp": "033", "nama_kpp": "KPP Manado", "kode_kanwil": "220"},
    {"kode_kpp": "034", "nama_kpp": "KPP Palu", "kode_kanwil": "230"},
    {"kode_kpp": "035", "nama_kpp": "KPP Makassar", "kode_kanwil": "240"},
    {"kode_kpp": "036", "nama_kpp": "KPP Kendari", "kode_kanwil": "250"},
    {"kode_kpp": "037", "nama_kpp": "KPP Gorontalo", "kode_kanwil": "260"},
    {"kode_kpp": "038", "nama_kpp": "KPP Mamuju", "kode_kanwil": "270"},
    {"kode_kpp": "039", "nama_kpp": "KPP Ambon", "kode_kanwil": "280"},
    {"kode_kpp": "040", "nama_kpp": "KPP Manokwari", "kode_kanwil": "290"},
    {"kode_kpp": "041", "nama_kpp": "KPP Jayapura", "kode_kanwil": "300"},
]

JENIS_TABEL_DATA = [
    {"deskripsi": "Diidentifikasi"},
    {"deskripsi": "Tidak Diidentifikasi"},
    {"deskripsi": "Tidak Terstruktur"},
]

DASAR_HUKUM_DATA = [
    {"deskripsi": "PMK"},
    {"deskripsi": "PKS"},
    {"deskripsi": "KSWP"},
    {"deskripsi": "EOI"},
    {"deskripsi": "ADHOC"},
    {"deskripsi": "DAPEN"},
]

PERIODE_PENGIRIMAN_DATA = [
    {"periode_penyampaian": "Harian", "periode_penerimaan": "Bulanan"},
    {"periode_penyampaian": "Mingguan", "periode_penerimaan": "Bulanan"},
    {"periode_penyampaian": "2 Mingguan", "periode_penerimaan": "Bulanan"},
    {"periode_penyampaian": "Bulanan", "periode_penerimaan": "Bulanan"},
    {"periode_penyampaian": "Triwulanan", "periode_penerimaan": "Triwulanan"},
    {"periode_penyampaian": "Semester", "periode_penerimaan": "Semester"},
    {"periode_penyampaian": "Tahunan", "periode_penerimaan": "Tahunan"},
]

STATUS_DATA_DATA = [
    {"deskripsi": "Data Utama"},
    {"deskripsi": "Pengecualian"},
]

BENTUK_DATA_DATA = [
    {"deskripsi": "Hardcopy"},
    {"deskripsi": "Softcopy"},
    {"deskripsi": "Data Tidak Tersedia"},
]

CARA_PENYAMPAIAN_DATA = [
    {"deskripsi": "Langsung"},
    {"deskripsi": "Online"},
    {"deskripsi": "Nadine"},
    {"deskripsi": "Data Tidak Tersedia"},
]

MEDIA_BACKUP_DATA = [
    {"deskripsi": "NAS"},
    {"deskripsi": "Sharepoint"},
    {"deskripsi": "Datawarehouse"},
]

STATUS_PENELITIAN_DATA = [
    {"deskripsi": "Lengkap"},
    {"deskripsi": "Lengkap Sebagian"},
    {"deskripsi": "Tidak Lengkap"},
]

ILAP_DATA = [
    {"id_ilap": "AS001", "id_kategori": "AS", "nama_ilap": "GABUNGAN INDUSTRI KENDARAAN BERMOTOR (GAIKINDO)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "AS002", "id_kategori": "AS", "nama_ilap": "ASOSIASI INDUSTRI SEPEDA MOTOR INDONESIA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "AS003", "id_kategori": "AS", "nama_ilap": "IKATAN AKUNTAN PUBLIK INDONESIA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "AS004", "id_kategori": "AS", "nama_ilap": "PENGELOLA NAMA DOMAIN INTERNET INDONESIA (PANDI)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "BI001", "id_kategori": "BI", "nama_ilap": "BANK INDONESIA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "BU001", "id_kategori": "BU", "nama_ilap": "PT PELABUHAN INDONESIA II (PERSERO)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "BU002", "id_kategori": "BU", "nama_ilap": "PT PELABUHAN INDONESIA III (PERSERO)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "BU003", "id_kategori": "BU", "nama_ilap": "BPJS KETENAGAKERJAAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "BU004", "id_kategori": "BU", "nama_ilap": "PT PELABUHAN INDONESIA IV (PERSERO)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "BU005", "id_kategori": "BU", "nama_ilap": "PT PELABUHAN INDONESIA I (PERSERO)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "BU006", "id_kategori": "BU", "nama_ilap": "PT PERUSAHAAN LISTRIK NEGARA (PERSERO)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "BU007", "id_kategori": "BU", "nama_ilap": "PT. PELAYANAN LISTRIK NASIONAL (PLN) BATAM", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "BU008", "id_kategori": "BU", "nama_ilap": "BADAN PENYELENGGARA JAMINAN SOSIAL KESEHATAN (BPJS KESEHATAN)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "EI001", "id_kategori": "EI", "nama_ilap": "AUSTRALIA", "id_kategori_wilayah": "Internasional"},
    {"id_ilap": "EI002", "id_kategori": "EI", "nama_ilap": "DENMARK", "id_kategori_wilayah": "Internasional"},
    {"id_ilap": "EI003", "id_kategori": "EI", "nama_ilap": "FINLANDIA", "id_kategori_wilayah": "Internasional"},
    {"id_ilap": "EI004", "id_kategori": "EI", "nama_ilap": "HUNGARY", "id_kategori_wilayah": "Internasional"},
    {"id_ilap": "EI005", "id_kategori": "EI", "nama_ilap": "JEPANG", "id_kategori_wilayah": "Internasional"},
    {"id_ilap": "EI006", "id_kategori": "EI", "nama_ilap": "KOREA SELATAN", "id_kategori_wilayah": "Internasional"},
    {"id_ilap": "EI008", "id_kategori": "EI", "nama_ilap": "SELANDIA BARU", "id_kategori_wilayah": "Internasional"},
    {"id_ilap": "EI009", "id_kategori": "EI", "nama_ilap": "TIONGKOK", "id_kategori_wilayah": "Internasional"},
    {"id_ilap": "EI010", "id_kategori": "EI", "nama_ilap": "UNITED KINGDOM", "id_kategori_wilayah": "Internasional"},
    {"id_ilap": "EI011", "id_kategori": "EI", "nama_ilap": "AUSTRIA", "id_kategori_wilayah": "Internasional"},
    {"id_ilap": "EI012", "id_kategori": "EI", "nama_ilap": "INGGRIS", "id_kategori_wilayah": "Internasional"},
    {"id_ilap": "EI013", "id_kategori": "EI", "nama_ilap": "BELANDA", "id_kategori_wilayah": "Internasional"},
    {"id_ilap": "EI950", "id_kategori": "EI", "nama_ilap": "LEMBAGA KEUANGAN (INFORMASI KEUANGAN DOMESTIK)", "id_kategori_wilayah": "Internasional"},
    {"id_ilap": "EI951", "id_kategori": "EI", "nama_ilap": "NEGARA/YURIDIKSI MITRA (INFORMASI KEUANGAN INTERNASIONAL)", "id_kategori_wilayah": "Internasional"},
    {"id_ilap": "EI955", "id_kategori": "EI", "nama_ilap": "NEGARA/YURIDIKSI MITRA (INFORMASI PER NEGARA)", "id_kategori_wilayah": "Internasional"},
    {"id_ilap": "KM001", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN PEKERJAAN UMUM", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM002", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN PENDIDIKAN DAN KEBUDAYAAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM003", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL PERHUBUNGAN UDARA, KEMENTERIAN PERHUBUNGAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM004", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL PERHUBUNGAN DARAT, KEMENTERIAN PERHUBUNGAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM005", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN KESEHATAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM006", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN AGAMA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM007", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN PERDAGANGAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM008", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN KETENAGAKERJAAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM009", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN PERINDUSTRIAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM010", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN LINGKUNGAN HIDUP DAN KEHUTANAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM011", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN BADAN USAHA MILIK NEGARA (BUMN)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM012", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL ADMINISTRASI HUKUM UMUM, KEMENTERIAN HUKUM DAN HAK ASASI MANUSIA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM013", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL IMIGRASI, KEMENTERIAN HUKUM DAN HAK ASASI MANUSIA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM014", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL ANGGARAN KEMENTERIAN KEUANGAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM015", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL PERBENDAHARAAN KEMENTERIAN KEUANGAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM016", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL PERIMBANGAN KEUANGAN, KEMENTERIAN KEUANGAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM017", "id_kategori": "KM", "nama_ilap": "BADAN KEBIJAKAN FISKAL, KEMENTERIAN KEUANGAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM018", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL BEA DAN CUKAI KEMENTERIAN KEUANGAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM019", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN DALAM NEGERI (DUKCAPIL)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM020", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL MINERAL DAN BATU BARA, KEMENTERIAN ENERGI DAN SUMBER DAYA MINERAL", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM021", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN KELAUTAN DAN PERIKANAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM022", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN PERTAHANAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM023", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN AGRARIA DAN TATA RUANG/BADAN PERTANAHAN NASIONAL", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM024", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN KOMUNIKASI DAN INFORMATIKA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM025", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN KOPERASI DAN UKM", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM026", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN PERTANIAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM027", "id_kategori": "KM", "nama_ilap": "PUSAT DATA DAN INFORMASI (PUSDATIN), KEMENTERIAN ENERGI DAN SUMBER DAYA MINERAL", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM028", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL MINYAK DAN GAS BUMI, KEMENTERIAN ENERGI DAN SUMBER DAYA MINERAL", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM029", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL PERHUBUNGAN LAUT", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM030", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL PEMBERDAYAAN SOSIAL, KEMENTERIAN SOSIAL", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM031", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL KEKAYAAN NEGARA, KEMENTERIAN KEUANGAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM032", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN RISET, TEKNOLOGI, DAN PENDIDIKAN TINGGI", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM033", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN KEUANGAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM034", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN PARIWISATA DAN EKONOMI KREATIF / BADAN PARIWISATA DAN EKONOMI KREATIF", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM035", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL PENGELOLAAN PEMBIAYAAN DAN RISIKO, KEMENTERIAN KEUANGAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM036", "id_kategori": "KM", "nama_ilap": "BADAN PENGELOLA DANA PERKEBUNAN KELAPA SAWIT (BPDPKS)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM037", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN SEKRETARIAT NEGARA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "KM038", "id_kategori": "KM", "nama_ilap": "KEMETERIAN LUAR NEGERI", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM001", "id_kategori": "LM", "nama_ilap": "KOMISI PEMILIHAN UMUM", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM002", "id_kategori": "LM", "nama_ilap": "LEMBAGA KEBIJAKAN PENGADAAN BARANG/JASA PEMERINTAH (LKPP)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM003", "id_kategori": "LM", "nama_ilap": "BADAN PUSAT STATISTIK", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM004", "id_kategori": "LM", "nama_ilap": "BADAN KOORDINASI PENANAMAN MODAL", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM005", "id_kategori": "LM", "nama_ilap": "PUSAT LAYANAN PENGADAAN SECARA ELEKTRONIK KEMENTERIAN KEUANGAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM006", "id_kategori": "LM", "nama_ilap": "KEPOLISIAN NEGARA REPUBLIK INDONESIA (POLRI)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM007", "id_kategori": "LM", "nama_ilap": "LEMBAGA PENERBANGAN DAN ANTARIKSA NASIONAL (LAPAN)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM008", "id_kategori": "LM", "nama_ilap": "SATUAN KERJA KHUSUS PELAKSANA KEGIATAN USAHA HULU MINYAK DAN GAS BUMI", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM009", "id_kategori": "LM", "nama_ilap": "BADAN PENGAWASAN OBAT DAN MAKANAN (BPOM)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM010", "id_kategori": "LM", "nama_ilap": "OTORITAS JASA KEUANGAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM011", "id_kategori": "LM", "nama_ilap": "BADAN STANDARDISASI NASIONAL (BSN)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM012", "id_kategori": "LM", "nama_ilap": "PUSAT PELAPORAN DAN ANALISIS TRANSAKSI KEUANGAN (PPATK)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM013", "id_kategori": "LM", "nama_ilap": "BADAN PENGUSAHAAN KAWASAN PERDAGANGAN BEBAS DAN PELABUHAN BEBAS BATAM (BP BATAM)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM016", "id_kategori": "LM", "nama_ilap": "BADAN INFORMASI GEOSPASIAL", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM017", "id_kategori": "LM", "nama_ilap": "BADAN PENGATUR HILIR MINYAK DAN GAS BUMI (BPH MIGAS)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM018", "id_kategori": "LM", "nama_ilap": "KOMISI PENGAWASAN PERSAINGAN USAHA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "LM019", "id_kategori": "LM", "nama_ilap": "LEMBAGA PEMBIAYAAN EKSPOR INDONESIA (INDONESIA EXIMBANK)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL001", "id_kategori": "PL", "nama_ilap": "PT SUCOFINDO", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL002", "id_kategori": "PL", "nama_ilap": "PT JAKARTA INTERNATIONAL CONTAINER TERMINAL", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL003", "id_kategori": "PL", "nama_ilap": "PT MUSTIKA ALAM LESTARI", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL004", "id_kategori": "PL", "nama_ilap": "PT TERMINAL PETI KEMAS KOJA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL005", "id_kategori": "PL", "nama_ilap": "PT TERMINAL PETI KEMAS SURABAYA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL006", "id_kategori": "PL", "nama_ilap": "PT SURVEYOR INDONESIA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL007", "id_kategori": "PL", "nama_ilap": "PT KUSTODIAN SENTRAL EFEK INDONESIA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL008", "id_kategori": "PL", "nama_ilap": "MASYARAKAT PROFESI PENILAI INDONESIA (MAPPI)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL009", "id_kategori": "PL", "nama_ilap": "PT CARSURIN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL010", "id_kategori": "PL", "nama_ilap": "PT GEOSERVICES", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL011", "id_kategori": "PL", "nama_ilap": "PUSAT PEMBINAAN PROFESI KEUANGAN, SEKRETARIAT JENDERAL KEMENTERIAN KEUANGAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL012", "id_kategori": "PL", "nama_ilap": "PT TASPEN (PERSERO)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL013", "id_kategori": "PL", "nama_ilap": "CITIBANK N.A", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL014", "id_kategori": "PL", "nama_ilap": "PAN INDONESIA BANK, LTD. TBK.", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL015", "id_kategori": "PL", "nama_ilap": "PT BANK ANZ INDONESIA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL016", "id_kategori": "PL", "nama_ilap": "PT BANK BUKOPIN, TBK.", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL017", "id_kategori": "PL", "nama_ilap": "PT BANK CENTRAL ASIA, TBK.", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL018", "id_kategori": "PL", "nama_ilap": "PT BANK CIMB NIAGA, TBK.", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL019", "id_kategori": "PL", "nama_ilap": "PT BANK DANAMON INDONESIA, TBK.", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL020", "id_kategori": "PL", "nama_ilap": "PT BANK MNC INTERNASIONAL", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL021", "id_kategori": "PL", "nama_ilap": "PT BANK ICBC INDONESIA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL022", "id_kategori": "PL", "nama_ilap": "PT BANK MAYBANK INDONESIA, TBK.", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL023", "id_kategori": "PL", "nama_ilap": "PT BANK MANDIRI (PERSERO), TBK.", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL024", "id_kategori": "PL", "nama_ilap": "PT BANK MEGA, TBK.", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL025", "id_kategori": "PL", "nama_ilap": "PT BANK NEGARA INDONESIA 1946 (PERSERO), TBK.", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL026", "id_kategori": "PL", "nama_ilap": "PT BANK NEGARA INDONESIA SYARIAH", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL027", "id_kategori": "PL", "nama_ilap": "PT BANK OCBC NISP, TBK.", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL028", "id_kategori": "PL", "nama_ilap": "PT BANK PERMATA, TBK.", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL029", "id_kategori": "PL", "nama_ilap": "PT BANK RAKYAT INDONESIA (PERSERO), TBK.", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL030", "id_kategori": "PL", "nama_ilap": "PT BANK SINARMAS, TBK", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL031", "id_kategori": "PL", "nama_ilap": "PT BANK UOB INDONESIA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL032", "id_kategori": "PL", "nama_ilap": "STANDARD CHARTERED BANK", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL033", "id_kategori": "PL", "nama_ilap": "THE HONGKONG & SHANGHAI BANKING CORP.", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL034", "id_kategori": "PL", "nama_ilap": "PT BANK QNB INDONESIA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL035", "id_kategori": "PL", "nama_ilap": "PT AEON CREDIT SERVICES", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL036", "id_kategori": "PL", "nama_ilap": "PT HUTCHISON 3 INDONESIA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL037", "id_kategori": "PL", "nama_ilap": "PT INDOSAT TBK", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL038", "id_kategori": "PL", "nama_ilap": "PT SAMPOERNA TELEKOMUNIKASI INDONESIA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL039", "id_kategori": "PL", "nama_ilap": "PT SMARTFREN TELECOM TBK (Seluler)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL040", "id_kategori": "PL", "nama_ilap": "PT SMART TELECOM", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL041", "id_kategori": "PL", "nama_ilap": "PT TELEKOMUNIKASI SELULAR", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL042", "id_kategori": "PL", "nama_ilap": "PT XL AXIATA TBK", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL043", "id_kategori": "PL", "nama_ilap": "PT INDOSAT MEGA MEDIA", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL044", "id_kategori": "PL", "nama_ilap": "PT TELEKOMUNIKASI INDONESIA (PERSERO) TBK", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL045", "id_kategori": "PL", "nama_ilap": "PT BATAM BINTAN TELEKOMUNIKASI", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL046", "id_kategori": "PL", "nama_ilap": "PT SMARTFREN TELECOM TBK (Lokal)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL047", "id_kategori": "PL", "nama_ilap": "DANA PENSIUN LEMBAGA KEUANGAN (DPLK) DAN DANA PENSIUN PEMBERI KERJA (DPPK)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL048", "id_kategori": "PL", "nama_ilap": "DEALER UTAMA PROGRAM PENGAMPUNAN SUKARELA (PPS)", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL903", "id_kategori": "PL", "nama_ilap": "DIREKTORAT PERATURAN PERPAJAKAN II", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL906", "id_kategori": "PL", "nama_ilap": "DIREKTORAT EKSTENSIFIKASI DAN PENILAIAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL913", "id_kategori": "PL", "nama_ilap": "DIREKTORAT TRANSFORMASI PROSES BISNIS", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL914", "id_kategori": "PL", "nama_ilap": "DIREKTORAT PERPAJAKAN INTERNASIONAL", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PL915", "id_kategori": "PL", "nama_ilap": "DIREKTORAT INTELIJEN PERPAJAKAN", "id_kategori_wilayah": "Nasional"},
    {"id_ilap": "PD001", "id_kategori": "PD", "nama_ilap": "KABUPATEN SERANG", "kode_kpp": "015", "id_kategori_wilayah": "Regional"},
    {"id_ilap": "PD002", "id_kategori": "PD", "nama_ilap": "KABUPATEN SUKABUMI", "kode_kpp": "015", "id_kategori_wilayah": "Regional"},
    {"id_ilap": "PD003", "id_kategori": "PD", "nama_ilap": "KABUPATEN BEKASI", "kode_kpp": "015", "id_kategori_wilayah": "Regional"},
    {"id_ilap": "PD004", "id_kategori": "PD", "nama_ilap": "KABUPATEN TEGAL", "kode_kpp": "018", "id_kategori_wilayah": "Regional"},
    {"id_ilap": "PD005", "id_kategori": "PD", "nama_ilap": "KABUPATEN BANJARNEGARA", "kode_kpp": "018", "id_kategori_wilayah": "Regional"},
    {"id_ilap": "PD006", "id_kategori": "PD", "nama_ilap": "KOTA YOGYAKARTA", "kode_kpp": "020", "id_kategori_wilayah": "Regional"},
    {"id_ilap": "PD007", "id_kategori": "PD", "nama_ilap": "KOTA SURABAYA", "kode_kpp": "021", "id_kategori_wilayah": "Regional"},
    {"id_ilap": "PD008", "id_kategori": "PD", "nama_ilap": "KABUPATEN BANGKALAN", "kode_kpp": "024", "id_kategori_wilayah": "Regional"},
    {"id_ilap": "PD009", "id_kategori": "PD", "nama_ilap": "KOTA KEDIRI", "kode_kpp": "023", "id_kategori_wilayah": "Regional"},
    {"id_ilap": "PD010", "id_kategori": "PD", "nama_ilap": "KOTA DENPASAR", "kode_kpp": "025", "id_kategori_wilayah": "Regional"},
    {"id_ilap": "PD011", "id_kategori": "PD", "nama_ilap": "KABUPATEN LOMBOK BARAT", "kode_kpp": "026", "id_kategori_wilayah": "Regional"},
    {"id_ilap": "PD012", "id_kategori": "PD", "nama_ilap": "KOTA BANDA ACEH", "kode_kpp": "001", "id_kategori_wilayah": "Regional"},
]

JENIS_DATA_ILAP_DATA = [
    # Asosiasi (AS)
    {"id_ilap": "AS001", "id_jenis_data": "AS00101", "id_sub_jenis_data": "AS0010101", "nama_jenis_data": "Data Industri Otomotif", "nama_sub_jenis_data": "Penjualan Kendaraan", "nama_tabel_I": "tabel_penjualan_kendaraan_i", "nama_tabel_U": "tabel_penjualan_kendaraan_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "AS001", "id_jenis_data": "AS00101", "id_sub_jenis_data": "AS0010102", "nama_jenis_data": "Data Industri Otomotif", "nama_sub_jenis_data": "Produksi Kendaraan", "nama_tabel_I": "tabel_produksi_kendaraan_i", "nama_tabel_U": "tabel_produksi_kendaraan_u", "id_jenis_tabel": "Tidak Diidentifikasi", "id_status_data": "Pengecualian"},
    
    # Bank Sentral (BI)
    {"id_ilap": "BI001", "id_jenis_data": "BI00101", "id_sub_jenis_data": "BI0010101", "nama_jenis_data": "Data Moneter", "nama_sub_jenis_data": "Suku Bunga Acuan", "nama_tabel_I": "tabel_suku_bunga_acuan_i", "nama_tabel_U": "tabel_suku_bunga_acuan_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "BI001", "id_jenis_data": "BI00101", "id_sub_jenis_data": "BI0010102", "nama_jenis_data": "Data Moneter", "nama_sub_jenis_data": "Inflasi Bulanan", "nama_tabel_I": "tabel_inflasi_bulanan_i", "nama_tabel_U": "tabel_inflasi_bulanan_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "BI001", "id_jenis_data": "BI00102", "id_sub_jenis_data": "BI0010201", "nama_jenis_data": "Data Perbankan", "nama_sub_jenis_data": "Kredit Perbankan", "nama_tabel_I": "tabel_kredit_perbankan_i", "nama_tabel_U": "tabel_kredit_perbankan_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Pengecualian"},
    
    # Badan Usaha Milik Negara (BU)
    {"id_ilap": "BU001", "id_jenis_data": "BU00101", "id_sub_jenis_data": "BU0010101", "nama_jenis_data": "Data Pelabuhan", "nama_sub_jenis_data": "Container Movement", "nama_tabel_I": "tabel_container_movement_i", "nama_tabel_U": "tabel_container_movement_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "BU006", "id_jenis_data": "BU00201", "id_sub_jenis_data": "BU0020101", "nama_jenis_data": "Data Energi Listrik", "nama_sub_jenis_data": "Produksi Energi", "nama_tabel_I": "tabel_produksi_energi_i", "nama_tabel_U": "tabel_produksi_energi_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "BU003", "id_jenis_data": "BU00301", "id_sub_jenis_data": "BU0030101", "nama_jenis_data": "Data Ketenagakerjaan", "nama_sub_jenis_data": "Peserta Asuransi", "nama_tabel_I": "tabel_peserta_asuransi_i", "nama_tabel_U": "tabel_peserta_asuransi_u", "id_jenis_tabel": "Tidak Diidentifikasi", "id_status_data": "Pengecualian"},
    
    # Exchange of Information (EI)
    {"id_ilap": "EI001", "id_jenis_data": "EI00101", "id_sub_jenis_data": "EI0010101", "nama_jenis_data": "Data Pertukaran Informasi", "nama_sub_jenis_data": "Informasi Pajak Australia", "nama_tabel_I": "tabel_info_pajak_australia_i", "nama_tabel_U": "tabel_info_pajak_australia_u", "id_jenis_tabel": "Tidak Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "EI005", "id_jenis_data": "EI00101", "id_sub_jenis_data": "EI0010102", "nama_jenis_data": "Data Pertukaran Informasi", "nama_sub_jenis_data": "Informasi Pajak Jepang", "nama_tabel_I": "tabel_info_pajak_jepang_i", "nama_tabel_U": "tabel_info_pajak_jepang_u", "id_jenis_tabel": "Tidak Diidentifikasi", "id_status_data": "Pengecualian"},
    
    # Kementerian (KM)
    {"id_ilap": "KM033", "id_jenis_data": "KM03301", "id_sub_jenis_data": "KM0330101", "nama_jenis_data": "Data Keuangan Negara", "nama_sub_jenis_data": "Realisasi Anggaran", "nama_tabel_I": "tabel_realisasi_anggaran_i", "nama_tabel_U": "tabel_realisasi_anggaran_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "KM033", "id_jenis_data": "KM03301", "id_sub_jenis_data": "KM0330102", "nama_jenis_data": "Data Keuangan Negara", "nama_sub_jenis_data": "Laporan Neraca Keuangan", "nama_tabel_I": "tabel_neraca_keuangan_i", "nama_tabel_U": "tabel_neraca_keuangan_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "KM005", "id_jenis_data": "KM00501", "id_sub_jenis_data": "KM0050101", "nama_jenis_data": "Data Kesehatan", "nama_sub_jenis_data": "Data Pasien", "nama_tabel_I": "tabel_data_pasien_i", "nama_tabel_U": "tabel_data_pasien_u", "id_jenis_tabel": "Tidak Terstruktur", "id_status_data": "Data Utama"},
    {"id_ilap": "KM026", "id_jenis_data": "KM02601", "id_sub_jenis_data": "KM0260101", "nama_jenis_data": "Data Pertanian", "nama_sub_jenis_data": "Hasil Panen", "nama_tabel_I": "tabel_hasil_panen_i", "nama_tabel_U": "tabel_hasil_panen_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    
    # Lembaga (LM)
    {"id_ilap": "LM003", "id_jenis_data": "LM00301", "id_sub_jenis_data": "LM0030101", "nama_jenis_data": "Data Statistik", "nama_sub_jenis_data": "Data Penduduk", "nama_tabel_I": "tabel_penduduk_i", "nama_tabel_U": "tabel_penduduk_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "LM003", "id_jenis_data": "LM00301", "id_sub_jenis_data": "LM0030102", "nama_jenis_data": "Data Statistik", "nama_sub_jenis_data": "Data Ketenagakerjaan", "nama_tabel_I": "tabel_ketenagakerjaan_i", "nama_tabel_U": "tabel_ketenagakerjaan_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "LM010", "id_jenis_data": "LM01001", "id_sub_jenis_data": "LM0100101", "nama_jenis_data": "Data Keuangan Lembaga", "nama_sub_jenis_data": "Laporan Keuangan Lembaga Jasa Keuangan", "nama_tabel_I": "tabel_keuangan_ljk_i", "nama_tabel_U": "tabel_keuangan_ljk_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Pengecualian"},
    
    # Pihak Lain (PL)
    {"id_ilap": "PL023", "id_jenis_data": "PL02301", "id_sub_jenis_data": "PL0230101", "nama_jenis_data": "Data Bank", "nama_sub_jenis_data": "Laporan Keuangan Bank", "nama_tabel_I": "tabel_keuangan_bank_i", "nama_tabel_U": "tabel_keuangan_bank_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "PL023", "id_jenis_data": "PL02301", "id_sub_jenis_data": "PL0230102", "nama_jenis_data": "Data Bank", "nama_sub_jenis_data": "Data Nasabah", "nama_tabel_I": "tabel_data_nasabah_i", "nama_tabel_U": "tabel_data_nasabah_u", "id_jenis_tabel": "Tidak Terstruktur", "id_status_data": "Data Utama"},
    {"id_ilap": "PL044", "id_jenis_data": "PL04401", "id_sub_jenis_data": "PL0440101", "nama_jenis_data": "Data Telekomunikasi", "nama_sub_jenis_data": "Data Pelanggan", "nama_tabel_I": "tabel_data_pelanggan_i", "nama_tabel_U": "tabel_data_pelanggan_u", "id_jenis_tabel": "Tidak Terstruktur", "id_status_data": "Data Utama"},
    
    # Pemerintah Daerah Kabupaten/Kota (PD)
    {"id_ilap": "PD001", "id_jenis_data": "PD00101", "id_sub_jenis_data": "PD0010101", "nama_jenis_data": "Data Pemerintah Daerah", "nama_sub_jenis_data": "Anggaran Daerah", "nama_tabel_I": "tabel_anggaran_daerah_i", "nama_tabel_U": "tabel_anggaran_daerah_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "PD001", "id_jenis_data": "PD00102", "id_sub_jenis_data": "PD0010201", "nama_jenis_data": "Data Pajak Daerah", "nama_sub_jenis_data": "Realisasi Pajak Bumi Bangunan", "nama_tabel_I": "tabel_realisasi_pbb_i", "nama_tabel_U": "tabel_realisasi_pbb_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "PD002", "id_jenis_data": "PD00101", "id_sub_jenis_data": "PD0020101", "nama_jenis_data": "Data Pemerintah Daerah", "nama_sub_jenis_data": "Anggaran Pendapatan Belanja Daerah", "nama_tabel_I": "tabel_apbd_i", "nama_tabel_U": "tabel_apbd_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "PD002", "id_jenis_data": "PD00103", "id_sub_jenis_data": "PD0020201", "nama_jenis_data": "Data Retribusi Daerah", "nama_sub_jenis_data": "Retribusi Jasa Umum", "nama_tabel_I": "tabel_retribusi_jasa_i", "nama_tabel_U": "tabel_retribusi_jasa_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "PD003", "id_jenis_data": "PD00101", "id_sub_jenis_data": "PD0030101", "nama_jenis_data": "Data Perizinan Daerah", "nama_sub_jenis_data": "Izin Mendirikan Bangunan", "nama_tabel_I": "tabel_imb_i", "nama_tabel_U": "tabel_imb_u", "id_jenis_tabel": "Tidak Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "PD003", "id_jenis_data": "PD00104", "id_sub_jenis_data": "PD0030201", "nama_jenis_data": "Data Kependudukan Daerah", "nama_sub_jenis_data": "Data Penduduk", "nama_tabel_I": "tabel_penduduk_daerah_i", "nama_tabel_U": "tabel_penduduk_daerah_u", "id_jenis_tabel": "Tidak Terstruktur", "id_status_data": "Data Utama"},
    {"id_ilap": "PD004", "id_jenis_data": "PD00101", "id_sub_jenis_data": "PD0040101", "nama_jenis_data": "Data Infrastruktur Daerah", "nama_sub_jenis_data": "Data Jalan Daerah", "nama_tabel_I": "tabel_jalan_daerah_i", "nama_tabel_U": "tabel_jalan_daerah_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "PD005", "id_jenis_data": "PD00105", "id_sub_jenis_data": "PD0050101", "nama_jenis_data": "Data Pertanian Daerah", "nama_sub_jenis_data": "Hasil Pertanian", "nama_tabel_I": "tabel_hasil_pertanian_daerah_i", "nama_tabel_U": "tabel_hasil_pertanian_daerah_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "PD006", "id_jenis_data": "PD00106", "id_sub_jenis_data": "PD0060101", "nama_jenis_data": "Data Pariwisata Daerah", "nama_sub_jenis_data": "Kunjungan Wisatawan", "nama_tabel_I": "tabel_kunjungan_wisata_i", "nama_tabel_U": "tabel_kunjungan_wisata_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "PD007", "id_jenis_data": "PD00107", "id_sub_jenis_data": "PD0070101", "nama_jenis_data": "Data Perdagangan Daerah", "nama_sub_jenis_data": "Data Pasar Tradisional", "nama_tabel_I": "tabel_pasar_tradisional_i", "nama_tabel_U": "tabel_pasar_tradisional_u", "id_jenis_tabel": "Tidak Terstruktur", "id_status_data": "Data Utama"},
    {"id_ilap": "PD008", "id_jenis_data": "PD00108", "id_sub_jenis_data": "PD0080101", "nama_jenis_data": "Data Pelabuhan Daerah", "nama_sub_jenis_data": "Aktivitas Pelabuhan", "nama_tabel_I": "tabel_aktivitas_pelabuhan_i", "nama_tabel_U": "tabel_aktivitas_pelabuhan_u", "id_jenis_tabel": "Diidentifikasi", "id_status_data": "Data Utama"},
    {"id_ilap": "PD009", "id_jenis_data": "PD00101", "id_sub_jenis_data": "PD0090101", "nama_jenis_data": "Data Transportasi Daerah", "nama_sub_jenis_data": "Data Kendaraan Umum", "nama_tabel_I": "tabel_kendaraan_umum_i", "nama_tabel_U": "tabel_kendaraan_umum_u", "id_jenis_tabel": "Tidak Diidentifikasi", "id_status_data": "Data Utama"},
]

KLASIFIKASI_JENIS_DATA = [
    # Asosiasi (AS) - random from PMK, PKS, KSWP, ADHOC, DAPEN
    {"id_sub_jenis_data": "AS0010101", "dasar_hukum": "PMK"},
    {"id_sub_jenis_data": "AS0010101", "dasar_hukum": "PKS"},
    {"id_sub_jenis_data": "AS0010102", "dasar_hukum": "KSWP"},
    {"id_sub_jenis_data": "AS0010102", "dasar_hukum": "ADHOC"},
    
    # Bank Sentral (BI)
    {"id_sub_jenis_data": "BI0010101", "dasar_hukum": "PMK"},
    {"id_sub_jenis_data": "BI0010102", "dasar_hukum": "PKS"},
    {"id_sub_jenis_data": "BI0010102", "dasar_hukum": "DAPEN"},
    {"id_sub_jenis_data": "BI0010201", "dasar_hukum": "PMK"},
    {"id_sub_jenis_data": "BI0010201", "dasar_hukum": "KSWP"},
    
    # Badan Usaha Milik Negara (BU)
    {"id_sub_jenis_data": "BU0010101", "dasar_hukum": "PKS"},
    {"id_sub_jenis_data": "BU0020101", "dasar_hukum": "PMK"},
    {"id_sub_jenis_data": "BU0020101", "dasar_hukum": "ADHOC"},
    {"id_sub_jenis_data": "BU0030101", "dasar_hukum": "DAPEN"},
    
    # Exchange of Information (EI) - always EOI
    {"id_sub_jenis_data": "EI0010101", "dasar_hukum": "EOI"},
    {"id_sub_jenis_data": "EI0010102", "dasar_hukum": "EOI"},
    
    # Kementerian (KM)
    {"id_sub_jenis_data": "KM0330101", "dasar_hukum": "PMK"},
    {"id_sub_jenis_data": "KM0330101", "dasar_hukum": "PKS"},
    {"id_sub_jenis_data": "KM0330102", "dasar_hukum": "KSWP"},
    {"id_sub_jenis_data": "KM0050101", "dasar_hukum": "PMK"},
    {"id_sub_jenis_data": "KM0050101", "dasar_hukum": "DAPEN"},
    {"id_sub_jenis_data": "KM0260101", "dasar_hukum": "PMK"},
    
    # Lembaga (LM)
    {"id_sub_jenis_data": "LM0030101", "dasar_hukum": "PKS"},
    {"id_sub_jenis_data": "LM0030101", "dasar_hukum": "ADHOC"},
    {"id_sub_jenis_data": "LM0030102", "dasar_hukum": "PMK"},
    {"id_sub_jenis_data": "LM0100101", "dasar_hukum": "KSWP"},
    
    # Pihak Lain (PL)
    {"id_sub_jenis_data": "PL0230101", "dasar_hukum": "PMK"},
    {"id_sub_jenis_data": "PL0230101", "dasar_hukum": "PKS"},
    {"id_sub_jenis_data": "PL0230102", "dasar_hukum": "DAPEN"},
    {"id_sub_jenis_data": "PL0440101", "dasar_hukum": "ADHOC"},
    
    # Pemerintah Daerah Kabupaten/Kota (PD)
    {"id_sub_jenis_data": "PD0010101", "dasar_hukum": "PMK"},
    {"id_sub_jenis_data": "PD0010101", "dasar_hukum": "PKS"},
    {"id_sub_jenis_data": "PD0010201", "dasar_hukum": "KSWP"},
    {"id_sub_jenis_data": "PD0020101", "dasar_hukum": "PMK"},
    {"id_sub_jenis_data": "PD0020201", "dasar_hukum": "PKS"},
    {"id_sub_jenis_data": "PD0020201", "dasar_hukum": "DAPEN"},
    {"id_sub_jenis_data": "PD0030101", "dasar_hukum": "ADHOC"},
    {"id_sub_jenis_data": "PD0030201", "dasar_hukum": "PMK"},
    {"id_sub_jenis_data": "PD0040101", "dasar_hukum": "PKS"},
    {"id_sub_jenis_data": "PD0040101", "dasar_hukum": "KSWP"},
    {"id_sub_jenis_data": "PD0050101", "dasar_hukum": "PMK"},
    {"id_sub_jenis_data": "PD0060101", "dasar_hukum": "PKS"},
    {"id_sub_jenis_data": "PD0060101", "dasar_hukum": "ADHOC"},
    {"id_sub_jenis_data": "PD0070101", "dasar_hukum": "DAPEN"},
    {"id_sub_jenis_data": "PD0080101", "dasar_hukum": "PMK"},
    {"id_sub_jenis_data": "PD0080101", "dasar_hukum": "KSWP"},
    {"id_sub_jenis_data": "PD0090101", "dasar_hukum": "ADHOC"},
]

PERIODE_JENIS_DATA = [
    # Asosiasi (AS)
    {"id_sub_jenis_data": "AS0010101", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 10},
    {"id_sub_jenis_data": "AS0010102", "periode": "Triwulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 15},
    
    # Bank Sentral (BI)
    {"id_sub_jenis_data": "BI0010101", "periode": "Harian", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 1},
    {"id_sub_jenis_data": "BI0010102", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 5},
    {"id_sub_jenis_data": "BI0010201", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 20},
    
    # Badan Usaha Milik Negara (BU)
    {"id_sub_jenis_data": "BU0010101", "periode": "Mingguan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 3},
    {"id_sub_jenis_data": "BU0020101", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 10},
    {"id_sub_jenis_data": "BU0030101", "periode": "2 Mingguan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 7},
    
    # Exchange of Information (EI)
    {"id_sub_jenis_data": "EI0010101", "periode": "Tahunan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 60},
    {"id_sub_jenis_data": "EI0010102", "periode": "Semester", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 45},
    
    # Kementerian (KM)
    {"id_sub_jenis_data": "KM0330101", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 15},
    {"id_sub_jenis_data": "KM0330102", "periode": "Triwulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 20},
    {"id_sub_jenis_data": "KM0050101", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 10},
    {"id_sub_jenis_data": "KM0260101", "periode": "Tahunan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 90},
    
    # Lembaga (LM)
    {"id_sub_jenis_data": "LM0030101", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 10},
    {"id_sub_jenis_data": "LM0030102", "periode": "Tahunan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 60},
    {"id_sub_jenis_data": "LM0100101", "periode": "Triwulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 30},
    
    # Pihak Lain (PL)
    {"id_sub_jenis_data": "PL0230101", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 10},
    {"id_sub_jenis_data": "PL0230102", "periode": "Triwulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 20},
    {"id_sub_jenis_data": "PL0440101", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 15},
    
    # Pemerintah Daerah Kabupaten/Kota (PD)
    {"id_sub_jenis_data": "PD0010101", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 20},
    {"id_sub_jenis_data": "PD0010201", "periode": "Triwulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 25},
    {"id_sub_jenis_data": "PD0020101", "periode": "Tahunan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 90},
    {"id_sub_jenis_data": "PD0020201", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 15},
    {"id_sub_jenis_data": "PD0030101", "periode": "Mingguan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 5},
    {"id_sub_jenis_data": "PD0030201", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 10},
    {"id_sub_jenis_data": "PD0040101", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 12},
    {"id_sub_jenis_data": "PD0050101", "periode": "Tahunan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 60},
    {"id_sub_jenis_data": "PD0060101", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 10},
    {"id_sub_jenis_data": "PD0070101", "periode": "Triwulanan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 18},
    {"id_sub_jenis_data": "PD0080101", "periode": "Mingguan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 3},
    {"id_sub_jenis_data": "PD0090101", "periode": "2 Mingguan", "start_date": "2024-01-01", "end_date": None, "akhir_penyampaian": 7},
]

JENIS_PRIORITAS_DATA = [
    # 2025 - selected sample from JenisDataILAP
    {"id_sub_jenis_data": "AS0010101", "no_nd": "ND-2025-001", "tahun": "2025", "start_date": "2025-01-01", "end_date": "2025-12-31"},
    {"id_sub_jenis_data": "BI0010101", "no_nd": "ND-2025-002", "tahun": "2025", "start_date": "2025-01-01", "end_date": "2025-12-31"},
    {"id_sub_jenis_data": "EI0010101", "no_nd": "ND-2025-003", "tahun": "2025", "start_date": "2025-01-01", "end_date": "2025-12-31"},
    {"id_sub_jenis_data": "KM0330101", "no_nd": "ND-2025-004", "tahun": "2025", "start_date": "2025-01-01", "end_date": "2025-12-31"},
    {"id_sub_jenis_data": "PD0010101", "no_nd": "ND-2025-005", "tahun": "2025", "start_date": "2025-01-01", "end_date": "2025-12-31"},
    
    # 2026 - selected sample from JenisDataILAP
    {"id_sub_jenis_data": "BI0010102", "no_nd": "ND-2026-001", "tahun": "2026", "start_date": "2026-01-01", "end_date": None},
    {"id_sub_jenis_data": "LM0030102", "no_nd": "ND-2026-002", "tahun": "2026", "start_date": "2026-01-01", "end_date": None},
    {"id_sub_jenis_data": "PD0020201", "no_nd": "ND-2026-003", "tahun": "2026", "start_date": "2026-01-01", "end_date": None},
]

USERS_DATA = [
    # user_p3de group (3 users) - username and password are the same (9-digit number)
    {"username": "334070720", "first_name": "Ahmad", "last_name": "Wijaya", "group": "user_p3de"},
    {"username": "219166966", "first_name": "Budi", "last_name": "Santoso", "group": "user_p3de"},
    {"username": "469817665", "first_name": "Citra", "last_name": "Dewi", "group": "user_p3de"},
    
    # user_pide group (3 users) - username and password are the same (9-digit number)
    {"username": "235512708", "first_name": "Dwi", "last_name": "Purwanto", "group": "user_pide"},
    {"username": "778511709", "first_name": "Eka", "last_name": "Prasetya", "group": "user_pide"},
    {"username": "648726232", "first_name": "Farhan", "last_name": "Hidayat", "group": "user_pide"},
    
    # user_pmde group (3 users) - username and password are the same (9-digit number)
    {"username": "446674438", "first_name": "Gitawati", "last_name": "Handini", "group": "user_pmde"},
    {"username": "090860740", "first_name": "Hendra", "last_name": "Kusuma", "group": "user_pmde"},
    {"username": "897882042", "first_name": "Irwan", "last_name": "Setiawan", "group": "user_pmde"},
]


# PIC data - fixed assignments with one user per seksi for each JenisDataILAP
PIC_DATA = [
    # AS0010101 - Penjualan Kendaraan
    {"id_sub_jenis_data": "AS0010101", "tipe": "P3DE", "username": "469817665"},
    {"id_sub_jenis_data": "AS0010101", "tipe": "PIDE", "username": "778511709"},
    {"id_sub_jenis_data": "AS0010101", "tipe": "PMDE", "username": "090860740"},
    # AS0010102 - Produksi Kendaraan
    {"id_sub_jenis_data": "AS0010102", "tipe": "P3DE", "username": "219166966"},
    {"id_sub_jenis_data": "AS0010102", "tipe": "PIDE", "username": "235512708"},
    {"id_sub_jenis_data": "AS0010102", "tipe": "PMDE", "username": "897882042"},
    # BI0010101 - Suku Bunga Acuan
    {"id_sub_jenis_data": "BI0010101", "tipe": "P3DE", "username": "334070720"},
    {"id_sub_jenis_data": "BI0010101", "tipe": "PIDE", "username": "648726232"},
    {"id_sub_jenis_data": "BI0010101", "tipe": "PMDE", "username": "897882042"},
    # BI0010102 - Inflasi Bulanan
    {"id_sub_jenis_data": "BI0010102", "tipe": "P3DE", "username": "469817665"},
    {"id_sub_jenis_data": "BI0010102", "tipe": "PIDE", "username": "648726232"},
    {"id_sub_jenis_data": "BI0010102", "tipe": "PMDE", "username": "446674438"},
    # BI0010201 - Kredit Perbankan
    {"id_sub_jenis_data": "BI0010201", "tipe": "P3DE", "username": "469817665"},
    {"id_sub_jenis_data": "BI0010201", "tipe": "PIDE", "username": "648726232"},
    {"id_sub_jenis_data": "BI0010201", "tipe": "PMDE", "username": "090860740"},
    # BU0010101 - Container Movement
    {"id_sub_jenis_data": "BU0010101", "tipe": "P3DE", "username": "219166966"},
    {"id_sub_jenis_data": "BU0010101", "tipe": "PIDE", "username": "648726232"},
    {"id_sub_jenis_data": "BU0010101", "tipe": "PMDE", "username": "446674438"},
    # BU0020101 - Produksi Energi
    {"id_sub_jenis_data": "BU0020101", "tipe": "P3DE", "username": "469817665"},
    {"id_sub_jenis_data": "BU0020101", "tipe": "PIDE", "username": "648726232"},
    {"id_sub_jenis_data": "BU0020101", "tipe": "PMDE", "username": "446674438"},
    # BU0030101 - Peserta Asuransi
    {"id_sub_jenis_data": "BU0030101", "tipe": "P3DE", "username": "219166966"},
    {"id_sub_jenis_data": "BU0030101", "tipe": "PIDE", "username": "235512708"},
    {"id_sub_jenis_data": "BU0030101", "tipe": "PMDE", "username": "897882042"},
    # EI0010101 - Informasi Pajak Australia
    {"id_sub_jenis_data": "EI0010101", "tipe": "P3DE", "username": "469817665"},
    {"id_sub_jenis_data": "EI0010101", "tipe": "PIDE", "username": "235512708"},
    {"id_sub_jenis_data": "EI0010101", "tipe": "PMDE", "username": "090860740"},
    # EI0010102 - Informasi Pajak Jepang
    {"id_sub_jenis_data": "EI0010102", "tipe": "P3DE", "username": "334070720"},
    {"id_sub_jenis_data": "EI0010102", "tipe": "PIDE", "username": "235512708"},
    {"id_sub_jenis_data": "EI0010102", "tipe": "PMDE", "username": "897882042"},
    # KM0050101 - Data Pasien
    {"id_sub_jenis_data": "KM0050101", "tipe": "P3DE", "username": "469817665"},
    {"id_sub_jenis_data": "KM0050101", "tipe": "PIDE", "username": "235512708"},
    {"id_sub_jenis_data": "KM0050101", "tipe": "PMDE", "username": "897882042"},
    # KM0260101 - Hasil Panen
    {"id_sub_jenis_data": "KM0260101", "tipe": "P3DE", "username": "219166966"},
    {"id_sub_jenis_data": "KM0260101", "tipe": "PIDE", "username": "778511709"},
    {"id_sub_jenis_data": "KM0260101", "tipe": "PMDE", "username": "446674438"},
    # KM0330101 - Realisasi Anggaran
    {"id_sub_jenis_data": "KM0330101", "tipe": "P3DE", "username": "469817665"},
    {"id_sub_jenis_data": "KM0330101", "tipe": "PIDE", "username": "235512708"},
    {"id_sub_jenis_data": "KM0330101", "tipe": "PMDE", "username": "446674438"},
    # KM0330102 - Laporan Neraca Keuangan
    {"id_sub_jenis_data": "KM0330102", "tipe": "P3DE", "username": "334070720"},
    {"id_sub_jenis_data": "KM0330102", "tipe": "PIDE", "username": "235512708"},
    {"id_sub_jenis_data": "KM0330102", "tipe": "PMDE", "username": "090860740"},
    # LM0030101 - Data Penduduk
    {"id_sub_jenis_data": "LM0030101", "tipe": "P3DE", "username": "334070720"},
    {"id_sub_jenis_data": "LM0030101", "tipe": "PIDE", "username": "648726232"},
    {"id_sub_jenis_data": "LM0030101", "tipe": "PMDE", "username": "897882042"},
    # LM0030102 - Data Ketenagakerjaan
    {"id_sub_jenis_data": "LM0030102", "tipe": "P3DE", "username": "219166966"},
    {"id_sub_jenis_data": "LM0030102", "tipe": "PIDE", "username": "235512708"},
    {"id_sub_jenis_data": "LM0030102", "tipe": "PMDE", "username": "090860740"},
    # LM0100101 - Laporan Keuangan Lembaga Jasa Keuangan
    {"id_sub_jenis_data": "LM0100101", "tipe": "P3DE", "username": "219166966"},
    {"id_sub_jenis_data": "LM0100101", "tipe": "PIDE", "username": "778511709"},
    {"id_sub_jenis_data": "LM0100101", "tipe": "PMDE", "username": "446674438"},
    # PD0010101 - Anggaran Daerah
    {"id_sub_jenis_data": "PD0010101", "tipe": "P3DE", "username": "334070720"},
    {"id_sub_jenis_data": "PD0010101", "tipe": "PIDE", "username": "648726232"},
    {"id_sub_jenis_data": "PD0010101", "tipe": "PMDE", "username": "090860740"},
    # PD0010201 - Realisasi Pajak Bumi Bangunan
    {"id_sub_jenis_data": "PD0010201", "tipe": "P3DE", "username": "219166966"},
    {"id_sub_jenis_data": "PD0010201", "tipe": "PIDE", "username": "235512708"},
    {"id_sub_jenis_data": "PD0010201", "tipe": "PMDE", "username": "446674438"},
    # PD0020101 - Anggaran Pendapatan Belanja Daerah
    {"id_sub_jenis_data": "PD0020101", "tipe": "P3DE", "username": "219166966"},
    {"id_sub_jenis_data": "PD0020101", "tipe": "PIDE", "username": "235512708"},
    {"id_sub_jenis_data": "PD0020101", "tipe": "PMDE", "username": "446674438"},
    # PD0020201 - Retribusi Jasa Umum
    {"id_sub_jenis_data": "PD0020201", "tipe": "P3DE", "username": "469817665"},
    {"id_sub_jenis_data": "PD0020201", "tipe": "PIDE", "username": "648726232"},
    {"id_sub_jenis_data": "PD0020201", "tipe": "PMDE", "username": "090860740"},
    # PD0030101 - Izin Mendirikan Bangunan
    {"id_sub_jenis_data": "PD0030101", "tipe": "P3DE", "username": "219166966"},
    {"id_sub_jenis_data": "PD0030101", "tipe": "PIDE", "username": "648726232"},
    {"id_sub_jenis_data": "PD0030101", "tipe": "PMDE", "username": "897882042"},
    # PD0030201 - Data Penduduk
    {"id_sub_jenis_data": "PD0030201", "tipe": "P3DE", "username": "469817665"},
    {"id_sub_jenis_data": "PD0030201", "tipe": "PIDE", "username": "778511709"},
    {"id_sub_jenis_data": "PD0030201", "tipe": "PMDE", "username": "446674438"},
    # PD0040101 - Data Jalan Daerah
    {"id_sub_jenis_data": "PD0040101", "tipe": "P3DE", "username": "334070720"},
    {"id_sub_jenis_data": "PD0040101", "tipe": "PIDE", "username": "235512708"},
    {"id_sub_jenis_data": "PD0040101", "tipe": "PMDE", "username": "090860740"},
    # PD0050101 - Hasil Pertanian
    {"id_sub_jenis_data": "PD0050101", "tipe": "P3DE", "username": "334070720"},
    {"id_sub_jenis_data": "PD0050101", "tipe": "PIDE", "username": "648726232"},
    {"id_sub_jenis_data": "PD0050101", "tipe": "PMDE", "username": "446674438"},
    # PD0060101 - Kunjungan Wisatawan
    {"id_sub_jenis_data": "PD0060101", "tipe": "P3DE", "username": "334070720"},
    {"id_sub_jenis_data": "PD0060101", "tipe": "PIDE", "username": "235512708"},
    {"id_sub_jenis_data": "PD0060101", "tipe": "PMDE", "username": "446674438"},
    # PD0070101 - Data Pasar Tradisional
    {"id_sub_jenis_data": "PD0070101", "tipe": "P3DE", "username": "334070720"},
    {"id_sub_jenis_data": "PD0070101", "tipe": "PIDE", "username": "235512708"},
    {"id_sub_jenis_data": "PD0070101", "tipe": "PMDE", "username": "090860740"},
    # PD0080101 - Aktivitas Pelabuhan
    {"id_sub_jenis_data": "PD0080101", "tipe": "P3DE", "username": "219166966"},
    {"id_sub_jenis_data": "PD0080101", "tipe": "PIDE", "username": "235512708"},
    {"id_sub_jenis_data": "PD0080101", "tipe": "PMDE", "username": "090860740"},
    # PD0090101 - Data Kendaraan Umum
    {"id_sub_jenis_data": "PD0090101", "tipe": "P3DE", "username": "219166966"},
    {"id_sub_jenis_data": "PD0090101", "tipe": "PIDE", "username": "778511709"},
    {"id_sub_jenis_data": "PD0090101", "tipe": "PMDE", "username": "090860740"},
    # PL0230101 - Laporan Keuangan Bank
    {"id_sub_jenis_data": "PL0230101", "tipe": "P3DE", "username": "219166966"},
    {"id_sub_jenis_data": "PL0230101", "tipe": "PIDE", "username": "235512708"},
    {"id_sub_jenis_data": "PL0230101", "tipe": "PMDE", "username": "897882042"},
    # PL0230102 - Data Nasabah
    {"id_sub_jenis_data": "PL0230102", "tipe": "P3DE", "username": "469817665"},
    {"id_sub_jenis_data": "PL0230102", "tipe": "PIDE", "username": "648726232"},
    {"id_sub_jenis_data": "PL0230102", "tipe": "PMDE", "username": "897882042"},
    # PL0440101 - Data Pelanggan
    {"id_sub_jenis_data": "PL0440101", "tipe": "P3DE", "username": "219166966"},
    {"id_sub_jenis_data": "PL0440101", "tipe": "PIDE", "username": "778511709"},
    {"id_sub_jenis_data": "PL0440101", "tipe": "PMDE", "username": "897882042"},
]

DURASI_JATUH_TEMPO_DATA = [
    # AS0010101 - Penjualan Kendaraan
    {"id_sub_jenis_data": "AS0010101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "AS0010101", "seksi": "user_pmde", "durasi": 90},
    # AS0010102 - Produksi Kendaraan
    {"id_sub_jenis_data": "AS0010102", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "AS0010102", "seksi": "user_pmde", "durasi": 90},
    # BI0010101 - Suku Bunga Acuan
    {"id_sub_jenis_data": "BI0010101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "BI0010101", "seksi": "user_pmde", "durasi": 90},
    # BI0010102 - Inflasi Bulanan
    {"id_sub_jenis_data": "BI0010102", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "BI0010102", "seksi": "user_pmde", "durasi": 90},
    # BI0010201 - Kredit Perbankan
    {"id_sub_jenis_data": "BI0010201", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "BI0010201", "seksi": "user_pmde", "durasi": 90},
    # BU0010101 - Container Movement
    {"id_sub_jenis_data": "BU0010101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "BU0010101", "seksi": "user_pmde", "durasi": 90},
    # BU0020101 - Produksi Energi
    {"id_sub_jenis_data": "BU0020101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "BU0020101", "seksi": "user_pmde", "durasi": 90},
    # BU0030101 - Peserta Asuransi
    {"id_sub_jenis_data": "BU0030101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "BU0030101", "seksi": "user_pmde", "durasi": 90},
    # EI0010101 - Informasi Pajak Australia
    {"id_sub_jenis_data": "EI0010101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "EI0010101", "seksi": "user_pmde", "durasi": 90},
    # EI0010102 - Informasi Pajak Jepang
    {"id_sub_jenis_data": "EI0010102", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "EI0010102", "seksi": "user_pmde", "durasi": 90},
    # KM0050101 - Data Pasien
    {"id_sub_jenis_data": "KM0050101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "KM0050101", "seksi": "user_pmde", "durasi": 90},
    # KM0260101 - Hasil Panen
    {"id_sub_jenis_data": "KM0260101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "KM0260101", "seksi": "user_pmde", "durasi": 90},
    # KM0330101 - Realisasi Anggaran
    {"id_sub_jenis_data": "KM0330101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "KM0330101", "seksi": "user_pmde", "durasi": 90},
    # KM0330102 - Laporan Neraca Keuangan
    {"id_sub_jenis_data": "KM0330102", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "KM0330102", "seksi": "user_pmde", "durasi": 90},
    # LM0030101 - Data Penduduk
    {"id_sub_jenis_data": "LM0030101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "LM0030101", "seksi": "user_pmde", "durasi": 90},
    # LM0030102 - Data Ketenagakerjaan
    {"id_sub_jenis_data": "LM0030102", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "LM0030102", "seksi": "user_pmde", "durasi": 90},
    # LM0100101 - Laporan Keuangan Lembaga Jasa Keuangan
    {"id_sub_jenis_data": "LM0100101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "LM0100101", "seksi": "user_pmde", "durasi": 90},
    # PD0010101 - Anggaran Daerah
    {"id_sub_jenis_data": "PD0010101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "PD0010101", "seksi": "user_pmde", "durasi": 90},
    # PD0010201 - Realisasi Pajak Bumi Bangunan
    {"id_sub_jenis_data": "PD0010201", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "PD0010201", "seksi": "user_pmde", "durasi": 90},
    # PD0020101 - Anggaran Pendapatan Belanja Daerah
    {"id_sub_jenis_data": "PD0020101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "PD0020101", "seksi": "user_pmde", "durasi": 90},
    # PD0020201 - Retribusi Jasa Umum
    {"id_sub_jenis_data": "PD0020201", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "PD0020201", "seksi": "user_pmde", "durasi": 90},
    # PD0030101 - Izin Mendirikan Bangunan
    {"id_sub_jenis_data": "PD0030101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "PD0030101", "seksi": "user_pmde", "durasi": 90},
    # PD0030201 - Data Penduduk
    {"id_sub_jenis_data": "PD0030201", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "PD0030201", "seksi": "user_pmde", "durasi": 90},
    # PD0040101 - Data Jalan Daerah
    {"id_sub_jenis_data": "PD0040101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "PD0040101", "seksi": "user_pmde", "durasi": 90},
    # PD0050101 - Hasil Pertanian
    {"id_sub_jenis_data": "PD0050101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "PD0050101", "seksi": "user_pmde", "durasi": 90},
    # PD0060101 - Kunjungan Wisatawan
    {"id_sub_jenis_data": "PD0060101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "PD0060101", "seksi": "user_pmde", "durasi": 90},
    # PD0070101 - Data Pasar Tradisional
    {"id_sub_jenis_data": "PD0070101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "PD0070101", "seksi": "user_pmde", "durasi": 90},
    # PD0080101 - Aktivitas Pelabuhan
    {"id_sub_jenis_data": "PD0080101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "PD0080101", "seksi": "user_pmde", "durasi": 90},
    # PD0090101 - Data Kendaraan Umum
    {"id_sub_jenis_data": "PD0090101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "PD0090101", "seksi": "user_pmde", "durasi": 90},
    # PL0230101 - Laporan Keuangan Bank
    {"id_sub_jenis_data": "PL0230101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "PL0230101", "seksi": "user_pmde", "durasi": 90},
    # PL0230102 - Data Nasabah
    {"id_sub_jenis_data": "PL0230102", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "PL0230102", "seksi": "user_pmde", "durasi": 90},
    # PL0440101 - Data Pelanggan
    {"id_sub_jenis_data": "PL0440101", "seksi": "user_pide", "durasi": 90},
    {"id_sub_jenis_data": "PL0440101", "seksi": "user_pmde", "durasi": 90},
]


def seed_kategori_ilap(apps, schema_editor):
    """Seeds the KategoriILAP model with initial data."""
    KategoriILAP = apps.get_model("diamond_web", "KategoriILAP")
    for item in KATEGORI_ILAP_DATA:
        KategoriILAP.objects.get_or_create(
            id_kategori=item["kode"], defaults={"nama_kategori": item["nama"]}
        )


def unseed_kategori_ilap(apps, schema_editor):
    """Removes the initial data from the KategoriILAP model."""
    KategoriILAP = apps.get_model("diamond_web", "KategoriILAP")
    kodes_to_delete = [item["kode"] for item in KATEGORI_ILAP_DATA]
    KategoriILAP.objects.filter(id_kategori__in=kodes_to_delete).delete()


def seed_kategori_wilayah(apps, schema_editor):
    """Seeds the KategoriWilayah model with initial data."""
    KategoriWilayah = apps.get_model("diamond_web", "KategoriWilayah")
    for item in KATEGORI_WILAYAH_DATA:
        KategoriWilayah.objects.get_or_create(
            deskripsi=item["deskripsi"]
        )


def unseed_kategori_wilayah(apps, schema_editor):
    """Removes the initial data from the KategoriWilayah model."""
    KategoriWilayah = apps.get_model("diamond_web", "KategoriWilayah")
    descriptions_to_delete = [item["deskripsi"] for item in KATEGORI_WILAYAH_DATA]
    KategoriWilayah.objects.filter(deskripsi__in=descriptions_to_delete).delete()


def seed_kanwil(apps, schema_editor):
    """Seeds the Kanwil model with initial data."""
    Kanwil = apps.get_model("diamond_web", "Kanwil")
    for item in KANWIL_DATA:
        Kanwil.objects.get_or_create(
            kode_kanwil=item["kode_kanwil"],
            defaults={"nama_kanwil": item["nama_kanwil"]}
        )


def unseed_kanwil(apps, schema_editor):
    """Removes the initial data from the Kanwil model."""
    Kanwil = apps.get_model("diamond_web", "Kanwil")
    kodes_to_delete = [item["kode_kanwil"] for item in KANWIL_DATA]
    Kanwil.objects.filter(kode_kanwil__in=kodes_to_delete).delete()


def seed_kpp(apps, schema_editor):
    """Seeds the KPP model with initial data."""
    KPP = apps.get_model("diamond_web", "KPP")
    Kanwil = apps.get_model("diamond_web", "Kanwil")
    for item in KPP_DATA:
        kanwil = Kanwil.objects.get(kode_kanwil=item["kode_kanwil"])
        KPP.objects.get_or_create(
            kode_kpp=item["kode_kpp"],
            defaults={
                "nama_kpp": item["nama_kpp"],
                "id_kanwil": kanwil
            }
        )


def unseed_kpp(apps, schema_editor):
    """Removes the initial data from the KPP model."""
    KPP = apps.get_model("diamond_web", "KPP")
    kodes_to_delete = [item["kode_kpp"] for item in KPP_DATA]
    KPP.objects.filter(kode_kpp__in=kodes_to_delete).delete()


def seed_jenis_tabel(apps, schema_editor):
    """Seeds the JenisTabel model with initial data."""
    JenisTabel = apps.get_model("diamond_web", "JenisTabel")
    for item in JENIS_TABEL_DATA:
        JenisTabel.objects.get_or_create(
            deskripsi=item["deskripsi"]
        )


def unseed_jenis_tabel(apps, schema_editor):
    """Removes the initial data from the JenisTabel model."""
    JenisTabel = apps.get_model("diamond_web", "JenisTabel")
    descriptions_to_delete = [item["deskripsi"] for item in JENIS_TABEL_DATA]
    JenisTabel.objects.filter(deskripsi__in=descriptions_to_delete).delete()


def seed_dasar_hukum(apps, schema_editor):
    """Seeds the DasarHukum model with initial data."""
    DasarHukum = apps.get_model("diamond_web", "DasarHukum")
    for item in DASAR_HUKUM_DATA:
        DasarHukum.objects.get_or_create(
            deskripsi=item["deskripsi"]
        )


def unseed_dasar_hukum(apps, schema_editor):
    """Removes the initial data from the DasarHukum model."""
    DasarHukum = apps.get_model("diamond_web", "DasarHukum")
    descriptions_to_delete = [item["deskripsi"] for item in DASAR_HUKUM_DATA]
    DasarHukum.objects.filter(deskripsi__in=descriptions_to_delete).delete()


def seed_periode_pengiriman(apps, schema_editor):
    """Seeds the PeriodePengiriman model with initial data."""
    PeriodePengiriman = apps.get_model("diamond_web", "PeriodePengiriman")
    for periode in PERIODE_PENGIRIMAN_DATA:
        PeriodePengiriman.objects.get_or_create(
            periode_penyampaian=periode["periode_penyampaian"],
            defaults={"periode_penerimaan": periode["periode_penerimaan"]}
        )


def unseed_periode_pengiriman(apps, schema_editor):
    """Removes the initial data from the PeriodePengiriman model."""
    PeriodePengiriman = apps.get_model("diamond_web", "PeriodePengiriman")
    periode_penyampaian_list = [item["periode_penyampaian"] for item in PERIODE_PENGIRIMAN_DATA]
    PeriodePengiriman.objects.filter(periode_penyampaian__in=periode_penyampaian_list).delete()


def seed_status_data(apps, schema_editor):
    """Seeds the StatusData model with initial data."""
    StatusData = apps.get_model("diamond_web", "StatusData")
    for item in STATUS_DATA_DATA:
        StatusData.objects.get_or_create(
            deskripsi=item["deskripsi"]
        )


def unseed_status_data(apps, schema_editor):
    """Removes the initial data from the StatusData model."""
    StatusData = apps.get_model("diamond_web", "StatusData")
    descriptions_to_delete = [item["deskripsi"] for item in STATUS_DATA_DATA]
    StatusData.objects.filter(deskripsi__in=descriptions_to_delete).delete()


def seed_bentuk_data(apps, schema_editor):
    """Seeds the BentukData model with initial data."""
    BentukData = apps.get_model("diamond_web", "BentukData")
    for item in BENTUK_DATA_DATA:
        BentukData.objects.get_or_create(
            deskripsi=item["deskripsi"]
        )


def unseed_bentuk_data(apps, schema_editor):
    """Removes the initial data from the BentukData model."""
    BentukData = apps.get_model("diamond_web", "BentukData")
    descriptions_to_delete = [item["deskripsi"] for item in BENTUK_DATA_DATA]
    BentukData.objects.filter(deskripsi__in=descriptions_to_delete).delete()


def seed_cara_penyampaian(apps, schema_editor):
    """Seeds the CaraPenyampaian model with initial data."""
    CaraPenyampaian = apps.get_model("diamond_web", "CaraPenyampaian")
    for item in CARA_PENYAMPAIAN_DATA:
        CaraPenyampaian.objects.get_or_create(
            deskripsi=item["deskripsi"]
        )


def unseed_cara_penyampaian(apps, schema_editor):
    """Removes the initial data from the CaraPenyampaian model."""
    CaraPenyampaian = apps.get_model("diamond_web", "CaraPenyampaian")
    descriptions_to_delete = [item["deskripsi"] for item in CARA_PENYAMPAIAN_DATA]
    CaraPenyampaian.objects.filter(deskripsi__in=descriptions_to_delete).delete()


def seed_media_backup(apps, schema_editor):
    """Seeds the MediaBackup model with initial data."""
    MediaBackup = apps.get_model("diamond_web", "MediaBackup")
    for item in MEDIA_BACKUP_DATA:
        MediaBackup.objects.get_or_create(
            deskripsi=item["deskripsi"]
        )


def unseed_media_backup(apps, schema_editor):
    """Removes the initial data from the MediaBackup model."""
    MediaBackup = apps.get_model("diamond_web", "MediaBackup")
    descriptions_to_delete = [item["deskripsi"] for item in MEDIA_BACKUP_DATA]
    MediaBackup.objects.filter(deskripsi__in=descriptions_to_delete).delete()


def seed_status_penelitian(apps, schema_editor):
    """Seeds the StatusPenelitian model with initial data."""
    StatusPenelitian = apps.get_model("diamond_web", "StatusPenelitian")
    for item in STATUS_PENELITIAN_DATA:
        StatusPenelitian.objects.get_or_create(
            deskripsi=item["deskripsi"]
        )


def unseed_status_penelitian(apps, schema_editor):
    """Removes the initial data from the StatusPenelitian model."""
    StatusPenelitian = apps.get_model("diamond_web", "StatusPenelitian")
    descriptions_to_delete = [item["deskripsi"] for item in STATUS_PENELITIAN_DATA]
    StatusPenelitian.objects.filter(deskripsi__in=descriptions_to_delete).delete()


def seed_ilap(apps, schema_editor):
    """Seeds the ILAP model with initial data."""
    ILAP = apps.get_model("diamond_web", "ILAP")
    KategoriILAP = apps.get_model("diamond_web", "KategoriILAP")
    KPP = apps.get_model("diamond_web", "KPP")
    KategoriWilayah = apps.get_model("diamond_web", "KategoriWilayah")
    
    for item in ILAP_DATA:
        kategori = KategoriILAP.objects.get(id_kategori=item["id_kategori"])
        
        # Get KPP if kode_kpp is provided in the data
        kpp = None
        if "kode_kpp" in item and item["kode_kpp"]:
            kpp = KPP.objects.get(kode_kpp=item["kode_kpp"])
        
        # Get kategori_wilayah from data if provided
        kategori_wilayah = None
        if "id_kategori_wilayah" in item and item["id_kategori_wilayah"]:
            kategori_wilayah = KategoriWilayah.objects.get(deskripsi=item["id_kategori_wilayah"])
        
        ILAP.objects.get_or_create(
            id_ilap=item["id_ilap"],
            defaults={
                "id_kategori": kategori,
                "nama_ilap": item["nama_ilap"],
                "id_kpp": kpp,
                "id_kategori_wilayah": kategori_wilayah
            }
        )


def unseed_ilap(apps, schema_editor):
    """Removes the initial data from the ILAP model."""
    ILAP = apps.get_model("diamond_web", "ILAP")
    ids_to_delete = [item["id_ilap"] for item in ILAP_DATA]
    ILAP.objects.filter(id_ilap__in=ids_to_delete).delete()


def seed_jenis_data_ilap(apps, schema_editor):
    """Seeds the JenisDataILAP model with initial data."""
    JenisDataILAP = apps.get_model("diamond_web", "JenisDataILAP")
    ILAP = apps.get_model("diamond_web", "ILAP")
    JenisTabel = apps.get_model("diamond_web", "JenisTabel")
    StatusData = apps.get_model("diamond_web", "StatusData")
    
    for item in JENIS_DATA_ILAP_DATA:
        try:
            ilap = ILAP.objects.get(id_ilap=item["id_ilap"])
            jenis_tabel = JenisTabel.objects.get(deskripsi=item["id_jenis_tabel"])
            status_data = StatusData.objects.get(deskripsi=item["id_status_data"])
            
            JenisDataILAP.objects.get_or_create(
                id_sub_jenis_data=item["id_sub_jenis_data"],
                defaults={
                    "id_ilap": ilap,
                    "id_jenis_data": item["id_jenis_data"],
                    "nama_jenis_data": item["nama_jenis_data"],
                    "nama_sub_jenis_data": item["nama_sub_jenis_data"],
                    "nama_tabel_I": item["nama_tabel_I"],
                    "nama_tabel_U": item["nama_tabel_U"],
                    "id_jenis_tabel": jenis_tabel,
                    "id_status_data": status_data,
                }
            )
        except Exception as e:
            print(f"Warning: Could not create JenisDataILAP {item['id_sub_jenis_data']}: {e}")


def unseed_jenis_data_ilap(apps, schema_editor):
    """Removes the initial data from the JenisDataILAP model."""
    JenisDataILAP = apps.get_model("diamond_web", "JenisDataILAP")
    sub_jenis_data_ids = [item["id_sub_jenis_data"] for item in JENIS_DATA_ILAP_DATA]
    JenisDataILAP.objects.filter(id_sub_jenis_data__in=sub_jenis_data_ids).delete()


def seed_klasifikasi_jenis_data(apps, schema_editor):
    """Seeds the KlasifikasiJenisData model with initial data."""
    KlasifikasiJenisData = apps.get_model("diamond_web", "KlasifikasiJenisData")
    JenisDataILAP = apps.get_model("diamond_web", "JenisDataILAP")
    DasarHukum = apps.get_model("diamond_web", "DasarHukum")
    
    for item in KLASIFIKASI_JENIS_DATA:
        try:
            jenis_data_ilap = JenisDataILAP.objects.get(id_sub_jenis_data=item["id_sub_jenis_data"])
            dasar_hukum = DasarHukum.objects.get(deskripsi=item["dasar_hukum"])
            
            KlasifikasiJenisData.objects.get_or_create(
                id_jenis_data_ilap=jenis_data_ilap,
                id_klasifikasi_tabel=dasar_hukum
            )
        except Exception as e:
            print(f"Warning: Could not create KlasifikasiJenisData for {item['id_sub_jenis_data']} with {item['dasar_hukum']}: {e}")


def unseed_klasifikasi_jenis_data(apps, schema_editor):
    """Removes the initial data from the KlasifikasiJenisData model."""
    KlasifikasiJenisData = apps.get_model("diamond_web", "KlasifikasiJenisData")
    sub_jenis_data_ids = [item["id_sub_jenis_data"] for item in KLASIFIKASI_JENIS_DATA]
    # Delete all KlasifikasiJenisData records associated with the seeded JenisDataILAP records
    KlasifikasiJenisData.objects.filter(id_jenis_data_ilap__id_sub_jenis_data__in=sub_jenis_data_ids).delete()


def seed_periode_jenis_data(apps, schema_editor):
    """Seeds the PeriodeJenisData model with initial data."""
    from datetime import datetime
    PeriodeJenisData = apps.get_model("diamond_web", "PeriodeJenisData")
    JenisDataILAP = apps.get_model("diamond_web", "JenisDataILAP")
    PeriodePengiriman = apps.get_model("diamond_web", "PeriodePengiriman")
    
    for item in PERIODE_JENIS_DATA:
        try:
            jenis_data_ilap = JenisDataILAP.objects.get(id_sub_jenis_data=item["id_sub_jenis_data"])
            periode_pengiriman = PeriodePengiriman.objects.get(periode_penyampaian=item["periode"])
            
            # Parse the dates
            start_date = datetime.strptime(item["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(item["end_date"], "%Y-%m-%d").date() if item["end_date"] else None
            
            PeriodeJenisData.objects.get_or_create(
                id_sub_jenis_data_ilap=jenis_data_ilap,
                id_periode_pengiriman=periode_pengiriman,
                defaults={
                    "start_date": start_date,
                    "end_date": end_date,
                    "akhir_penyampaian": item["akhir_penyampaian"],
                }
            )
        except Exception as e:
            print(f"Warning: Could not create PeriodeJenisData for {item['id_sub_jenis_data']}: {e}")


def unseed_periode_jenis_data(apps, schema_editor):
    """Removes the initial data from the PeriodeJenisData model."""
    PeriodeJenisData = apps.get_model("diamond_web", "PeriodeJenisData")
    sub_jenis_data_ids = [item["id_sub_jenis_data"] for item in PERIODE_JENIS_DATA]
    # Delete all PeriodeJenisData records associated with the seeded JenisDataILAP records
    PeriodeJenisData.objects.filter(id_sub_jenis_data_ilap__id_sub_jenis_data__in=sub_jenis_data_ids).delete()


def seed_jenis_prioritas_data(apps, schema_editor):
    """Seeds the JenisPrioritasData model with initial data."""
    from datetime import datetime
    JenisPrioritasData = apps.get_model("diamond_web", "JenisPrioritasData")
    JenisDataILAP = apps.get_model("diamond_web", "JenisDataILAP")
    
    for item in JENIS_PRIORITAS_DATA:
        try:
            jenis_data_ilap = JenisDataILAP.objects.get(id_sub_jenis_data=item["id_sub_jenis_data"])
            
            # Parse the dates
            start_date = datetime.strptime(item["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(item["end_date"], "%Y-%m-%d").date() if item["end_date"] else None
            
            JenisPrioritasData.objects.get_or_create(
                id_sub_jenis_data_ilap=jenis_data_ilap,
                tahun=item["tahun"],
                defaults={
                    "start_date": start_date,
                    "end_date": end_date,
                    "no_nd": item["no_nd"],
                }
            )
        except Exception as e:
            print(f"Warning: Could not create JenisPrioritasData for {item['id_sub_jenis_data']} tahun {item['tahun']}: {e}")


def unseed_jenis_prioritas_data(apps, schema_editor):
    """Removes the initial data from the JenisPrioritasData model."""
    JenisPrioritasData = apps.get_model("diamond_web", "JenisPrioritasData")
    sub_jenis_data_ids = [item["id_sub_jenis_data"] for item in JENIS_PRIORITAS_DATA]
    # Delete all JenisPrioritasData records associated with the seeded JenisDataILAP records
    JenisPrioritasData.objects.filter(id_sub_jenis_data_ilap__id_sub_jenis_data__in=sub_jenis_data_ids).delete()


def seed_users(apps, schema_editor):
    """Seeds the User model with fixed users (3 per group) with fixed 9-digit usernames and passwords."""
    from django.contrib.auth.hashers import make_password
    
    User = apps.get_model("auth", "User")
    Group = apps.get_model("auth", "Group")
    
    for item in USERS_DATA:
        try:
            group = Group.objects.get(name=item["group"])
            
            # Use fixed username from USERS_DATA
            username = item["username"]
            # Password is same as username
            password = username
            email = f"{username}@diamond.pde"
            
            # Create user with hashed password (skip if already exists)
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": item["first_name"],
                    "last_name": item["last_name"],
                    "email": email,
                    "password": make_password(password)
                }
            )
            
            # Add to group
            user.groups.add(group)
        except Exception as e:
            print(f"Warning: Could not create user {item['first_name']} {item['last_name']}: {e}")


def unseed_users(apps, schema_editor):
    """Removes the seeded users from user groups."""
    User = apps.get_model("auth", "User")
    
    # Delete users with fixed 9-digit usernames from USERS_DATA
    usernames = [item["username"] for item in USERS_DATA]
    User.objects.filter(username__in=usernames).delete()


def seed_pic(apps, schema_editor):
    """Seeds the PIC model with fixed user assignments from PIC_DATA."""
    User = apps.get_model("auth", "User")
    JenisDataILAP = apps.get_model("diamond_web", "JenisDataILAP")
    PIC = apps.get_model("diamond_web", "PIC")
    
    from datetime import datetime
    start_date = datetime.strptime("2024-01-01", "%Y-%m-%d").date()
    
    # Create PIC for each entry in PIC_DATA
    for item in PIC_DATA:
        try:
            jenis_data_ilap = JenisDataILAP.objects.get(id_sub_jenis_data=item["id_sub_jenis_data"])
            user = User.objects.get(username=item["username"])
            
            PIC.objects.get_or_create(
                tipe=item["tipe"],
                id_sub_jenis_data_ilap=jenis_data_ilap,
                defaults={
                    'id_user': user,
                    'start_date': start_date,
                    'end_date': None
                }
            )
        except Exception as e:
            print(f"Warning: Could not create PIC for {item['id_sub_jenis_data']} {item['tipe']}: {e}")


def unseed_pic(apps, schema_editor):
    """Removes all seeded PIC records."""
    PIC = apps.get_model("diamond_web", "PIC")
    
    # Delete PIC records that match the seeded data
    id_sub_jenis_data_list = [item["id_sub_jenis_data"] for item in PIC_DATA]
    PIC.objects.filter(id_sub_jenis_data_ilap__id_sub_jenis_data__in=id_sub_jenis_data_list).delete()


def seed_durasi_jatuh_tempo(apps, schema_editor):
    """Seeds the DurasiJatuhTempo model with fixed durations for PIDE and PMDE seksi."""
    Group = apps.get_model("auth", "Group")
    JenisDataILAP = apps.get_model("diamond_web", "JenisDataILAP")
    DurasiJatuhTempo = apps.get_model("diamond_web", "DurasiJatuhTempo")
    
    from datetime import datetime
    start_date = datetime.strptime("2024-01-01", "%Y-%m-%d").date()
    
    # Create DurasiJatuhTempo for each entry in DURASI_JATUH_TEMPO_DATA
    for item in DURASI_JATUH_TEMPO_DATA:
        try:
            jenis_data_ilap = JenisDataILAP.objects.get(id_sub_jenis_data=item["id_sub_jenis_data"])
            seksi_group = Group.objects.get(name=item["seksi"])
            
            DurasiJatuhTempo.objects.get_or_create(
                id_sub_jenis_data=jenis_data_ilap,
                seksi=seksi_group,
                defaults={
                    'durasi': item["durasi"],
                    'start_date': start_date,
                    'end_date': None
                }
            )
        except Exception as e:
            print(f"Warning: Could not create DurasiJatuhTempo for {item['id_sub_jenis_data']} {item['seksi']}: {e}")


def unseed_durasi_jatuh_tempo(apps, schema_editor):
    """Removes all seeded DurasiJatuhTempo records."""
    DurasiJatuhTempo = apps.get_model("diamond_web", "DurasiJatuhTempo")
    
    # Delete DurasiJatuhTempo records that match the seeded data
    id_sub_jenis_data_list = [item["id_sub_jenis_data"] for item in DURASI_JATUH_TEMPO_DATA]
    DurasiJatuhTempo.objects.filter(id_sub_jenis_data__id_sub_jenis_data__in=id_sub_jenis_data_list).delete()


def seed_docx_templates(apps, schema_editor):
    """Seeds the DocxTemplate model with sample template metadata."""
    DocxTemplate = apps.get_model("diamond_web", "DocxTemplate")
    
    templates = [
        {
            'nama_template': 'Tanda Terima ILAP Nasional/Internasional',
            'deskripsi': 'Template tanda terima untuk ILAP nasional dan internasional dengan placeholder: {{nomor_tanda_terima}}, {{diterima_dari}}, {{nomor_surat_pengantar}}, {{tanggal_surat_pengantar}}, {{nama_ilap}}, {{jenis_data}}, {{periode_data}}, {{bentuk_data}}, {{cara_penyampaian}}, {{tanggal_terima_dip}}, {{nama_pic_p3de}}',
            'jenis_dokumen': 'tanda_terima_nasional_internasional',
        },
        {
            'nama_template': 'Tanda Terima ILAP Regional',
            'deskripsi': 'Template tanda terima untuk ILAP regional dengan placeholder untuk nomor, tanggal, dan data pengirim',
            'jenis_dokumen': 'tanda_terima_regional',
        },
        {
            'nama_template': 'Lampiran Tanda Terima ILAP Nasional/Internasional',
            'deskripsi': 'Lampiran rincian tanda terima untuk ILAP nasional dan internasional',
            'jenis_dokumen': 'lampiran_tanda_terima_nasional_internasional',
        },
        {
            'nama_template': 'Lampiran Tanda Terima ILAP Regional',
            'deskripsi': 'Lampiran rincian tanda terima untuk ILAP regional',
            'jenis_dokumen': 'lampiran_tanda_terima_regional',
        },
        {
            'nama_template': 'Register Penerimaan Data',
            'deskripsi': 'Register pencatatan penerimaan data P3DE',
            'jenis_dokumen': 'register_penerimaan_data',
        },
        {
            'nama_template': 'ND Pengantar ke PIDE',
            'deskripsi': 'Naskah Dinas pengantar pengiriman data ke PIDE',
            'jenis_dokumen': 'nd_pengantar_pide',
        },
        {
            'nama_template': 'Surat Klarifikasi',
            'deskripsi': 'Surat klarifikasi data untuk pengirim',
            'jenis_dokumen': 'surat_klarifikasi',
        },
        {
            'nama_template': 'Surat PKDI ILAP Nasional/Internasional Lengkap',
            'deskripsi': 'Surat Pernyataan Kesesuaian Data ILAP Lengkap',
            'jenis_dokumen': 'surat_pkdi_nasional_internasional_lengkap',
        },
        {
            'nama_template': 'Surat PKDI ILAP Nasional/Internasional Lengkap Sebagian',
            'deskripsi': 'Surat Pernyataan Kesesuaian Data ILAP Lengkap Sebagian',
            'jenis_dokumen': 'surat_pkdi_nasional_internasional_sebagian',
        },
        {
            'nama_template': 'Surat PKDI ILAP Regional Lengkap',
            'deskripsi': 'Surat Pernyataan Kesesuaian Data ILAP Regional Lengkap',
            'jenis_dokumen': 'surat_pkdi_regional_lengkap',
        },
        {
            'nama_template': 'Surat PKDI ILAP Regional Lengkap Sebagian',
            'deskripsi': 'Surat Pernyataan Kesesuaian Data ILAP Regional Lengkap Sebagian',
            'jenis_dokumen': 'surat_pkdi_regional_sebagian',
        },
    ]
    
    for template in templates:
        # Create DocxTemplate metadata entry if it doesn't exist
        DocxTemplate.objects.get_or_create(
            jenis_dokumen=template['jenis_dokumen'],
            defaults={
                'nama_template': template['nama_template'],
                'deskripsi': template['deskripsi'],
                'active': True,
            }
        )


def unseed_docx_templates(apps, schema_editor):
    """Reverse function for seed_docx_templates."""
    DocxTemplate = apps.get_model("diamond_web", "DocxTemplate")
    DocxTemplate.objects.all().delete()



class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(seed_kategori_ilap, reverse_code=unseed_kategori_ilap),
        migrations.RunPython(seed_kategori_wilayah, reverse_code=unseed_kategori_wilayah),
        migrations.RunPython(seed_kanwil, reverse_code=unseed_kanwil),
        migrations.RunPython(seed_kpp, reverse_code=unseed_kpp),
        migrations.RunPython(seed_jenis_tabel, reverse_code=unseed_jenis_tabel),
        migrations.RunPython(seed_dasar_hukum, reverse_code=unseed_dasar_hukum),
        migrations.RunPython(seed_periode_pengiriman, reverse_code=unseed_periode_pengiriman),
        migrations.RunPython(seed_status_data, reverse_code=unseed_status_data),
        migrations.RunPython(seed_bentuk_data, reverse_code=unseed_bentuk_data),
        migrations.RunPython(seed_cara_penyampaian, reverse_code=unseed_cara_penyampaian),
        migrations.RunPython(seed_media_backup, reverse_code=unseed_media_backup),
        migrations.RunPython(seed_status_penelitian, reverse_code=unseed_status_penelitian),
        migrations.RunPython(seed_ilap, reverse_code=unseed_ilap),
        migrations.RunPython(seed_jenis_data_ilap, reverse_code=unseed_jenis_data_ilap),
        migrations.RunPython(seed_klasifikasi_jenis_data, reverse_code=unseed_klasifikasi_jenis_data),
        migrations.RunPython(seed_periode_jenis_data, reverse_code=unseed_periode_jenis_data),
        migrations.RunPython(seed_jenis_prioritas_data, reverse_code=unseed_jenis_prioritas_data),
        migrations.RunPython(seed_users, reverse_code=unseed_users),
        migrations.RunPython(seed_pic, reverse_code=unseed_pic),
        migrations.RunPython(seed_durasi_jatuh_tempo, reverse_code=unseed_durasi_jatuh_tempo),
        migrations.RunPython(seed_docx_templates, reverse_code=unseed_docx_templates),
    ]
