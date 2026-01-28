# Generated squashed migration - Seed ILAP data

from django.db import migrations

ILAP_DATA = [
    {"id_ilap": "AS001", "id_kategori": "AS", "nama_ilap": "GABUNGAN INDUSTRI KENDARAAN BERMOTOR (GAIKINDO)"},
    {"id_ilap": "AS002", "id_kategori": "AS", "nama_ilap": "ASOSIASI INDUSTRI SEPEDA MOTOR INDONESIA"},
    {"id_ilap": "AS003", "id_kategori": "AS", "nama_ilap": "IKATAN AKUNTAN PUBLIK INDONESIA"},
    {"id_ilap": "AS004", "id_kategori": "AS", "nama_ilap": "PENGELOLA NAMA DOMAIN INTERNET INDONESIA (PANDI)"},
    {"id_ilap": "BI001", "id_kategori": "BI", "nama_ilap": "BANK INDONESIA"},
    {"id_ilap": "BU001", "id_kategori": "BU", "nama_ilap": "PT PELABUHAN INDONESIA II (PERSERO)"},
    {"id_ilap": "BU002", "id_kategori": "BU", "nama_ilap": "PT PELABUHAN INDONESIA III (PERSERO)"},
    {"id_ilap": "BU003", "id_kategori": "BU", "nama_ilap": "BPJS KETENAGAKERJAAN"},
    {"id_ilap": "BU004", "id_kategori": "BU", "nama_ilap": "PT PELABUHAN INDONESIA IV (PERSERO)"},
    {"id_ilap": "BU005", "id_kategori": "BU", "nama_ilap": "PT PELABUHAN INDONESIA I (PERSERO)"},
    {"id_ilap": "BU006", "id_kategori": "BU", "nama_ilap": "PT PERUSAHAAN LISTRIK NEGARA (PERSERO)"},
    {"id_ilap": "BU007", "id_kategori": "BU", "nama_ilap": "PT. PELAYANAN LISTRIK NASIONAL (PLN) BATAM"},
    {"id_ilap": "BU008", "id_kategori": "BU", "nama_ilap": "BADAN PENYELENGGARA JAMINAN SOSIAL KESEHATAN (BPJS KESEHATAN)"},
    {"id_ilap": "EI001", "id_kategori": "EI", "nama_ilap": "AUSTRALIA"},
    {"id_ilap": "EI002", "id_kategori": "EI", "nama_ilap": "DENMARK"},
    {"id_ilap": "EI003", "id_kategori": "EI", "nama_ilap": "FINLANDIA"},
    {"id_ilap": "EI004", "id_kategori": "EI", "nama_ilap": "HUNGARY"},
    {"id_ilap": "EI005", "id_kategori": "EI", "nama_ilap": "JEPANG"},
    {"id_ilap": "EI006", "id_kategori": "EI", "nama_ilap": "KOREA SELATAN"},
    {"id_ilap": "EI008", "id_kategori": "EI", "nama_ilap": "SELANDIA BARU"},
    {"id_ilap": "EI009", "id_kategori": "EI", "nama_ilap": "TIONGKOK"},
    {"id_ilap": "EI010", "id_kategori": "EI", "nama_ilap": "UNITED KINGDOM"},
    {"id_ilap": "EI011", "id_kategori": "EI", "nama_ilap": "AUSTRIA"},
    {"id_ilap": "EI012", "id_kategori": "EI", "nama_ilap": "INGGRIS"},
    {"id_ilap": "EI013", "id_kategori": "EI", "nama_ilap": "BELANDA"},
    {"id_ilap": "EI950", "id_kategori": "EI", "nama_ilap": "LEMBAGA KEUANGAN (INFORMASI KEUANGAN DOMESTIK)"},
    {"id_ilap": "EI951", "id_kategori": "EI", "nama_ilap": "NEGARA/YURIDIKSI MITRA (INFORMASI KEUANGAN INTERNASIONAL)"},
    {"id_ilap": "EI955", "id_kategori": "EI", "nama_ilap": "NEGARA/YURIDIKSI MITRA (INFORMASI PER NEGARA)"},
    {"id_ilap": "KM001", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN PEKERJAAN UMUM"},
    {"id_ilap": "KM002", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN PENDIDIKAN DAN KEBUDAYAAN"},
    {"id_ilap": "KM003", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL PERHUBUNGAN UDARA, KEMENTERIAN PERHUBUNGAN"},
    {"id_ilap": "KM004", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL PERHUBUNGAN DARAT, KEMENTERIAN PERHUBUNGAN"},
    {"id_ilap": "KM005", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN KESEHATAN"},
    {"id_ilap": "KM006", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN AGAMA"},
    {"id_ilap": "KM007", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN PERDAGANGAN"},
    {"id_ilap": "KM008", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN KETENAGAKERJAAN"},
    {"id_ilap": "KM009", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN PERINDUSTRIAN"},
    {"id_ilap": "KM010", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN LINGKUNGAN HIDUP DAN KEHUTANAN"},
    {"id_ilap": "KM011", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN BADAN USAHA MILIK NEGARA (BUMN)"},
    {"id_ilap": "KM012", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL ADMINISTRASI HUKUM UMUM, KEMENTERIAN HUKUM DAN HAK ASASI MANUSIA"},
    {"id_ilap": "KM013", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL IMIGRASI, KEMENTERIAN HUKUM DAN HAK ASASI MANUSIA"},
    {"id_ilap": "KM014", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL ANGGARAN KEMENTERIAN KEUANGAN"},
    {"id_ilap": "KM015", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL PERBENDAHARAAN KEMENTERIAN KEUANGAN"},
    {"id_ilap": "KM016", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL PERIMBANGAN KEUANGAN, KEMENTERIAN KEUANGAN"},
    {"id_ilap": "KM017", "id_kategori": "KM", "nama_ilap": "BADAN KEBIJAKAN FISKAL, KEMENTERIAN KEUANGAN"},
    {"id_ilap": "KM018", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL BEA DAN CUKAI KEMENTERIAN KEUANGAN"},
    {"id_ilap": "KM019", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN DALAM NEGERI (DUKCAPIL)"},
    {"id_ilap": "KM020", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL MINERAL DAN BATU BARA, KEMENTERIAN ENERGI DAN SUMBER DAYA MINERAL"},
    {"id_ilap": "KM021", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN KELAUTAN DAN PERIKANAN"},
    {"id_ilap": "KM022", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN PERTAHANAN"},
    {"id_ilap": "KM023", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN AGRARIA DAN TATA RUANG/BADAN PERTANAHAN NASIONAL"},
    {"id_ilap": "KM024", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN KOMUNIKASI DAN INFORMATIKA"},
    {"id_ilap": "KM025", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN KOPERASI DAN UKM"},
    {"id_ilap": "KM026", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN PERTANIAN"},
    {"id_ilap": "KM027", "id_kategori": "KM", "nama_ilap": "PUSAT DATA DAN INFORMASI (PUSDATIN), KEMENTERIAN ENERGI DAN SUMBER DAYA MINERAL"},
    {"id_ilap": "KM028", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL MINYAK DAN GAS BUMI, KEMENTERIAN ENERGI DAN SUMBER DAYA MINERAL"},
    {"id_ilap": "KM029", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL PERHUBUNGAN LAUT"},
    {"id_ilap": "KM030", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL PEMBERDAYAAN SOSIAL, KEMENTERIAN SOSIAL"},
    {"id_ilap": "KM031", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL KEKAYAAN NEGARA, KEMENTERIAN KEUANGAN"},
    {"id_ilap": "KM032", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN RISET, TEKNOLOGI, DAN PENDIDIKAN TINGGI"},
    {"id_ilap": "KM033", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN KEUANGAN"},
    {"id_ilap": "KM034", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN PARIWISATA DAN EKONOMI KREATIF / BADAN PARIWISATA DAN EKONOMI KREATIF"},
    {"id_ilap": "KM035", "id_kategori": "KM", "nama_ilap": "DIREKTORAT JENDERAL PENGELOLAAN PEMBIAYAAN DAN RISIKO, KEMENTERIAN KEUANGAN"},
    {"id_ilap": "KM036", "id_kategori": "KM", "nama_ilap": "BADAN PENGELOLA DANA PERKEBUNAN KELAPA SAWIT (BPDPKS)"},
    {"id_ilap": "KM037", "id_kategori": "KM", "nama_ilap": "KEMENTERIAN SEKRETARIAT NEGARA"},
    {"id_ilap": "KM038", "id_kategori": "KM", "nama_ilap": "KEMETERIAN LUAR NEGERI"},
    {"id_ilap": "LM001", "id_kategori": "LM", "nama_ilap": "KOMISI PEMILIHAN UMUM"},
    {"id_ilap": "LM002", "id_kategori": "LM", "nama_ilap": "LEMBAGA KEBIJAKAN PENGADAAN BARANG/JASA PEMERINTAH (LKPP)"},
    {"id_ilap": "LM003", "id_kategori": "LM", "nama_ilap": "BADAN PUSAT STATISTIK"},
    {"id_ilap": "LM004", "id_kategori": "LM", "nama_ilap": "BADAN KOORDINASI PENANAMAN MODAL"},
    {"id_ilap": "LM005", "id_kategori": "LM", "nama_ilap": "PUSAT LAYANAN PENGADAAN SECARA ELEKTRONIK KEMENTERIAN KEUANGAN"},
    {"id_ilap": "LM006", "id_kategori": "LM", "nama_ilap": "KEPOLISIAN NEGARA REPUBLIK INDONESIA (POLRI)"},
    {"id_ilap": "LM007", "id_kategori": "LM", "nama_ilap": "LEMBAGA PENERBANGAN DAN ANTARIKSA NASIONAL (LAPAN)"},
    {"id_ilap": "LM008", "id_kategori": "LM", "nama_ilap": "SATUAN KERJA KHUSUS PELAKSANA KEGIATAN USAHA HULU MINYAK DAN GAS BUMI"},
    {"id_ilap": "LM009", "id_kategori": "LM", "nama_ilap": "BADAN PENGAWASAN OBAT DAN MAKANAN (BPOM)"},
    {"id_ilap": "LM010", "id_kategori": "LM", "nama_ilap": "OTORITAS JASA KEUANGAN"},
    {"id_ilap": "LM011", "id_kategori": "LM", "nama_ilap": "BADAN STANDARDISASI NASIONAL (BSN)"},
    {"id_ilap": "LM012", "id_kategori": "LM", "nama_ilap": "PUSAT PELAPORAN DAN ANALISIS TRANSAKSI KEUANGAN (PPATK)"},
    {"id_ilap": "LM013", "id_kategori": "LM", "nama_ilap": "BADAN PENGUSAHAAN KAWASAN PERDAGANGAN BEBAS DAN PELABUHAN BEBAS BATAM (BP BATAM)"},
    {"id_ilap": "LM016", "id_kategori": "LM", "nama_ilap": "BADAN INFORMASI GEOSPASIAL"},
    {"id_ilap": "LM017", "id_kategori": "LM", "nama_ilap": "BADAN PENGATUR HILIR MINYAK DAN GAS BUMI (BPH MIGAS)"},
    {"id_ilap": "LM018", "id_kategori": "LM", "nama_ilap": "KOMISI PENGAWASAN PERSAINGAN USAHA"},
    {"id_ilap": "LM019", "id_kategori": "LM", "nama_ilap": "LEMBAGA PEMBIAYAAN EKSPOR INDONESIA (INDONESIA EXIMBANK)"},
    {"id_ilap": "PL001", "id_kategori": "PL", "nama_ilap": "PT SUCOFINDO"},
    {"id_ilap": "PL002", "id_kategori": "PL", "nama_ilap": "PT JAKARTA INTERNATIONAL CONTAINER TERMINAL"},
    {"id_ilap": "PL003", "id_kategori": "PL", "nama_ilap": "PT MUSTIKA ALAM LESTARI"},
    {"id_ilap": "PL004", "id_kategori": "PL", "nama_ilap": "PT TERMINAL PETI KEMAS KOJA"},
    {"id_ilap": "PL005", "id_kategori": "PL", "nama_ilap": "PT TERMINAL PETI KEMAS SURABAYA"},
    {"id_ilap": "PL006", "id_kategori": "PL", "nama_ilap": "PT SURVEYOR INDONESIA"},
    {"id_ilap": "PL007", "id_kategori": "PL", "nama_ilap": "PT KUSTODIAN SENTRAL EFEK INDONESIA"},
    {"id_ilap": "PL008", "id_kategori": "PL", "nama_ilap": "MASYARAKAT PROFESI PENILAI INDONESIA (MAPPI)"},
    {"id_ilap": "PL009", "id_kategori": "PL", "nama_ilap": "PT CARSURIN"},
    {"id_ilap": "PL010", "id_kategori": "PL", "nama_ilap": "PT GEOSERVICES"},
    {"id_ilap": "PL011", "id_kategori": "PL", "nama_ilap": "PUSAT PEMBINAAN PROFESI KEUANGAN, SEKRETARIAT JENDERAL KEMENTERIAN KEUANGAN"},
    {"id_ilap": "PL012", "id_kategori": "PL", "nama_ilap": "PT TASPEN (PERSERO)"},
    {"id_ilap": "PL013", "id_kategori": "PL", "nama_ilap": "CITIBANK N.A"},
    {"id_ilap": "PL014", "id_kategori": "PL", "nama_ilap": "PAN INDONESIA BANK, LTD. TBK."},
    {"id_ilap": "PL015", "id_kategori": "PL", "nama_ilap": "PT BANK ANZ INDONESIA"},
    {"id_ilap": "PL016", "id_kategori": "PL", "nama_ilap": "PT BANK BUKOPIN, TBK."},
    {"id_ilap": "PL017", "id_kategori": "PL", "nama_ilap": "PT BANK CENTRAL ASIA, TBK."},
    {"id_ilap": "PL018", "id_kategori": "PL", "nama_ilap": "PT BANK CIMB NIAGA, TBK."},
    {"id_ilap": "PL019", "id_kategori": "PL", "nama_ilap": "PT BANK DANAMON INDONESIA, TBK."},
    {"id_ilap": "PL020", "id_kategori": "PL", "nama_ilap": "PT BANK MNC INTERNASIONAL"},
    {"id_ilap": "PL021", "id_kategori": "PL", "nama_ilap": "PT BANK ICBC INDONESIA"},
    {"id_ilap": "PL022", "id_kategori": "PL", "nama_ilap": "PT BANK MAYBANK INDONESIA, TBK."},
    {"id_ilap": "PL023", "id_kategori": "PL", "nama_ilap": "PT BANK MANDIRI (PERSERO), TBK."},
    {"id_ilap": "PL024", "id_kategori": "PL", "nama_ilap": "PT BANK MEGA, TBK."},
    {"id_ilap": "PL025", "id_kategori": "PL", "nama_ilap": "PT BANK NEGARA INDONESIA 1946 (PERSERO), TBK."},
    {"id_ilap": "PL026", "id_kategori": "PL", "nama_ilap": "PT BANK NEGARA INDONESIA SYARIAH"},
    {"id_ilap": "PL027", "id_kategori": "PL", "nama_ilap": "PT BANK OCBC NISP, TBK."},
    {"id_ilap": "PL028", "id_kategori": "PL", "nama_ilap": "PT BANK PERMATA, TBK."},
    {"id_ilap": "PL029", "id_kategori": "PL", "nama_ilap": "PT BANK RAKYAT INDONESIA (PERSERO), TBK."},
    {"id_ilap": "PL030", "id_kategori": "PL", "nama_ilap": "PT BANK SINARMAS, TBK"},
    {"id_ilap": "PL031", "id_kategori": "PL", "nama_ilap": "PT BANK UOB INDONESIA"},
    {"id_ilap": "PL032", "id_kategori": "PL", "nama_ilap": "STANDARD CHARTERED BANK"},
    {"id_ilap": "PL033", "id_kategori": "PL", "nama_ilap": "THE HONGKONG & SHANGHAI BANKING CORP."},
    {"id_ilap": "PL034", "id_kategori": "PL", "nama_ilap": "PT BANK QNB INDONESIA"},
    {"id_ilap": "PL035", "id_kategori": "PL", "nama_ilap": "PT AEON CREDIT SERVICES"},
    {"id_ilap": "PL036", "id_kategori": "PL", "nama_ilap": "PT HUTCHISON 3 INDONESIA"},
    {"id_ilap": "PL037", "id_kategori": "PL", "nama_ilap": "PT INDOSAT TBK"},
    {"id_ilap": "PL038", "id_kategori": "PL", "nama_ilap": "PT SAMPOERNA TELEKOMUNIKASI INDONESIA"},
    {"id_ilap": "PL039", "id_kategori": "PL", "nama_ilap": "PT SMARTFREN TELECOM TBK (Seluler)"},
    {"id_ilap": "PL040", "id_kategori": "PL", "nama_ilap": "PT SMART TELECOM"},
    {"id_ilap": "PL041", "id_kategori": "PL", "nama_ilap": "PT TELEKOMUNIKASI SELULAR"},
    {"id_ilap": "PL042", "id_kategori": "PL", "nama_ilap": "PT XL AXIATA TBK"},
    {"id_ilap": "PL043", "id_kategori": "PL", "nama_ilap": "PT INDOSAT MEGA MEDIA"},
    {"id_ilap": "PL044", "id_kategori": "PL", "nama_ilap": "PT TELEKOMUNIKASI INDONESIA (PERSERO) TBK"},
    {"id_ilap": "PL045", "id_kategori": "PL", "nama_ilap": "PT BATAM BINTAN TELEKOMUNIKASI"},
    {"id_ilap": "PL046", "id_kategori": "PL", "nama_ilap": "PT SMARTFREN TELECOM TBK (Lokal)"},
    {"id_ilap": "PL047", "id_kategori": "PL", "nama_ilap": "DANA PENSIUN LEMBAGA KEUANGAN (DPLK) DAN DANA PENSIUN PEMBERI KERJA (DPPK)"},
    {"id_ilap": "PL048", "id_kategori": "PL", "nama_ilap": "DEALER UTAMA PROGRAM PENGAMPUNAN SUKARELA (PPS)"},
    {"id_ilap": "PL903", "id_kategori": "PL", "nama_ilap": "DIREKTORAT PERATURAN PERPAJAKAN II"},
    {"id_ilap": "PL906", "id_kategori": "PL", "nama_ilap": "DIREKTORAT EKSTENSIFIKASI DAN PENILAIAN"},
    {"id_ilap": "PL913", "id_kategori": "PL", "nama_ilap": "DIREKTORAT TRANSFORMASI PROSES BISNIS"},
    {"id_ilap": "PL914", "id_kategori": "PL", "nama_ilap": "DIREKTORAT PERPAJAKAN INTERNASIONAL"},
    {"id_ilap": "PL915", "id_kategori": "PL", "nama_ilap": "DIREKTORAT INTELIJEN PERPAJAKAN"},
    {"id_ilap": "PD001", "id_kategori": "PD", "nama_ilap": "KABUPATEN SERANG"},
    {"id_ilap": "PD002", "id_kategori": "PD", "nama_ilap": "KABUPATEN SUKABUMI"},
    {"id_ilap": "PD003", "id_kategori": "PD", "nama_ilap": "KABUPATEN BEKASI"},
    {"id_ilap": "PD004", "id_kategori": "PD", "nama_ilap": "KABUPATEN TEGAL"},
    {"id_ilap": "PD005", "id_kategori": "PD", "nama_ilap": "KABUPATEN BANJARNEGARA"},
    {"id_ilap": "PD006", "id_kategori": "PD", "nama_ilap": "KOTA YOGYAKARTA"},
    {"id_ilap": "PD007", "id_kategori": "PD", "nama_ilap": "KOTA SURABAYA"},
    {"id_ilap": "PD008", "id_kategori": "PD", "nama_ilap": "KABUPATEN BANGKALAN"},
    {"id_ilap": "PD009", "id_kategori": "PD", "nama_ilap": "KOTA KEDIRI"},
    {"id_ilap": "PD010", "id_kategori": "PD", "nama_ilap": "KOTA DENPASAR"},
    {"id_ilap": "PD011", "id_kategori": "PD", "nama_ilap": "KABUPATEN LOMBOK BARAT"},
    {"id_ilap": "PD012", "id_kategori": "PD", "nama_ilap": "KOTA BANDA ACEH"},
]


def seed_ilap(apps, schema_editor):
    """Seeds the ILAP table with initial data."""
    ILAP = apps.get_model("diamond_web", "ILAP")
    KategoriIlap = apps.get_model("diamond_web", "KategoriIlap")
    KategoriWilayah = apps.get_model("diamond_web", "KategoriWilayah")
    
    # Get the kategori_wilayah objects
    internasional = KategoriWilayah.objects.get(deskripsi="Internasional")
    regional = KategoriWilayah.objects.get(deskripsi="Regional")
    nasional = KategoriWilayah.objects.get(deskripsi="Nasional")
    
    for item in ILAP_DATA:
        kategori = KategoriIlap.objects.get(id_kategori=item["id_kategori"])
        
        # Determine kategori_wilayah based on id_kategori
        if item["id_kategori"] == "EI":
            kategori_wilayah = internasional
        elif item["id_kategori"] in ["PV", "PD"]:
            kategori_wilayah = regional
        else:
            kategori_wilayah = nasional
        
        ILAP.objects.get_or_create(
            id_ilap=item["id_ilap"],
            defaults={
                "id_kategori": kategori,
                "nama_ilap": item["nama_ilap"],
                "id_kategori_wilayah": kategori_wilayah
            }
        )


def unseed_ilap(apps, schema_editor):
    """Removes the initial data from the ILAP table."""
    ILAP = apps.get_model("diamond_web", "ILAP")
    ids_to_delete = [item["id_ilap"] for item in ILAP_DATA]
    ILAP.objects.filter(id_ilap__in=ids_to_delete).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0005_seed_kategori_wilayah"),
    ]

    operations = [
        migrations.RunPython(seed_ilap, reverse_code=unseed_ilap),
    ]
