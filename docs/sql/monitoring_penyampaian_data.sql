-- =============================================================================
-- Monitoring Penyampaian Data — padanan SQL dari
-- diamond_web/views/monitoring_penyampaian_data.py :: monitoring_penyampaian_data_data
--
-- Dialek : SQLite >= 3.25 (window function + recursive CTE + JSON1).
-- Hasil  : satu baris per (periode_jenis_data x periode penerimaan), kolom sama
--          dengan tabel di halaman + records_total / records_filtered DataTables.
--
-- Aturan:
--   * Periode mengikuti kalender (Bulanan 1 = Januari, Triwulan III = Jul-Sep,
--     Semesteran II = Jul-Des, Tahunan = 1 Jan - 31 Des). Periode yang sebagian
--     masih berada di dalam start_date ikut dipantau (start 15-03 -> mulai Maret).
--   * Batas penyampaian = akhir periode + akhir_penyampaian hari.
--   * Penyampaian Harian/Mingguan/2 Mingguan selalu diterima Bulanan.
--   * Tiket Dibatalkan (status_tiket = 7) tidak dihitung menyampaikan.
--   * ILAP Regional dinilai dari tgl_terima_vertikal, fallback ke tgl_terima_dip.
--
-- Cara pakai: ubah nilai di blok PARAMS saja. Filter multi-pilih ditulis sebagai
-- array JSON; '[]' = "-- Semua --".
--   id numerik  : '[1, 2]'            (tahun, pic_p3de, kategori_ilap, ilap, kanwil,
--                                      kpp, kategori_wilayah, jenis_tabel,
--                                      dasar_hukum, periode_pengiriman)
--   kode teks   : '["DA00101"]'       (jenis_data, sub_jenis_data)
--   status      : '["Belum Menyampaikan"]', terlambat: '["Ya"]'
-- =============================================================================
WITH RECURSIVE
-- >>> PARAMS
params AS (
    SELECT
        date('now', 'localtime') AS today,      -- datetime.now().date()
        1                        AS user_id,    -- auth_user.id yang membuka halaman
        '[]' AS f_tahun,
        '[]' AS f_pic_p3de,
        '[]' AS f_kategori_ilap,
        '[]' AS f_ilap,
        '[]' AS f_jenis_data,
        '[]' AS f_sub_jenis_data,
        '[]' AS f_kanwil,
        '[]' AS f_kpp,
        '[]' AS f_kategori_wilayah,
        '[]' AS f_jenis_tabel,
        '[]' AS f_dasar_hukum,
        '[]' AS f_periode_pengiriman,
        '[]' AS f_status_penyampaian,
        '[]' AS f_terlambat,
        'ilap_name' AS order_col,               -- kolom sort DataTables (default order [[0,'asc']])
        0    AS order_desc,                     -- 1 = desc
        0    AS start_row,                      -- DataTables `start`
        10   AS page_length                     -- DataTables `length`
),
-- <<< PARAMS

-- ---------------------------------------------------------------------------
-- 1. Hak akses user
--    Boleh membuka : admin, admin_p3de, user_p3de, kasi_p3de
--    Lihat semua   : superuser, admin, admin_p3de, kasi_p3de
--    Selain itu    : hanya sub jenis data tempat dia PIC P3DE aktif
-- ---------------------------------------------------------------------------
usr AS (
    SELECT
        u.id,
        EXISTS (SELECT 1 FROM auth_user_groups ug JOIN auth_group g ON g.id = ug.group_id
                WHERE ug.user_id = u.id
                  AND g.name IN ('admin', 'admin_p3de', 'user_p3de', 'kasi_p3de'))  AS can_open,
        u.is_superuser OR EXISTS (
                SELECT 1 FROM auth_user_groups ug JOIN auth_group g ON g.id = ug.group_id
                WHERE ug.user_id = u.id
                  AND g.name IN ('admin', 'admin_p3de', 'kasi_p3de'))               AS sees_all
    FROM auth_user u
    JOIN params p ON u.id = p.user_id
),

-- Tahun terpilih (hanya yang berupa angka, seperti `year.isdigit()`)
tahun_sel AS (
    SELECT CAST(value AS INTEGER) AS y
    FROM params, json_each(params.f_tahun)
    WHERE CAST(value AS TEXT) GLOB '[0-9]*'
),

