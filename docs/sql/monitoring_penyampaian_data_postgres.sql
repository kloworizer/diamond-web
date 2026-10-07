-- Monitoring Penyampaian Data (PostgreSQL) — semua sub jenis data, tanpa filter.
-- Satu baris per periode jenis data x periode penerimaan, dari start_date
-- sampai end_date (atau hari ini).
--
-- Aturan (sama dengan halaman):
--   * Periode mengikuti kalender: Bulanan 1 = Januari, Triwulan III = Jul-Sep,
--     Semester II = Jul-Des, Tahunan = 1 Jan - 31 Des. Start date di tengah
--     periode tetap memantau periode itu (start 15-03 -> mulai Maret).
--   * Penyampaian Harian/Mingguan/2 Mingguan selalu diterima Bulanan.
--   * Batas penyampaian = akhir periode + akhir_penyampaian hari.
--   * Tiket penyampaian yang dipakai = id terbesar yang tidak Dibatalkan (status 7).
--   * ILAP Regional dinilai dari tgl_terima_vertikal, fallback ke tgl_terima_dip.
SELECT
    i.id_ilap || ' - ' || i.nama_ilap                       AS ilap,
    jdi.id_sub_jenis_data || ' - ' || jdi.nama_sub_jenis_data AS jenis_data,
    pp.periode_penyampaian,
    pen.periode_penerimaan,
    CASE st.bulan
        WHEN 1  THEN (ARRAY['Januari','Februari','Maret','April','Mei','Juni','Juli',
                            'Agustus','September','Oktober','November','Desember'])[n]
        WHEN 3  THEN 'Triwulan ' || (ARRAY['I','II','III','IV'])[n]
        WHEN 6  THEN 'Semester ' || (ARRAY['I','II'])[n]
        WHEN 12 THEN y::text
    END                                                     AS periode,
    y                                                       AS tahun,
    prd.awal                                                AS awal_periode,
    prd.akhir                                               AS akhir_periode,
    prd.akhir + pjd.akhir_penyampaian                       AS batas_penyampaian,
    tk.nomor_tiket,
    tk.tgl_terima::date                                     AS tgl_terima,
    CASE WHEN tk.id IS NOT NULL THEN 'Sudah Menyampaikan' ELSE 'Belum Menyampaikan' END
                                                            AS status_penyampaian,
    CASE WHEN tk.id IS NOT NULL
         THEN CASE WHEN tk.tgl_terima::date > prd.akhir + pjd.akhir_penyampaian THEN 'Ya' ELSE 'Tidak' END
         ELSE CASE WHEN CURRENT_DATE > prd.akhir + pjd.akhir_penyampaian THEN 'Ya' ELSE 'Tidak' END
    END                                                     AS terlambat,
    (prd.akhir + pjd.akhir_penyampaian) - CURRENT_DATE      AS hari
FROM periode_jenis_data pjd
JOIN periode_pengiriman pp ON pp.id = pjd.id_periode_pengiriman
JOIN jenis_data_ilap   jdi ON jdi.id = pjd.id_sub_jenis_data_ilap
JOIN ilap              i   ON i.id  = jdi.id_ilap
JOIN kategori_wilayah  kw  ON kw.id = i.id_kategori_wilayah
-- periode penerimaan efektif dan jumlah bulan per periode
CROSS JOIN LATERAL (
    SELECT CASE WHEN lower(pp.periode_penyampaian) IN ('harian', 'mingguan', '2 mingguan')
                THEN 'Bulanan' ELSE pp.periode_penerimaan END AS periode_penerimaan
) pen
CROSS JOIN LATERAL (
    SELECT CASE lower(trim(pen.periode_penerimaan))
               WHEN 'bulanan'    THEN 1
               WHEN 'triwulanan' THEN 3
               WHEN 'kuartal'    THEN 3
               WHEN 'semester'   THEN 6
               WHEN 'semesteran' THEN 6
               WHEN 'tahunan'    THEN 12
           END AS bulan
) st
-- setiap tahun dari start_date s/d end_date (atau hari ini), dan setiap periode di tahun itu
CROSS JOIN LATERAL generate_series(EXTRACT(YEAR FROM pjd.start_date)::int,
                                   EXTRACT(YEAR FROM coalesce(pjd.end_date, CURRENT_DATE))::int) AS y
CROSS JOIN LATERAL generate_series(1, 12 / st.bulan) AS n
CROSS JOIN LATERAL (
    SELECT make_date(y, (n - 1) * st.bulan + 1, 1)                                         AS awal,
           (make_date(y, (n - 1) * st.bulan + 1, 1) + make_interval(months => st.bulan))::date - 1 AS akhir
) prd
-- tiket penyampaian terbaru yang tidak Dibatalkan
LEFT JOIN LATERAL (
    SELECT t.id,
           t.nomor_tiket,
           CASE WHEN lower(kw.deskripsi) LIKE '%regional%'
                THEN coalesce(t.tgl_terima_vertikal, t.tgl_terima_dip)
                ELSE t.tgl_terima_dip END AS tgl_terima
    FROM tiket t
    WHERE t.id_periode_data = pjd.id
      AND t.periode         = n
      AND t.tahun           = y
      AND t.penyampaian     = 1
      AND t.status_tiket   <> 7
    ORDER BY t.id DESC
    LIMIT 1
) tk ON true
WHERE prd.akhir >= pjd.start_date
  AND prd.awal  <= coalesce(pjd.end_date, CURRENT_DATE)
ORDER BY i.nama_ilap, jdi.id_sub_jenis_data, prd.awal;