-- ---------------------------------------------------------------------------
-- 2. PeriodeJenisData yang lolos hak akses + filter kolom (apply_filters)
-- ---------------------------------------------------------------------------
pjd AS (
    SELECT
        pjd.id                     AS pjd_id,
        pjd.akhir_penyampaian,
        CASE WHEN lower(pp.periode_penyampaian) IN ('harian', 'mingguan', '2 mingguan')
             THEN 'Bulanan' ELSE pp.periode_penerimaan END
                                   AS periode_penerimaan,
        jdi.id_sub_jenis_data,
        jdi.nama_jenis_data,
        jdi.nama_sub_jenis_data,
        i.id                       AS ilap_pk,
        i.id_ilap,
        i.nama_ilap,
        lower(kw.deskripsi) LIKE '%regional%' AS is_regional,
        -- Jendela periode: start_date .. (end_date atau hari ini), dipotong ke
        -- 1 Jan tahun terkecil .. 31 Des tahun terbesar yang dipilih
        CASE WHEN (SELECT min(y) FROM tahun_sel) IS NOT NULL
                  AND printf('%04d-01-01', (SELECT min(y) FROM tahun_sel)) > pjd.start_date
             THEN printf('%04d-01-01', (SELECT min(y) FROM tahun_sel))
             ELSE pjd.start_date END                                     AS gen_start,
        CASE WHEN (SELECT max(y) FROM tahun_sel) IS NOT NULL
                  AND printf('%04d-12-31', (SELECT max(y) FROM tahun_sel)) < coalesce(pjd.end_date, p.today)
             THEN printf('%04d-12-31', (SELECT max(y) FROM tahun_sel))
             ELSE coalesce(pjd.end_date, p.today) END                    AS gen_end
    FROM periode_jenis_data pjd
    CROSS JOIN params p
    CROSS JOIN usr
    JOIN periode_pengiriman pp ON pp.id = pjd.id_periode_pengiriman
    JOIN jenis_data_ilap   jdi ON jdi.id = pjd.id_sub_jenis_data_ilap
    JOIN ilap              i   ON i.id  = jdi.id_ilap
    JOIN kategori_wilayah  kw  ON kw.id = i.id_kategori_wilayah
    WHERE
        usr.can_open
        AND (usr.sees_all OR EXISTS (
                SELECT 1 FROM pic
                WHERE pic.id_sub_jenis_data_ilap = jdi.id
                  AND pic.tipe = 'P3DE'
                  AND pic.id_user = usr.id
                  AND pic.start_date <= p.today
                  AND (pic.end_date IS NULL OR pic.end_date >= p.today)))
        -- tahun: rentang aktif menyentuh salah satu tahun terpilih
        AND (NOT EXISTS (SELECT 1 FROM tahun_sel) OR EXISTS (
                SELECT 1 FROM tahun_sel
                WHERE pjd.start_date <= printf('%04d-12-31', y)
                  AND (pjd.end_date IS NULL OR pjd.end_date >= printf('%04d-01-01', y))))
        -- pic_p3de: sub jenis data punya PIC P3DE aktif dari user terpilih
        AND (json_array_length(p.f_pic_p3de) = 0 OR EXISTS (
                SELECT 1 FROM pic
                WHERE pic.id_sub_jenis_data_ilap = jdi.id
                  AND pic.tipe = 'P3DE'
                  AND pic.id_user IN (SELECT CAST(value AS INTEGER) FROM json_each(p.f_pic_p3de))
                  AND pic.start_date <= p.today
                  AND (pic.end_date IS NULL OR pic.end_date >= p.today)))
        -- kanwil: langsung (PV) atau lewat KPP (PD)
        AND (json_array_length(p.f_kanwil) = 0 OR EXISTS (
                SELECT 1 FROM ilap_kpp r
                LEFT JOIN kpp k ON k.id = r.id_kpp
                WHERE r.id_ilap = i.id
                  AND (r.id_kanwil       IN (SELECT CAST(value AS INTEGER) FROM json_each(p.f_kanwil))
                       OR k.id_kanwil_id IN (SELECT CAST(value AS INTEGER) FROM json_each(p.f_kanwil)))))
        AND (json_array_length(p.f_kpp) = 0 OR EXISTS (
                SELECT 1 FROM ilap_kpp r
                WHERE r.id_ilap = i.id
                  AND r.id_kpp IN (SELECT CAST(value AS INTEGER) FROM json_each(p.f_kpp))))
        AND (json_array_length(p.f_kategori_wilayah) = 0
             OR i.id_kategori_wilayah IN (SELECT CAST(value AS INTEGER) FROM json_each(p.f_kategori_wilayah)))
        AND (json_array_length(p.f_kategori_ilap) = 0
             OR i.id_kategori IN (SELECT CAST(value AS INTEGER) FROM json_each(p.f_kategori_ilap)))
        AND (json_array_length(p.f_ilap) = 0
             OR i.id IN (SELECT CAST(value AS INTEGER) FROM json_each(p.f_ilap)))
        AND (json_array_length(p.f_jenis_data) = 0
             OR jdi.id_jenis_data IN (SELECT value FROM json_each(p.f_jenis_data)))
        AND (json_array_length(p.f_sub_jenis_data) = 0
             OR jdi.id_sub_jenis_data IN (SELECT value FROM json_each(p.f_sub_jenis_data)))
        AND (json_array_length(p.f_jenis_tabel) = 0
             OR jdi.id_jenis_tabel IN (SELECT CAST(value AS INTEGER) FROM json_each(p.f_jenis_tabel)))
        AND (json_array_length(p.f_dasar_hukum) = 0 OR EXISTS (
                SELECT 1 FROM klasifikasi_jenis_data kjd
                WHERE kjd.id_sub_jenis_data = jdi.id
                  AND kjd.id_klasifikasi_tabel IN (SELECT CAST(value AS INTEGER) FROM json_each(p.f_dasar_hukum))))
        AND (json_array_length(p.f_periode_pengiriman) = 0
             OR pjd.id_periode_pengiriman IN (SELECT CAST(value AS INTEGER) FROM json_each(p.f_periode_pengiriman)))
),

-- Jumlah bulan per periode; 0 = tipe berbasis hari (Harian/Mingguan/2 Mingguan
-- sebagai periode_penerimaan, atau tipe tak dikenal -> per hari)
pjd_step AS (
    SELECT pjd.*,
        CASE lower(trim(periode_penerimaan))
            WHEN 'bulanan'    THEN 1
            WHEN 'triwulanan' THEN 3
            WHEN 'kuartal'    THEN 3
            WHEN 'semester'   THEN 6
            WHEN 'semesteran' THEN 6
            WHEN 'tahunan'    THEN 12
            ELSE 0 END                                   AS step_months,
        CASE lower(trim(periode_penerimaan))
            WHEN 'mingguan'   THEN 7
            WHEN '2 mingguan' THEN 14
            ELSE 1 END                                   AS step_days
    FROM pjd
    WHERE gen_start <= gen_end
),

-- ---------------------------------------------------------------------------
-- 3. Periode kalender: (tahun x nomor periode) yang beririsan dengan jendela
-- ---------------------------------------------------------------------------
years (y) AS (
    SELECT CAST(strftime('%Y', min(gen_start)) AS INTEGER) FROM pjd_step
    UNION ALL
    SELECT y + 1 FROM years
    WHERE y < (SELECT CAST(strftime('%Y', max(gen_end)) AS INTEGER) FROM pjd_step)
),
nums (n) AS (VALUES (1),(2),(3),(4),(5),(6),(7),(8),(9),(10),(11),(12)),

calendar_periods AS (
    SELECT
        s.pjd_id,
        nums.n                                                            AS periode_num,
        years.y                                                           AS tahun,
        printf('%04d-%02d-01', years.y, (nums.n - 1) * s.step_months + 1) AS period_start,
        date(printf('%04d-%02d-01', years.y, (nums.n - 1) * s.step_months + 1),
             printf('+%d months', s.step_months), '-1 day')               AS period_end
    FROM pjd_step s
    JOIN years ON years.y BETWEEN CAST(strftime('%Y', s.gen_start) AS INTEGER)
                              AND CAST(strftime('%Y', s.gen_end)   AS INTEGER)
    JOIN nums  ON nums.n <= 12 / s.step_months
    WHERE s.step_months > 0
),

-- Tipe berbasis hari: melangkah dari gen_start, nomor direset tiap tahun
day_steps (pjd_id, period_start, gen_end, step_days) AS (
    SELECT pjd_id, gen_start, gen_end, step_days FROM pjd_step WHERE step_months = 0
    UNION ALL
    SELECT pjd_id, date(period_start, printf('+%d days', step_days)), gen_end, step_days
    FROM day_steps
    WHERE date(period_start, printf('+%d days', step_days)) <= gen_end
),

periods AS (
    SELECT pjd_id, periode_num, tahun, period_start, period_end
    FROM calendar_periods cp
    WHERE cp.period_end   >= (SELECT gen_start FROM pjd_step s WHERE s.pjd_id = cp.pjd_id)
      AND cp.period_start <= (SELECT gen_end   FROM pjd_step s WHERE s.pjd_id = cp.pjd_id)
    UNION ALL
    SELECT pjd_id,
        ROW_NUMBER() OVER (PARTITION BY pjd_id, strftime('%Y', period_start) ORDER BY period_start),
        CAST(strftime('%Y', period_start) AS INTEGER),
        period_start,
        date(period_start, printf('+%d days', step_days), '-1 day')
    FROM day_steps
),

-- Angka romawi 1..3999 untuk format_periode (Triwulan/Kuartal/Semester)
roman (d, h, t, o) AS (
    VALUES (0, '',     '',     ''),    (1, 'C',    'X',    'I'),
           (2, 'CC',   'XX',   'II'),  (3, 'CCC',  'XXX',  'III'),
           (4, 'CD',   'XL',   'IV'),  (5, 'D',    'L',    'V'),
           (6, 'DC',   'LX',   'VI'),  (7, 'DCC',  'LXX',  'VII'),
           (8, 'DCCC', 'LXXX', 'VIII'),(9, 'CM',   'XC',   'IX')
),

-- ---------------------------------------------------------------------------
-- 4. Baris monitoring: tiket terbaru yang tidak Dibatalkan, deadline, status
-- ---------------------------------------------------------------------------
rows_all AS (
    SELECT
        pr.pjd_id                               AS id_periode_data,
        s.ilap_pk,
        s.id_ilap,
        s.nama_ilap                             AS ilap_name,
        s.id_sub_jenis_data,
        s.nama_jenis_data,
        s.nama_sub_jenis_data,
        s.periode_penerimaan,
        s.is_regional,
        pr.periode_num,
        pr.tahun,
        pr.period_start,
        date(pr.period_end, printf('%+d days', s.akhir_penyampaian))       AS deadline_date,
        (SELECT max(t.id) FROM tiket t
          WHERE t.id_periode_data = pr.pjd_id
            AND t.periode         = pr.periode_num
            AND t.tahun           = pr.tahun
            AND t.penyampaian     = 1
            AND t.status_tiket   <> 7)                                      AS tiket_id
    FROM periods pr
    JOIN pjd_step s ON s.pjd_id = pr.pjd_id
),

rows_labeled AS (
    SELECT
        r.*,
        CASE WHEN r.tiket_id IS NOT NULL THEN 'Sudah Menyampaikan' ELSE 'Belum Menyampaikan' END
                                                            AS status_penyampaian,
        CASE WHEN r.tiket_id IS NOT NULL
             THEN coalesce(date(CASE WHEN r.is_regional
                                     THEN coalesce(t.tgl_terima_vertikal, t.tgl_terima_dip)
                                     ELSE t.tgl_terima_dip END) > r.deadline_date, 0)
             ELSE p.today > r.deadline_date
        END                                                 AS is_late,
        CAST(julianday(r.deadline_date) - julianday(p.today) AS INTEGER)
                                                            AS days_diff,
        -- format_periode(periode_penerimaan, periode_num, tahun, include_year=False)
        CASE r.periode_penerimaan
            WHEN 'Harian'     THEN 'Hari ' || r.periode_num
            WHEN 'Mingguan'   THEN 'Minggu ' || r.periode_num
            WHEN '2 Mingguan' THEN '2 Minggu ' || r.periode_num
            WHEN 'Bulanan'    THEN CASE WHEN r.periode_num BETWEEN 1 AND 12
                                        THEN json_extract('["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"]',
                                                          printf('$[%d]', r.periode_num - 1))
                                        ELSE 'Bulan ' || r.periode_num END
            WHEN 'Tahunan'    THEN CAST(r.tahun AS TEXT)
            ELSE CASE
                WHEN r.periode_penerimaan IN ('Triwulanan', 'Kuartal', 'Semester', 'Semesteran') THEN
                    CASE r.periode_penerimaan
                        WHEN 'Triwulanan' THEN 'Triwulan '
                        WHEN 'Kuartal'    THEN 'Kuartal '
                        ELSE 'Semester ' END
                    || substr('MMM', 1, r.periode_num / 1000)
                    || (SELECT h FROM roman WHERE d = (r.periode_num / 100) % 10)
                    || (SELECT t FROM roman WHERE d = (r.periode_num / 10) % 10)
                    || (SELECT o FROM roman WHERE d = r.periode_num % 10)
                ELSE CAST(r.periode_num AS TEXT) END
        END                                                 AS periode_display_name
    FROM rows_all r
    CROSS JOIN params p
    LEFT JOIN tiket t ON t.id = r.tiket_id
),

rows_counted AS (
    SELECT rl.*,
        CASE WHEN rl.is_late THEN 'Ya' ELSE 'Tidak' END     AS status_terlambat,
        COUNT(*) OVER ()                                    AS records_total
    FROM rows_labeled rl
),

-- 5. Filter yang hanya bisa diterapkan setelah periode dibangkitkan
rows_filtered AS (
    SELECT rc.*, COUNT(*) OVER () AS records_filtered
    FROM rows_counted rc, params p
    WHERE (NOT EXISTS (SELECT 1 FROM tahun_sel) OR rc.tahun IN (SELECT y FROM tahun_sel))
      AND (json_array_length(p.f_status_penyampaian) = 0
           OR rc.status_penyampaian IN (SELECT value FROM json_each(p.f_status_penyampaian)))
      AND (json_array_length(p.f_terlambat) = 0
           OR rc.status_terlambat IN (SELECT value FROM json_each(p.f_terlambat)))
)

-- ---------------------------------------------------------------------------
-- 6. Output (kolom tabel halaman) + sort + paging
-- ---------------------------------------------------------------------------
SELECT
    f.id_ilap || ' - ' || f.ilap_name                         AS ilap,
    f.id_sub_jenis_data || ' - ' || f.nama_sub_jenis_data     AS jenis_data,
    f.periode_display_name                                    AS periode,
    f.tahun,
    strftime('%d-%m-%Y', f.deadline_date)                     AS deadline,
    f.status_penyampaian,
    f.status_terlambat,
    f.days_diff                                               AS hari,
    '/tiket/?ilap=' || f.ilap_pk || '&sub_jenis_data=' || f.id_sub_jenis_data
        || '&periode=' || f.periode_num || '&tahun=' || f.tahun
        || '&periode_penerimaan=' || replace(f.periode_penerimaan, ' ', '+')
                                                              AS url_lihat_tiket,
    '/tiket/rekam/?ilap_id=' || f.ilap_pk || '&periode_data_id=' || f.id_periode_data
        || '&periode=' || f.periode_num || '&tahun=' || f.tahun
                                                              AS url_rekam_tiket,
    f.records_total,
    f.records_filtered
FROM rows_filtered f
CROSS JOIN params p
ORDER BY
    -- Teks diurutkan lower-case; periode, tahun dan hari sebagai angka.
    CASE WHEN p.order_desc = 0 THEN
        CASE p.order_col
            WHEN 'ilap_name'          THEN lower(f.ilap_name)
            WHEN 'jenis_data'         THEN lower(f.nama_jenis_data)
            WHEN 'deadline_date'      THEN f.deadline_date
            WHEN 'status_penyampaian' THEN lower(f.status_penyampaian)
            WHEN 'status_terlambat'   THEN lower(f.status_terlambat)
        END END ASC,
    CASE WHEN p.order_desc = 0 THEN
        CASE p.order_col WHEN 'periode' THEN f.periode_num WHEN 'tahun' THEN f.tahun
                         WHEN 'days_diff' THEN f.days_diff END
    END ASC,
    CASE WHEN p.order_desc = 1 THEN
        CASE p.order_col
            WHEN 'ilap_name'          THEN lower(f.ilap_name)
            WHEN 'jenis_data'         THEN lower(f.nama_jenis_data)
            WHEN 'deadline_date'      THEN f.deadline_date
            WHEN 'status_penyampaian' THEN lower(f.status_penyampaian)
            WHEN 'status_terlambat'   THEN lower(f.status_terlambat)
        END END DESC,
    CASE WHEN p.order_desc = 1 THEN
        CASE p.order_col WHEN 'periode' THEN f.periode_num WHEN 'tahun' THEN f.tahun
                         WHEN 'days_diff' THEN f.days_diff END
    END DESC,
    -- tie-breaker = urutan pembangkitan di Python (PeriodeJenisData.id, lalu periode)
    f.id_periode_data,
    f.period_start
LIMIT (SELECT page_length FROM params) OFFSET (SELECT start_row FROM params);
