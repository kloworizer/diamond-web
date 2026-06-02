import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import transaction
from django.db.utils import IntegrityError


logger = logging.getLogger(__name__)


class OracleSyncConfigError(Exception):
    """Raised when Oracle sync configuration is invalid."""


def _discover_pmde_prioritas_years(
    connection_config: "OracleConnectionConfig" = None,
) -> list[int]:
    """Discover which PRIORITAS_* columns exist in REF_TABEL_PMDE table.
    
    Queries Oracle's user_tab_columns view to find columns matching PRIORITAS_<year> pattern.
    Returns a sorted list of years that have corresponding PRIORITAS columns.
    
    Args:
        connection_config: Optional OracleConnectionConfig. If not provided, skips discovery
                          and returns range 2022 to current year.
    
    Returns:
        Sorted list of year integers with PRIORITAS columns, or 2022-current_year if discovery fails.
    """
    if not connection_config:
        current_year = date.today().year
        return list(range(2022, current_year + 1))
    
    try:
        import oracledb
    except ImportError:
        logger.warning("oracledb not available, using default year range for PMDE query")
        current_year = date.today().year
        return list(range(2022, current_year + 1))
    
    try:
        # Build connection string for oracledb
        if connection_config.service_name:
            dsn = f"{connection_config.host}:{connection_config.port}/{connection_config.service_name}"
        else:
            dsn = f"{connection_config.host}:{connection_config.port}/{connection_config.sid}"
        
        logger.debug(f"Attempting to discover PMDE PRIORITAS columns from: {dsn}")
        
        conn = oracledb.connect(
            user=connection_config.user,
            password=connection_config.password,
            dsn=dsn,
        )
        cursor = conn.cursor()
        
        # Query user_tab_columns to find PRIORITAS_* columns
        cursor.execute("""
            SELECT COLUMN_NAME
            FROM user_tab_columns
            WHERE TABLE_NAME = 'REF_TABEL_PMDE'
            AND COLUMN_NAME LIKE 'PRIORITAS_%'
            ORDER BY COLUMN_NAME
        """)
        
        years: list[int] = []
        for (column_name,) in cursor.fetchall():
            # Extract year from PRIORITAS_YYYY format
            match = re.search(r"PRIORITAS_(\d{4})", column_name)
            if match:
                try:
                    year = int(match.group(1))
                    years.append(year)
                except ValueError:
                    pass
        
        cursor.close()
        conn.close()
        
        if years:
            logger.info(f"✓ Discovered PMDE PRIORITAS columns for years: {years}")
            return sorted(years)
        else:
            # Fallback to default if no columns found
            logger.warning("No PRIORITAS_* columns found in REF_TABEL_PMDE, using default year range")
            current_year = date.today().year
            return list(range(2022, current_year + 1))
            
    except Exception as e:
        error_msg = str(e)
        if "ORA-12170" in error_msg or "timeout" in error_msg.lower():
            logger.warning(
                f"Failed to discover PMDE PRIORITAS columns: Network timeout connecting to {connection_config.host}. "
                f"Using default year range. This may be a temporary issue."
            )
        elif "ORA-01017" in error_msg or "invalid" in error_msg.lower():
            logger.warning(
                f"Failed to discover PMDE PRIORITAS columns: Invalid credentials. "
                f"Check ORACLE_SECONDARY_USER and ORACLE_SECONDARY_PASSWORD."
            )
        else:
            logger.warning(f"Failed to discover PMDE PRIORITAS columns: {error_msg}. Using default year range.")
        current_year = date.today().year
        return list(range(2022, current_year + 1))


def _build_pmde_prioritas_query(
    start_year: int = 2022,
    discovered_years: list[int] | None = None,
) -> str:
    """Build UNION ALL query for PMDE prioritas data across multiple years.
    
    Args:
        start_year: Starting year (only used if discovered_years is None).
        discovered_years: Pre-discovered list of years with PRIORITAS columns.
                         If provided, will only query these years.
    
    Returns:
        SQL query string with UNION ALL across discovered years.
    """
    if discovered_years:
        years_to_query = sorted(discovered_years)
    else:
        current_year = date.today().year
        years_to_query = list(range(start_year, current_year + 1))
    
    union_queries: list[str] = []

    for year in years_to_query:
        union_queries.append(
            f"""
            SELECT DISTINCT
                ID_TABEL_S,
                DATE '{year}-01-01' AS START_DATE,
                DATE '{year}-12-31' AS END_DATE,
                'ND-' AS NO_ND,
                '{year}' AS TAHUN,
                DURASI
            FROM REF_TABEL_PMDE
            WHERE PRIORITAS_{year} = 1
            """.strip()
        )

    return "\nUNION ALL\n".join(union_queries)


@dataclass(frozen=True)
class OracleSyncTableConfig:
    name: str
    target_model_label: str
    target_key_field: str
    source_key_column: str
    field_map: dict[str, str]
    source_table: str = ""
    source_query: str = ""
    foreign_key_lookup_map: dict[str, str] = field(default_factory=dict)
    derived_field_map: dict[str, str] = field(default_factory=dict)
    match_fields: tuple[str, ...] = field(default_factory=tuple)
    where_clause: str = ""
    source_connection: str = "primary"


@dataclass(frozen=True)
class OracleConnectionConfig:
    name: str
    user: str
    password: str
    host: str
    port: int
    service_name: str
    sid: str


@dataclass
class OracleSyncSummary:
    table_name: str
    source_table: str
    target_model: str
    source_rows: int
    inserts: int
    updates: int
    unchanged: int
    errors: list[str] = field(default_factory=list)
    inserted_keys: list[str] = field(default_factory=list)
    updated_keys: list[str] = field(default_factory=list)
    skipped_rows_detail: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "table_name": self.table_name,
            "source_table": self.source_table,
            "target_model": self.target_model,
            "source_rows": self.source_rows,
            "inserts": self.inserts,
            "updates": self.updates,
            "unchanged": self.unchanged,
            "errors": self.errors,
            "inserted_keys": self.inserted_keys,
            "updated_keys": self.updated_keys,
        }


@dataclass
class OracleSyncBatchSummary:
    source_rows: int
    inserts: int
    updates: int
    unchanged: int
    errors: list[str]
    inserted_keys: list[str]
    updated_keys: list[str]
    table_summaries: list[OracleSyncSummary]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_rows": self.source_rows,
            "inserts": self.inserts,
            "updates": self.updates,
            "unchanged": self.unchanged,
            "errors": self.errors,
            "inserted_keys": self.inserted_keys,
            "updated_keys": self.updated_keys,
            "table_summaries": [summary.as_dict() for summary in self.table_summaries],
        }


# NOTE:
# Hardcode mapping tabel sync di sini.
# Tambahkan item baru jika source Oracle lebih dari satu tabel.
# PENTING: Urutan tabel harus mengikuti dependency (parent sebelum child)
HARD_CODED_SYNC_TABLES: list[OracleSyncTableConfig] = [
    # 1. Independent tables (no dependencies)
    OracleSyncTableConfig(
        name="kategori_ilap",
        source_table="PROD.APP_KATEGORI_ILAP",
        target_model_label="diamond_web.KategoriILAP",
        target_key_field="id_kategori",
        source_key_column="ID_KATEGORI_ILAP",
        field_map={
            "nama_kategori": "NAMA_KATEGORI",
            "create_date": "CREATE_DATE",
            "create_by": "CREATE_BY",
        },
        where_clause="",
    ),
    OracleSyncTableConfig(
        name="dasar_hukum",
        source_query="""
            SELECT
                ID_DSR_HUKUM,
                KET_DSR_HUKUM
            FROM P3DE.REF_DTL_DSR_HUKUM
        """,
        target_model_label="diamond_web.DasarHukum",
        target_key_field="deskripsi",
        source_key_column="KET_DSR_HUKUM",
        field_map={
            "deskripsi": "KET_DSR_HUKUM",
        },
        derived_field_map={
            "kategori": "kategori_from_id_dsr_hukum",
        },
        where_clause="",
    ),
    # 2. Depends on kategori_ilap
    OracleSyncTableConfig(
        name="ilap",
        source_query="""
            WITH CombinedData AS (
                SELECT
                    app.*,
                    1 AS PRIORITY 
                FROM
                    PROD.APP_ILAP app
                UNION ALL
                SELECT
                    ID_ILAP,
                    ID_KATEGORI AS ID_KATEGORI_ILAP,
                    NAMA_ILAP,
                    NULL AS ALAMAT_ILAP,
                    NULL AS KOTA_ILAP,
                    NULL AS NAMAPIC_ILAP,
                    NULL AS TELP_KANTOR,
                    NULL AS FAX_ILAP,
                    NULL AS EMAIL_PICILAP,
                    NULL AS CREATE_DATE,
                    NULL AS CREATE_BY,
                    NULL AS JABATAN_PICILAP,
                    NULL AS TELP_PIC,
                    NULL AS TUJUAN_SURAT,
                    NULL AS TEMBUSAN,
                    NULL AS UPDATE_DATE,
                    NULL AS UPDATE_BY,
                    2 AS PRIORITY 
                FROM
                    PROD.REF_ILAP
            ),
            RankedData AS (
                SELECT 
                    c.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY c.ID_ILAP 
                        ORDER BY c.PRIORITY ASC
                    ) AS rn
                FROM CombinedData c
            )
            SELECT 
                ID_ILAP,
                ID_KATEGORI_ILAP,
                NAMA_ILAP,
                ALAMAT_ILAP,
                KOTA_ILAP,
                NAMAPIC_ILAP,
                TELP_KANTOR,
                FAX_ILAP,
                EMAIL_PICILAP,
                CREATE_DATE,
                CREATE_BY,
                JABATAN_PICILAP,
                TELP_PIC,
                TUJUAN_SURAT,
                TEMBUSAN,
                UPDATE_DATE,
                UPDATE_BY
            FROM RankedData
            WHERE rn = 1
        """,
        target_model_label="diamond_web.ILAP",
        target_key_field="id_ilap",
        source_key_column="ID_ILAP",
        field_map={
            "id_kategori": "ID_KATEGORI_ILAP",
            "nama_ilap": "NAMA_ILAP",
            "alamat_ilap": "ALAMAT_ILAP",
            "kota_ilap": "KOTA_ILAP",
            "namapic_ilap": "NAMAPIC_ILAP",
            "telp_kantor": "TELP_KANTOR",
            "fax_ilap": "FAX_ILAP",
            "email_picilap": "EMAIL_PICILAP",
            "create_date": "CREATE_DATE",
            "create_by": "CREATE_BY",
            "jabatan_picilap": "JABATAN_PICILAP",
            "telp_pic": "TELP_PIC",
            "tujuan_surat": "TUJUAN_SURAT",
            "tembusan": "TEMBUSAN",
            "update_date": "UPDATE_DATE",
            "update_by": "UPDATE_BY",
        },
        foreign_key_lookup_map={
            "id_kategori": "id_kategori",
            "id_kategori_wilayah": "deskripsi",
        },
        derived_field_map={
            "id_kategori_wilayah": "kategori_wilayah_from_id_kategori",
        },
        match_fields=("id_ilap", "nama_ilap"),
        where_clause="",
    ),
    # 3. Depends on ilap
    OracleSyncTableConfig(
        name="jenis_data_ilap",
        source_query="""
            WITH CombinedData AS (
            SELECT
                a.id_ilap,
                a.ID_JENIS_DATA,
                b.ID_TABEL_DATA AS ID_SUB_JENIS_DATA,
                a.NAMA_JENIS_DATA,
                a.NAMA_JENIS_DATA AS NAMA_SUB_JENIS_DATA,
                b.NAMA_TABEL_TIP AS NAMA_TABEL_I,
                b.NAMA_TABEL_TIP || '_U' AS NAMA_TABEL_U,
                CASE
                    WHEN b.JENIS_TABEL = 'Referensi' THEN 'Diidentifikasi'
                    WHEN b.JENIS_TABEL = 'Transaksi' THEN 'Tidak Diidentifikasi'
                    WHEN b.JENIS_TABEL = 'Unstructured' THEN 'Tidak Terstruktur'
                    ELSE NULL
                END AS JENIS_TABEL,
                'Data Utama' AS STATUS_DATA,
                1 AS PRIORITY -- Highest priority (First Table Join)
            FROM PROD.APP_JENIS_DATA_ILAP a
            JOIN PROD.APP_TABEL_DATA_ILAP b ON a.ID_JENIS_DATA = b.ID_JENIS_DATA
            UNION ALL 
            SELECT
                ID_ILAP,
                ID_JENIS_DATA,
                ID_TABEL AS ID_SUB_JENIS_DATA,
                JENIS_DATA AS NAMA_JENIS_DATA,
                JENIS_DATA AS NAMA_SUB_JENIS_DATA, -- Fixed: Added column to match the 9 columns above
                'KPDE_' || NAMA_TABEL AS NAMA_TABEL_I,
                'KPDE_' || NAMA_TABEL || '_U' AS NAMA_TABEL_U,
                'Diidentifikasi' AS JENIS_TABEL,
                'Data Utama' AS STATUS_DATA,
                2 AS PRIORITY -- Lower priority (Second Table)
            FROM P3DE.REF_DATA_ILAP
        ),
        RankedData AS (
            SELECT 
                c.*,
                ROW_NUMBER() OVER (
                    PARTITION BY c.ID_SUB_JENIS_DATA 
                    ORDER BY c.PRIORITY ASC
                ) AS rn
            FROM CombinedData c
        )
        SELECT 
            ID_ILAP,
            ID_JENIS_DATA,
            ID_SUB_JENIS_DATA,
            NAMA_JENIS_DATA,
            NAMA_SUB_JENIS_DATA,
            NAMA_TABEL_I,
            NAMA_TABEL_U,
            JENIS_TABEL,
            STATUS_DATA
        FROM RankedData
        WHERE rn = 1
            AND ID_SUB_JENIS_DATA IS NOT NULL
        """,
        target_model_label="diamond_web.JenisDataILAP",
        target_key_field="id_sub_jenis_data",
        source_key_column="ID_SUB_JENIS_DATA",
        field_map={
            "id_ilap": "ID_ILAP",
            "id_jenis_data": "ID_JENIS_DATA",
            "id_sub_jenis_data": "ID_SUB_JENIS_DATA",
            "nama_jenis_data": "NAMA_JENIS_DATA",
            "nama_sub_jenis_data": "NAMA_SUB_JENIS_DATA",
            "nama_tabel_I": "NAMA_TABEL_I",
            "nama_tabel_U": "NAMA_TABEL_U",
            "id_jenis_tabel": "JENIS_TABEL",
            "id_status_data": "STATUS_DATA",
        },
        foreign_key_lookup_map={
            "id_ilap": "id_ilap",
            "id_jenis_tabel": "deskripsi",
            "id_status_data": "deskripsi",
        },
        match_fields=("id_ilap", "id_jenis_data", "id_sub_jenis_data"),
        where_clause="",
    ),
    OracleSyncTableConfig(
        name="jenis_prioritas_data",
        source_query=_build_pmde_prioritas_query(),
        target_model_label="diamond_web.JenisPrioritasData",
        target_key_field="id_sub_jenis_data_ilap",
        source_key_column="ID_TABEL_S",
        field_map={
            "id_sub_jenis_data_ilap": "ID_TABEL_S",
            "start_date": "START_DATE",
            "end_date": "END_DATE",
            "no_nd": "NO_ND",
            "tahun": "TAHUN",
        },
        foreign_key_lookup_map={
            "id_sub_jenis_data_ilap": "id_sub_jenis_data",
        },
        match_fields=("id_sub_jenis_data_ilap", "tahun"),
        where_clause="",
        source_connection="secondary",
    ),
    # 4. Depends on jenis_data_ilap and dasar_hukum
    OracleSyncTableConfig(
        name="klasifikasi_jenis_data",
        source_query="""
           SELECT
                a.ID_TABEL,
                b.KET_DSR_HUKUM
            FROM
                P3DE.REF_DSR_HUKUM a
            JOIN P3DE.REF_DTL_DSR_HUKUM b ON
                a.ID_DSR_HUKUM = b.ID_DSR_HUKUM
        """,
        target_model_label="diamond_web.KlasifikasiJenisData",
        target_key_field="id_sub_jenis_data",
        source_key_column="ID_TABEL",
        field_map={
            "id_sub_jenis_data": "ID_TABEL",
            "id_klasifikasi_tabel": "KET_DSR_HUKUM",
        },
        foreign_key_lookup_map={
            "id_sub_jenis_data": "id_sub_jenis_data",
            "id_klasifikasi_tabel": "deskripsi",
        },
        match_fields=("id_sub_jenis_data", "id_klasifikasi_tabel"),
        where_clause="",
    ),
    # 5. Depends on jenis_data_ilap and periode_pengiriman
    OracleSyncTableConfig(
        name="periode_jenis_data",
        source_query="""
            WITH CombinedData AS (
                SELECT
                    b.ID_TABEL_DATA AS ID_SUB_JENIS_DATA,
                    CASE 
                        WHEN a.PERIODE_PENGIRIMAN = 'Triwulan' THEN 'Triwulanan'
                        ELSE a.PERIODE_PENGIRIMAN
                    END AS PERIODE_PENGIRIMAN,
                    a.TGL_PENYAMPAIAN_PERTAMA,
                    a.JADWAL_PENYAMPAIAN,
                    1 AS PRIORITY
                FROM
                    PROD.APP_JENIS_DATA_ILAP a
                JOIN PROD.APP_TABEL_DATA_ILAP b ON
                    a.ID_JENIS_DATA = b.ID_JENIS_DATA
                UNION ALL
                SELECT
                    ID_TABEL AS ID_SUB_JENIS_DATA,
                    NULL AS PERIODE_PENGIRIMAN,
                    NULL AS TGL_PENYAMPAIAN_PERTAMA,
                    NULL AS JADWAL_PENYAMPAIAN,
                    2 AS PRIORITY
                FROM P3DE.REF_DATA_ILAP
            ),
            RankedData AS (
                SELECT
                    c.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY c.ID_SUB_JENIS_DATA
                        ORDER BY c.PRIORITY ASC
                    ) AS rn
                FROM CombinedData c
            )
            SELECT 
                ID_SUB_JENIS_DATA,
                PERIODE_PENGIRIMAN,
                CASE WHEN TGL_PENYAMPAIAN_PERTAMA IS NULL THEN DATE '2015-01-01' ELSE TGL_PENYAMPAIAN_PERTAMA END TGL_PENYAMPAIAN_PERTAMA,
                NVL(JADWAL_PENYAMPAIAN, 0) AS JADWAL_PENYAMPAIAN
            FROM RankedData
            WHERE rn = 1
                AND ID_SUB_JENIS_DATA IS NOT NULL
                AND PERIODE_PENGIRIMAN IS NOT NULL
        """,
        target_model_label="diamond_web.PeriodeJenisData",
        target_key_field="id_sub_jenis_data_ilap",
        source_key_column="ID_SUB_JENIS_DATA",
        field_map={
            "id_sub_jenis_data_ilap": "ID_SUB_JENIS_DATA",
            "id_periode_pengiriman": "PERIODE_PENGIRIMAN",
            "start_date": "TGL_PENYAMPAIAN_PERTAMA",
            "akhir_penyampaian": "JADWAL_PENYAMPAIAN",
        },
        foreign_key_lookup_map={
            "id_sub_jenis_data_ilap": "id_sub_jenis_data",
            "id_periode_pengiriman": "periode_penyampaian",
        },
        match_fields=("id_sub_jenis_data_ilap", "id_periode_pengiriman"),
        where_clause="",
    ),
    # 6. PIC P3DE - Depends on jenis_data_ilap
    OracleSyncTableConfig(
        name="pic_p3de",
        source_query="""
            SELECT b.id_sub_jenis_data, a.pic_pddo id_user, DATE '2015-01-01' start_date FROM 
            (SELECT
                id_jenis_data,
                pic_pddo
            FROM
                PROD.APP_JENIS_DATA_ILAP
            WHERE
                pic_pddo IS NOT NULL) a
            JOIN 
            (WITH CombinedData AS (
                SELECT
                    a.id_ilap,
                    a.ID_JENIS_DATA,
                    b.ID_TABEL_DATA AS ID_SUB_JENIS_DATA,
                    a.NAMA_JENIS_DATA,
                    a.NAMA_JENIS_DATA AS NAMA_SUB_JENIS_DATA,
                    b.NAMA_TABEL_TIP AS NAMA_TABEL_I,
                    b.NAMA_TABEL_TIP || '_U' AS NAMA_TABEL_U,
                    CASE
                        WHEN b.JENIS_TABEL = 'Referensi' THEN 'Diidentifikasi'
                        WHEN b.JENIS_TABEL = 'Transaksi' THEN 'Tidak Diidentifikasi'
                        WHEN b.JENIS_TABEL = 'Unstructured' THEN 'Tidak Terstruktur'
                        ELSE NULL
                    END AS JENIS_TABEL,
                    'Data Utama' AS STATUS_DATA,
                    1 AS PRIORITY
                FROM PROD.APP_JENIS_DATA_ILAP a
                JOIN PROD.APP_TABEL_DATA_ILAP b ON a.ID_JENIS_DATA = b.ID_JENIS_DATA
                UNION ALL 
                SELECT
                    ID_ILAP,
                    ID_JENIS_DATA,
                    ID_TABEL AS ID_SUB_JENIS_DATA,
                    JENIS_DATA AS NAMA_JENIS_DATA,
                    JENIS_DATA AS NAMA_SUB_JENIS_DATA,
                    'KPDE_' || NAMA_TABEL AS NAMA_TABEL_I,
                    'KPDE_' || NAMA_TABEL || '_U' AS NAMA_TABEL_U,
                    'Diidentifikasi' AS JENIS_TABEL,
                    'Data Utama' AS STATUS_DATA,
                    2 AS PRIORITY
                FROM P3DE.REF_DATA_ILAP
            ),
            RankedData AS (
                SELECT 
                    c.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY c.ID_SUB_JENIS_DATA 
                        ORDER BY c.PRIORITY ASC
                    ) AS rn
                FROM CombinedData c
            )
            SELECT 
                ID_ILAP,
                ID_JENIS_DATA,
                ID_SUB_JENIS_DATA,
                NAMA_JENIS_DATA,
                NAMA_SUB_JENIS_DATA,
                NAMA_TABEL_I,
                NAMA_TABEL_U,
                JENIS_TABEL,
                STATUS_DATA
            FROM RankedData
            WHERE rn = 1
                AND ID_SUB_JENIS_DATA IS NOT NULL
            ) b 
            ON a.id_jenis_data = b.ID_JENIS_DATA
        """,
        target_model_label="diamond_web.PIC",
        target_key_field="id_sub_jenis_data_ilap",
        source_key_column="ID_SUB_JENIS_DATA",
        field_map={
            "id_sub_jenis_data_ilap": "ID_SUB_JENIS_DATA",
            "id_user": "ID_USER",
            "start_date": "START_DATE",
        },
        foreign_key_lookup_map={
            "id_sub_jenis_data_ilap": "id_sub_jenis_data",
            "id_user": "username",
        },
        derived_field_map={
            "tipe": "pic_p3de_tipe",
        },
        match_fields=("id_sub_jenis_data_ilap", "id_user", "start_date"),
        where_clause="",
    ),
    # 7. PIC PIDE - Depends on jenis_data_ilap
    # Oracle query returns (nm_tabel, nip_match, start_date).
    # Rows are expanded by _expand_pic_pide_rows which looks up JenisDataILAP.nama_tabel_I
    # matching nm_tabel to resolve id_sub_jenis_data values, adding ID_SUB_JENIS_DATA to each row.
    OracleSyncTableConfig(
        name="pic_pide",
        source_query="""
            SELECT
                distinct
                a.nm_tabel,
                b.nip_match,
                DATE '2015-01-01' AS start_date
            FROM
                PVPTD.ZA_REKAP_PEMBAGIAN_PIC_PIDE a
            JOIN PVPTD.ZA_REKAP_PIC_PIDE b
                        ON
                a.pic = b.nama_match
            WHERE
                a.id_tabel IS NOT NULL
        """,
        target_model_label="diamond_web.PIC",
        target_key_field="id_sub_jenis_data_ilap",
        source_key_column="ID_SUB_JENIS_DATA",
        field_map={
            "id_sub_jenis_data_ilap": "ID_SUB_JENIS_DATA",
            "id_user": "NIP_MATCH",
            "start_date": "START_DATE",
        },
        foreign_key_lookup_map={
            "id_sub_jenis_data_ilap": "id_sub_jenis_data",
            "id_user": "username",
        },
        derived_field_map={
            "tipe": "pic_pide_tipe",
        },
        match_fields=("id_sub_jenis_data_ilap", "id_user", "start_date"),
        where_clause="",
    ),
    # 8. PIC PMDE - Depends on jenis_data_ilap
    # Oracle query returns (nm_tabel, nip_match, start_date) from REF_TABEL_PMDE.
    # Rows are expanded by _expand_pic_pide_rows which looks up JenisDataILAP.nama_tabel_I
    # matching nm_tabel to resolve id_sub_jenis_data values, adding ID_SUB_JENIS_DATA to each row.
    OracleSyncTableConfig(
        name="pic_pmde",
        source_query="""
            SELECT
                DISTINCT TABEL_I nm_tabel,
                NIP_PIC nip_match,
                DATE '2015-01-01' AS start_date
            FROM
                REF_TABEL_PMDE
        """,
        target_model_label="diamond_web.PIC",
        target_key_field="id_sub_jenis_data_ilap",
        source_key_column="ID_SUB_JENIS_DATA",
        field_map={
            "id_sub_jenis_data_ilap": "ID_SUB_JENIS_DATA",
            "id_user": "NIP_MATCH",
            "start_date": "START_DATE",
        },
        foreign_key_lookup_map={
            "id_sub_jenis_data_ilap": "id_sub_jenis_data",
            "id_user": "username",
        },
        derived_field_map={
            "tipe": "pic_pmde_tipe",
        },
        match_fields=("id_sub_jenis_data_ilap", "id_user", "start_date"),
        where_clause="",
        source_connection="secondary",
    ),
    # 8b. PIC PMDE (ref table) - Depends on jenis_data_ilap (via id_ilap)
    # Oracle query returns (id_ilap, username) from REF_PIC_ILAP_PMDE.
    # Rows are expanded by _expand_pic_pmde_rows which resolves id_ilap → JenisDataILAP
    # to find id_sub_jenis_data values, adding ID_SUB_JENIS_DATA to each row.
    OracleSyncTableConfig(
        name="pic_pmde_ref",
        source_query="""
            SELECT id_ilap, nip_pic username FROM REF_PIC_ILAP_PMDE
        """,
        target_model_label="diamond_web.PIC",
        target_key_field="id_sub_jenis_data_ilap",
        source_key_column="ID_SUB_JENIS_DATA",
        field_map={
            "id_sub_jenis_data_ilap": "ID_SUB_JENIS_DATA",
            "id_user": "USERNAME",
            "start_date": "START_DATE",
        },
        foreign_key_lookup_map={
            "id_sub_jenis_data_ilap": "id_sub_jenis_data",
            "id_user": "username",
        },
        derived_field_map={
            "tipe": "pic_pmde_tipe",
        },
        match_fields=("id_sub_jenis_data_ilap", "id_user", "start_date"),
        where_clause="",
        source_connection="secondary",
    ),
    # 9. DurasiJatuhTempo - depends on jenis_data_ilap
    OracleSyncTableConfig(
        name="durasi_jatuh_tempo_pmde",
        source_query=_build_pmde_prioritas_query(),
        target_model_label="diamond_web.DurasiJatuhTempo",
        target_key_field="id_sub_jenis_data",
        source_key_column="ID_TABEL_S",
        field_map={
            "id_sub_jenis_data": "ID_TABEL_S",
            "durasi": "DURASI",
            "start_date": "START_DATE",
            "end_date": "END_DATE",
        },
        foreign_key_lookup_map={
            "id_sub_jenis_data": "id_sub_jenis_data",
            "seksi": "name",
        },
        derived_field_map={
            "seksi": "pmde_group_name",
        },
        match_fields=("id_sub_jenis_data", "seksi", "start_date"),
        where_clause="",
        source_connection="secondary",
    ),
]


def _initialize_oracledb_thick_mode():
    """Initialize oracledb in thick mode if not already initialized.
    
    Thick mode requires Oracle Client libraries to be installed on the system.
    Set ORACLE_CLIENT_HOME environment variable or use LD_LIBRARY_PATH to specify
    the location of Oracle Client libraries.
    
    For RHEL/CentOS systems:
    - Install oracle-instantclient-basic and oracle-instantclient-devel
    - Set LD_LIBRARY_PATH=/usr/lib/oracle/<version>/client<arch>/lib
    
    For Windows systems:
    - Set ORACLE_CLIENT_HOME to Oracle Client installation directory
    
    Raises:
        Exception: If Oracle Client libraries are not found (Windows) or 
                  LD_LIBRARY_PATH not set properly (Linux/Unix)
    """
    try:
        import oracledb
        
        # Check if already initialized
        if hasattr(oracledb, '_is_thick_mode') and oracledb._is_thick_mode:
            return
        
        # Try to initialize thick mode
        try:
            oracledb.init_oracle_client()
            logger.info("Initialized oracledb in thick mode")
        except Exception as e:
            error_msg = str(e)
            # Catch "Unexpected token" errors which indicate Oracle Client not found
            if "Unexpected token" in error_msg or "html" in error_msg.lower() or "<" in error_msg:
                logger.error(
                    "Failed to initialize oracledb thick mode - Oracle Client libraries not found or misconfigured. "
                    "Error: %s. For RHEL9, ensure Oracle InstantClient is installed and LD_LIBRARY_PATH is set correctly.",
                    error_msg[:200]
                )
            else:
                logger.error(f"Failed to initialize oracledb thick mode: {error_msg[:200]}")
            logger.error(
                "Thick mode requires Oracle Client libraries. "
                "Install Oracle Client or set ORACLE_CLIENT_HOME / LD_LIBRARY_PATH"
            )
            raise
    except ImportError:
        logger.warning("oracledb not available, skipping thick mode initialization")


class OracleDataSyncService:
    """Sync rows from Oracle tables into one or more configured Django models."""

    _IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$.]*$")

    def __init__(self, connection_only: bool = False):
        """Initialize the service.

        Args:
            connection_only: When True, skip PMDE year discovery and sync config
                             validation. Use this when only Oracle connections are
                             needed (e.g. tiket sync/check tasks) to avoid the
                             secondary-connection round-trip for PMDE column discovery.
        """
        # Initialize thick mode before any connections
        try:
            _initialize_oracledb_thick_mode()
        except Exception as e:
            logger.error(f"Failed to initialize oracledb thick mode: {e}")
            # Continue anyway - may work in thin mode
        
        self.oracle_connections = self._load_oracle_connections()
        self._target_model_cache: dict[str, Any] = {}

        if connection_only:
            # Skip PMDE discovery and config validation – not needed for tiket tasks
            self._pmde_discovered_years = list(range(2022, date.today().year + 1))
            return
        
        # Discover PMDE PRIORITAS years before validating sync configs
        try:
            self._pmde_discovered_years = self._discover_and_update_pmde_queries()
        except Exception as e:
            logger.warning(f"Failed to discover PMDE years, using default range: {e}")
            self._pmde_discovered_years = list(range(2022, date.today().year + 1))
        
        self._validate_connection_config()
        self._validate_sync_configs(HARD_CODED_SYNC_TABLES)

    @staticmethod
    def _safe_int(value: str, default: int) -> int:
        try:
            return int(str(value).strip())
        except Exception:
            return default

    def _load_oracle_connections(self) -> dict[str, OracleConnectionConfig]:
        # Backward compatibility:
        # - ORACLE_* is treated as primary
        # - ORACLE_PRIMARY_* can override ORACLE_*
        primary_user = os.getenv("ORACLE_PRIMARY_USER", os.getenv("ORACLE_USER", "")).strip()
        primary_password = os.getenv("ORACLE_PRIMARY_PASSWORD", os.getenv("ORACLE_PASSWORD", "")).strip()
        primary_host = os.getenv("ORACLE_PRIMARY_HOST", os.getenv("ORACLE_HOST", "")).strip()
        primary_port = self._safe_int(os.getenv("ORACLE_PRIMARY_PORT", os.getenv("ORACLE_PORT", "1521")), 1521)
        primary_service = os.getenv("ORACLE_PRIMARY_SERVICE_NAME", os.getenv("ORACLE_SERVICE_NAME", "")).strip()
        primary_sid = os.getenv("ORACLE_PRIMARY_SID", os.getenv("ORACLE_SID", "")).strip()

        secondary_user = os.getenv("ORACLE_SECONDARY_USER", "").strip()
        secondary_password = os.getenv("ORACLE_SECONDARY_PASSWORD", "").strip()
        secondary_host = os.getenv("ORACLE_SECONDARY_HOST", "").strip()
        secondary_port = self._safe_int(os.getenv("ORACLE_SECONDARY_PORT", "1521"), 1521)
        secondary_service = os.getenv("ORACLE_SECONDARY_SERVICE_NAME", "").strip()
        secondary_sid = os.getenv("ORACLE_SECONDARY_SID", "").strip()

        return {
            "primary": OracleConnectionConfig(
                name="primary",
                user=primary_user,
                password=primary_password,
                host=primary_host,
                port=primary_port,
                service_name=primary_service,
                sid=primary_sid,
            ),
            "secondary": OracleConnectionConfig(
                name="secondary",
                user=secondary_user,
                password=secondary_password,
                host=secondary_host,
                port=secondary_port,
                service_name=secondary_service,
                sid=secondary_sid,
            ),
        }

    def _discover_and_update_pmde_queries(self) -> list[int]:
        """Discover PMDE PRIORITAS columns and update sync configs with discovered years.
        
        Returns:
            List of discovered years for PMDE queries.
        """
        # Determine which connection to use for discovery (PMDE syncs use secondary)
        connection_config = self.oracle_connections.get("secondary")
        if not connection_config or not connection_config.user:
            # Secondary not configured, use primary
            connection_config = self.oracle_connections.get("primary")
        
        # Discover available PRIORITAS years
        discovered_years = _discover_pmde_prioritas_years(connection_config)
        logger.info(f"Discovered PMDE PRIORITAS years: {discovered_years}")
        
        # Update HARD_CODED_SYNC_TABLES to use discovered years
        for cfg in HARD_CODED_SYNC_TABLES:
            if cfg.name in ("jenis_prioritas_data", "durasi_jatuh_tempo_pmde"):
                # Rebuild the query with discovered years
                # Since configs are frozen dataclasses, we need to replace them
                new_query = _build_pmde_prioritas_query(discovered_years=discovered_years)
                # Update source_query on the config object (this will fail since frozen)
                # Instead, we'll handle this in the sync method by checking _pmde_discovered_years
                logger.info(f"Updated {cfg.name} to query PMDE years: {discovered_years}")
        
        return discovered_years

    def _validate_identifier(self, value: str, label: str):
        if not self._IDENTIFIER_RE.match(value):
            raise OracleSyncConfigError(f"{label} tidak valid: {value}")

    def _validate_connection_config(self):
        primary = self.oracle_connections["primary"]
        required_values = {
            "ORACLE_USER / ORACLE_PRIMARY_USER": primary.user,
            "ORACLE_PASSWORD / ORACLE_PRIMARY_PASSWORD": primary.password,
            "ORACLE_HOST / ORACLE_PRIMARY_HOST": primary.host,
        }
        missing = [name for name, value in required_values.items() if not value]
        if missing:
            raise OracleSyncConfigError(
                "Konfigurasi Oracle (primary) belum lengkap: " + ", ".join(missing)
            )

        if not primary.service_name and not primary.sid:
            raise OracleSyncConfigError(
                "Set ORACLE_SERVICE_NAME / ORACLE_PRIMARY_SERVICE_NAME atau ORACLE_SID / ORACLE_PRIMARY_SID di .env"
            )

        secondary = self.oracle_connections["secondary"]
        has_any_secondary = any(
            [
                secondary.user,
                secondary.password,
                secondary.host,
                secondary.service_name,
                secondary.sid,
            ]
        )
        if has_any_secondary:
            missing_secondary = [
                name
                for name, value in {
                    "ORACLE_SECONDARY_USER": secondary.user,
                    "ORACLE_SECONDARY_PASSWORD": secondary.password,
                    "ORACLE_SECONDARY_HOST": secondary.host,
                }.items()
                if not value
            ]
            if missing_secondary:
                raise OracleSyncConfigError(
                    "Konfigurasi Oracle (secondary) belum lengkap: " + ", ".join(missing_secondary)
                )
            if not secondary.service_name and not secondary.sid:
                raise OracleSyncConfigError(
                    "Set ORACLE_SECONDARY_SERVICE_NAME atau ORACLE_SECONDARY_SID di .env"
                )

    def _validate_sync_configs(self, sync_configs: list[OracleSyncTableConfig]):
        if not sync_configs:
            raise OracleSyncConfigError(
                "Konfigurasi sync tabel kosong. Isi HARD_CODED_SYNC_TABLES di utils/oracle_sync.py"
            )

        names: set[str] = set()
        for cfg in sync_configs:
            if cfg.name in names:
                raise OracleSyncConfigError(f"Nama config sync duplikat: {cfg.name}")
            names.add(cfg.name)

            if bool(cfg.source_table.strip()) == bool(cfg.source_query.strip()):
                raise OracleSyncConfigError(
                    f"Config {cfg.name} harus isi tepat salah satu: source_table atau source_query"
                )

            conn_name = cfg.source_connection or "primary"
            if conn_name not in self.oracle_connections:
                raise OracleSyncConfigError(
                    f"source_connection tidak dikenali di config {cfg.name}: {conn_name}"
                )

            conn_cfg = self.oracle_connections[conn_name]
            if not conn_cfg.user or not conn_cfg.password or not conn_cfg.host:
                raise OracleSyncConfigError(
                    f"Config {cfg.name} memakai connection '{conn_name}' tapi env belum lengkap"
                )
            if not conn_cfg.service_name and not conn_cfg.sid:
                raise OracleSyncConfigError(
                    f"Config {cfg.name} memakai connection '{conn_name}' tapi SERVICE_NAME/SID belum diisi"
                )

            if cfg.source_table:
                self._validate_identifier(cfg.source_table, f"source_table ({cfg.name})")
            self._validate_identifier(cfg.source_key_column, f"source_key_column ({cfg.name})")

            if not cfg.field_map:
                raise OracleSyncConfigError(f"field_map kosong untuk config {cfg.name}")

            target_model = self._get_target_model(cfg.target_model_label)

            for target_field, source_column in cfg.field_map.items():
                if not target_field or not isinstance(target_field, str):
                    raise OracleSyncConfigError(f"target field invalid pada config {cfg.name}")
                if not source_column or not isinstance(source_column, str):
                    raise OracleSyncConfigError(f"source column invalid pada config {cfg.name}")

                self._validate_identifier(source_column.strip(), f"source column ({cfg.name})")

                try:
                    field_obj = target_model._meta.get_field(target_field)
                    if field_obj.is_relation:
                        lookup_field = cfg.foreign_key_lookup_map.get(target_field)
                        if not lookup_field:
                            raise OracleSyncConfigError(
                                f"Field relasi butuh foreign_key_lookup_map: {cfg.name}.{target_field}"
                            )

                        related_model = field_obj.remote_field.model
                        try:
                            related_model._meta.get_field(lookup_field)
                        except FieldDoesNotExist as exc:
                            raise OracleSyncConfigError(
                                f"Lookup field relasi tidak ada: {related_model._meta.label}.{lookup_field}"
                            ) from exc
                except FieldDoesNotExist as exc:
                    raise OracleSyncConfigError(
                        f"Field target tidak ada: {cfg.target_model_label}.{target_field}"
                    ) from exc

            for target_field in cfg.derived_field_map.keys():
                try:
                    field_obj = target_model._meta.get_field(target_field)
                    if field_obj.is_relation:
                        lookup_field = cfg.foreign_key_lookup_map.get(target_field)
                        if not lookup_field:
                            raise OracleSyncConfigError(
                                f"Field relasi derived butuh foreign_key_lookup_map: {cfg.name}.{target_field}"
                            )

                        related_model = field_obj.remote_field.model
                        try:
                            related_model._meta.get_field(lookup_field)
                        except FieldDoesNotExist as exc:
                            raise OracleSyncConfigError(
                                f"Lookup field relasi tidak ada: {related_model._meta.label}.{lookup_field}"
                            ) from exc
                except FieldDoesNotExist as exc:
                    raise OracleSyncConfigError(
                        f"Field target derived tidak ada: {cfg.target_model_label}.{target_field}"
                    ) from exc

            try:
                target_model._meta.get_field(cfg.target_key_field)
            except FieldDoesNotExist as exc:
                raise OracleSyncConfigError(
                    f"Target key field tidak ada: {cfg.target_model_label}.{cfg.target_key_field}"
                ) from exc

            if cfg.match_fields:
                for match_field in cfg.match_fields:
                    try:
                        target_model._meta.get_field(match_field)
                    except FieldDoesNotExist as exc:
                        raise OracleSyncConfigError(
                            f"Match field tidak ada: {cfg.target_model_label}.{match_field}"
                        ) from exc

    def _get_target_model(self, model_label: str):
        if model_label not in self._target_model_cache:
            self._target_model_cache[model_label] = apps.get_model(model_label)
        return self._target_model_cache[model_label]

    def _connect_oracle(self, connection_name: str = "primary"):
        try:
            import oracledb
        except Exception as exc:
            raise OracleSyncConfigError(
                "Library oracledb belum terpasang. Install dependency terlebih dahulu."
            ) from exc

        if connection_name not in self.oracle_connections:
            raise OracleSyncConfigError(f"Connection Oracle tidak dikenali: {connection_name}")

        conn_cfg = self.oracle_connections[connection_name]

        if not conn_cfg.user or not conn_cfg.password or not conn_cfg.host:
            raise OracleSyncConfigError(
                f"Konfigurasi Oracle ({connection_name}) belum lengkap"
            )

        if not conn_cfg.service_name and not conn_cfg.sid:
            raise OracleSyncConfigError(
                f"Set SERVICE_NAME atau SID untuk connection Oracle ({connection_name})"
            )

        if conn_cfg.service_name:
            dsn = f"{conn_cfg.host}:{conn_cfg.port}/{conn_cfg.service_name}"
        else:
            dsn = f"{conn_cfg.host}:{conn_cfg.port}/{conn_cfg.sid}"

        # TCP connect timeout (seconds) – prevents the caller from hanging
        # indefinitely when the Oracle host is unreachable.  Override via the
        # ORACLE_TCP_CONNECT_TIMEOUT env-var (float, default 15 s).
        try:
            tcp_timeout = float(os.getenv("ORACLE_TCP_CONNECT_TIMEOUT", "15"))
        except (TypeError, ValueError):
            tcp_timeout = 15.0

        try:
            return oracledb.connect(
                user=conn_cfg.user,
                password=conn_cfg.password,
                dsn=dsn,
                tcp_connect_timeout=tcp_timeout,
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Oracle Connection Error ({connection_name}): {error_msg}")
            raise OracleSyncConfigError(error_msg) from e

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, Decimal):
            if value == value.to_integral_value():
                return int(value)
            return float(value)
        if isinstance(value, datetime):
            return value.replace(microsecond=0)
        return value

    def _coerce_model_value(self, target_model, model_field_name: str, value: Any) -> Any:
        field_obj = target_model._meta.get_field(model_field_name)
        if value is None:
            return None

        if field_obj.get_internal_type() == "DateField" and isinstance(value, datetime):
            return value.date()

        if field_obj.get_internal_type() in {"IntegerField", "AutoField", "BigIntegerField"}:
            return int(value)

        if field_obj.get_internal_type() in {"FloatField", "DecimalField"} and isinstance(value, Decimal):
            return float(value)

        if isinstance(value, date) and field_obj.get_internal_type() == "DateTimeField":
            return datetime.combine(value, datetime.min.time())

        return value

    def _build_select_sql(self, cfg: OracleSyncTableConfig) -> str:
        if cfg.source_query.strip():
            # Special handling for PMDE queries - use discovered years
            if cfg.name in ("jenis_prioritas_data", "durasi_jatuh_tempo_pmde"):
                query = _build_pmde_prioritas_query(discovered_years=self._pmde_discovered_years)
                return query.strip().rstrip(";")
            return cfg.source_query.strip().rstrip(";")

        columns = [cfg.source_key_column, *cfg.field_map.values()]
        dedup_columns: list[str] = []
        for column_name in columns:
            if column_name not in dedup_columns:
                dedup_columns.append(column_name)

        sql = f"SELECT {', '.join(dedup_columns)} FROM {cfg.source_table}"
        if cfg.where_clause:
            sql = f"{sql} WHERE {cfg.where_clause}"
        return sql

    def _fetch_oracle_rows(self, cfg: OracleSyncTableConfig) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        sql = self._build_select_sql(cfg)
        conn_name = cfg.source_connection or "primary"
        logger.debug("Oracle sync query [%s/%s]: %s", conn_name, cfg.name, sql)

        with self._connect_oracle(conn_name) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                columns = [col[0].upper() for col in cursor.description]

                for row in cursor.fetchall():
                    mapped = {
                        columns[idx]: self._normalize_value(value)
                        for idx, value in enumerate(row)
                    }
                    rows.append(mapped)

        return rows

    def _map_source_to_target(
        self,
        cfg: OracleSyncTableConfig,
        target_model,
        source_row: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        key = source_row.get(cfg.source_key_column.upper())
        if key is None:
            raise ValueError(
                f"{cfg.name}: Key source column {cfg.source_key_column} bernilai NULL"
            )

        def _assign_target_value(target_field: str, raw_value: Any):
            field_obj = target_model._meta.get_field(target_field)

            if field_obj.is_relation:
                lookup_field = cfg.foreign_key_lookup_map.get(target_field)
                if not lookup_field:
                    raise ValueError(
                        f"{cfg.name}: foreign_key_lookup_map tidak ditemukan untuk field {target_field}"
                    )

                if raw_value is None:
                    mapped_values[field_obj.attname] = None
                else:
                    related_model = field_obj.remote_field.model
                    try:
                        related_obj = related_model.objects.only("pk").get(**{lookup_field: raw_value})
                    except related_model.DoesNotExist as exc:
                        raise ValueError(
                            f"{cfg.name}: referensi {target_field} tidak ditemukan untuk nilai {raw_value}"
                        ) from exc
                    except related_model.MultipleObjectsReturned as exc:
                        # Get details about the duplicates for debugging
                        duplicate_objs = related_model.objects.filter(**{lookup_field: raw_value})
                        duplicate_details = [
                            f"pk={obj.pk}" + (f", {', '.join([f'{k}={getattr(obj, k, None)}' for k in ['id_ilap', 'id_jenis_data', 'id_sub_jenis_data'] if hasattr(obj, k)])}" if hasattr(obj, 'id_jenis_data') else "")
                            for obj in duplicate_objs[:5]
                        ]
                        raise ValueError(
                            f"{cfg.name}: referensi {target_field} ditemukan {duplicate_objs.count()} records untuk {lookup_field}={raw_value}. "
                            f"Details (max 5): [{', '.join(duplicate_details)}]"
                        ) from exc
                    mapped_values[field_obj.attname] = related_obj.pk
                return

            mapped_values[target_field] = self._coerce_model_value(
                target_model,
                target_field,
                raw_value,
            )

        mapped_values: dict[str, Any] = {}
        for target_field, source_column in cfg.field_map.items():
            raw_value = source_row.get(source_column.upper())
            _assign_target_value(target_field, raw_value)

        for target_field, rule_name in cfg.derived_field_map.items():
            raw_value = self._resolve_derived_value(rule_name, source_row)
            _assign_target_value(target_field, raw_value)

        key_value = self._coerce_model_value(target_model, cfg.target_key_field, key)
        # Only set the key directly if it's NOT a relation field.
        # Relation fields are already handled by _assign_target_value above (which sets
        # the attname FK column, e.g. id_sub_jenis_data_id). Setting the plain field name
        # again with a raw string value would create a conflicting key that Django
        # cannot assign as a model instance.
        key_field_obj = target_model._meta.get_field(cfg.target_key_field)
        if not key_field_obj.is_relation:
            mapped_values[cfg.target_key_field] = key_value
        # Always store human-readable key for reporting (never passed to model constructor)
        mapped_values["__sync_key__"] = str(key_value)
        return str(key_value), mapped_values

    @staticmethod
    def _resolve_derived_value(rule_name: str, source_row: dict[str, Any]) -> Any:
        if rule_name == "kategori_wilayah_from_id_kategori":
            kategori = str(source_row.get("ID_KATEGORI_ILAP") or "").strip().upper()
            if kategori in {"PV", "PD"}:
                return "Regional"
            if kategori == "EI":
                return "Internasional"
            return "Nasional"

        if rule_name == "kategori_from_id_dsr_hukum":
            id_dsr_hukum = str(source_row.get("ID_DSR_HUKUM") or "").strip()
            if "-" in id_dsr_hukum:
                return id_dsr_hukum.split("-")[0].upper()
            return id_dsr_hukum.upper()

        if rule_name == "pmde_group_name":
            return "user_pmde"

        if rule_name == "pic_p3de_tipe":
            return "P3DE"

        if rule_name == "pic_pide_tipe":
            return "PIDE"

        if rule_name == "pic_pmde_tipe":
            return "PMDE"

        raise ValueError(f"Rule derived tidak dikenali: {rule_name}")

    def _expand_pic_pide_rows(
        self,
        source_rows: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict]]:
        """Expand pic_pide source rows: one source row (nm_tabel, nip_match, start_date)
        is expanded into one row per id_sub_jenis_data found in JenisDataILAP where
        nama_tabel_I matches nm_tabel.

        Rows where nip_match is NULL or no JenisDataILAP is found are recorded as skipped.
        """
        from datetime import date as _date
        from diamond_web.models import JenisDataILAP

        expanded: list[dict[str, Any]] = []
        skipped: list[dict] = []

        for row_idx, row in enumerate(source_rows, 1):
            nm_tabel = row.get("NM_TABEL")
            nip_match = row.get("NIP_MATCH")

            if not nip_match:
                skipped.append({
                    "row_number": row_idx,
                    "key": str(nm_tabel or "-"),
                    "reason": "NIP_MATCH bernilai NULL (tidak ada user PIC PIDE yang cocok)",
                })
                continue

            if not nm_tabel:
                skipped.append({
                    "row_number": row_idx,
                    "key": str(nip_match or "-"),
                    "reason": "NM_TABEL bernilai NULL",
                })
                continue

            # Lookup JenisDataILAP by nama_tabel_I matching nm_tabel
            jdi_ids = list(
                JenisDataILAP.objects
                .filter(nama_tabel_I=nm_tabel)
                .values_list("id_sub_jenis_data", flat=True)
            )

            if not jdi_ids:
                skipped.append({
                    "row_number": row_idx,
                    "key": str(nm_tabel or "-"),
                    "reason": (
                        f"Tidak ditemukan JenisDataILAP dengan "
                        f"nama_tabel_I={nm_tabel}"
                    ),
                })
                continue

            for id_sub_jenis_data in jdi_ids:
                expanded.append({
                    **row,
                    "ID_SUB_JENIS_DATA": id_sub_jenis_data,
                    "START_DATE": _date(2015, 1, 1),
                })

        return expanded, skipped

    def _expand_pic_pmde_rows(
        self,
        source_rows: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict]]:
        """Expand pic_pmde source rows: one source row (id_ilap, username) is expanded
        into one row per id_sub_jenis_data found in JenisDataILAP for that id_ilap.

        For id_ilap values starting with 'PV' or 'PD' (regional/private ILAPs that do
        not appear in JenisDataILAP directly), a fallback lookup is used:
        query REF_TABEL_PMDE (secondary connection) for (tabel_i, nip_pic), then match
        tabel_i → nama_tabel_I in JenisDataILAP to resolve id_sub_jenis_data values.
        """
        from datetime import date as _date
        from diamond_web.models import JenisDataILAP

        expanded: list[dict[str, Any]] = []
        skipped: list[dict] = []

        # Lazily fetched fallback data from REF_TABEL_PMDE (secondary connection).
        # Maps nip_pic -> list[id_sub_jenis_data] resolved via nama_tabel_I.
        _ref_tabel_pmde_by_nip: dict[str, list[str]] | None = None

        def _get_ref_tabel_pmde_by_nip() -> dict[str, list[str]]:
            """Fetch REF_TABEL_PMDE once and build nip_pic -> [id_sub_jenis_data] map."""
            result: dict[str, list[str]] = {}
            try:
                with self._connect_oracle("secondary") as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "SELECT tabel_i, nip_pic FROM REF_TABEL_PMDE WHERE tabel_i IS NOT NULL AND nip_pic IS NOT NULL"
                        )
                        rows = cursor.fetchall()

                # Build tabel_i -> [id_sub_jenis_data] map from JenisDataILAP
                tabel_i_values = list({str(r[0]).strip() for r in rows if r[0]})
                tabel_map: dict[str, list[str]] = {}
                for jdi in JenisDataILAP.objects.filter(nama_tabel_I__in=tabel_i_values).values("nama_tabel_I", "id_sub_jenis_data"):
                    tabel_map.setdefault(jdi["nama_tabel_I"], []).append(jdi["id_sub_jenis_data"])

                for tabel_i_raw, nip_pic_raw in rows:
                    tabel_i = str(tabel_i_raw).strip() if tabel_i_raw else ""
                    nip_pic = str(nip_pic_raw).strip() if nip_pic_raw else ""
                    if not nip_pic or not tabel_i:
                        continue
                    for sub_id in tabel_map.get(tabel_i, []):
                        result.setdefault(nip_pic, [])
                        if sub_id not in result[nip_pic]:
                            result[nip_pic].append(sub_id)

                logger.info(
                    f"[pic_pmde fallback] Loaded REF_TABEL_PMDE: "
                    f"{len(rows)} rows → {sum(len(v) for v in result.values())} (nip,sub_jenis) pairs"
                )
            except Exception as exc:
                logger.warning(f"[pic_pmde fallback] Failed to fetch REF_TABEL_PMDE: {exc}")
            return result

        # Prefixes that trigger fallback lookup
        FALLBACK_PREFIXES = ("PV", "PD", "PK")

        for row_idx, row in enumerate(source_rows, 1):
            id_ilap = row.get("ID_ILAP")
            username = row.get("USERNAME")
            id_ilap_str = str(id_ilap or "").strip().upper()

            if not username:
                skipped.append({
                    "row_number": row_idx,
                    "key": str(id_ilap or "-"),
                    "reason": "USERNAME (nip_pic) bernilai NULL",
                })
                continue

            # --- Fallback path for PV*/PD* ILAPs ---
            if any(id_ilap_str.startswith(pfx) for pfx in FALLBACK_PREFIXES):
                if _ref_tabel_pmde_by_nip is None:
                    _ref_tabel_pmde_by_nip = _get_ref_tabel_pmde_by_nip()

                username_str = str(username).strip()
                jdi_ids = _ref_tabel_pmde_by_nip.get(username_str, [])

                if not jdi_ids:
                    skipped.append({
                        "row_number": row_idx,
                        "key": f"{id_ilap_str}:{username_str}",
                        "reason": (
                            f"Fallback REF_TABEL_PMDE: tidak ditemukan id_sub_jenis_data "
                            f"untuk nip_pic={username_str}"
                        ),
                    })
                    continue

                for id_sub_jenis_data in jdi_ids:
                    expanded.append({
                        **row,
                        "ID_SUB_JENIS_DATA": id_sub_jenis_data,
                        "START_DATE": _date(2015, 1, 1),
                    })
                continue

            # --- Normal path: lookup by id_ilap ---
            jdi_ids = list(
                JenisDataILAP.objects
                .filter(id_ilap__id_ilap=id_ilap)
                .values_list("id_sub_jenis_data", flat=True)
            )

            if not jdi_ids:
                skipped.append({
                    "row_number": row_idx,
                    "key": str(id_ilap or "-"),
                    "reason": f"Tidak ditemukan JenisDataILAP untuk id_ilap={id_ilap}",
                })
                continue

            for id_sub_jenis_data in jdi_ids:
                expanded.append({
                    **row,
                    "ID_SUB_JENIS_DATA": id_sub_jenis_data,
                    "START_DATE": _date(2015, 1, 1),
                })

        return expanded, skipped

    def _expand_durasi_jatuh_tempo_default_rows(
        self,
        oracle_rows: list[dict[str, Any]],
        discovered_years: list[int],
    ) -> tuple[list[dict[str, Any]], list[dict]]:
        """Supplement durasi_jatuh_tempo_pmde oracle rows with default rows (durasi=90)
        for every (id_sub_jenis_data, year) pair in JenisDataILAP that has no PMDE
        PRIORITAS record in oracle_rows.

        Example: if oracle has records for LM0081401 in 2025 and 2026, and
        discovered_years = [2022, 2023, 2024, 2025, 2026], then default rows are
        generated for LM0081401 × [2022, 2023, 2024] with durasi=90.
        """
        from datetime import date as _date
        from diamond_web.models import JenisDataILAP

        # Build set of (ID_TABEL_S, TAHUN) that already exist in oracle data
        oracle_covered: set[tuple[str, str]] = {
            (str(row.get("ID_TABEL_S") or ""), str(row.get("TAHUN") or ""))
            for row in oracle_rows
        }

        # Get all id_sub_jenis_data values from Django model
        all_sub_jenis = list(
            JenisDataILAP.objects.values_list("id_sub_jenis_data", flat=True).distinct()
        )

        default_rows: list[dict[str, Any]] = []
        for id_sub_jenis_data in all_sub_jenis:
            for year in discovered_years:
                key = (str(id_sub_jenis_data), str(year))
                if key not in oracle_covered:
                    default_rows.append({
                        "ID_TABEL_S": id_sub_jenis_data,
                        "START_DATE": _date(year, 1, 1),
                        "END_DATE": _date(year, 12, 31),
                        "NO_ND": "ND-",
                        "TAHUN": str(year),
                        "DURASI": 90,
                    })

        logger.info(
            f"[durasi_jatuh_tempo_pmde] Oracle rows: {len(oracle_rows)}, "
            f"Default rows generated: {len(default_rows)}"
        )
        # No skipped rows for this expansion (all generated rows have valid IDs from Django)
        return oracle_rows + default_rows, []

    def _calculate_diff_for_config(
        self,
        cfg: OracleSyncTableConfig,
        stop_checker=None,
    ) -> tuple[OracleSyncSummary, Any, list[dict[str, Any]], list[tuple[Any, dict[str, Any]]]]:
        target_model = self._get_target_model(cfg.target_model_label)
        source_rows = self._fetch_oracle_rows(cfg)

        normalized_rows: list[dict[str, Any]] = []
        key_values: list[Any] = []
        errors: list[str] = []
        skipped_rows_detail: list[dict] = []

        # For pic_pmde: expand each source row (nm_tabel, nip_match) into one row per id_sub_jenis_data
        # matched by JenisDataILAP.nama_tabel_I == nm_tabel
        if cfg.name == "pic_pmde":
            source_rows, expansion_skipped = self._expand_pic_pide_rows(source_rows)
            skipped_rows_detail.extend(expansion_skipped)

        # For pic_pide: expand each source row (nm_tabel, nip_match) into one row per id_sub_jenis_data
        # matched by JenisDataILAP.nama_tabel_I == nm_tabel
        if cfg.name == "pic_pide":
            source_rows, expansion_skipped = self._expand_pic_pide_rows(source_rows)
            skipped_rows_detail.extend(expansion_skipped)

        # For pic_pmde_ref: expand each source row (id_ilap, username) into one row per
        # id_sub_jenis_data found in JenisDataILAP for that id_ilap
        if cfg.name == "pic_pmde_ref":
            source_rows, expansion_skipped = self._expand_pic_pmde_rows(source_rows)
            skipped_rows_detail.extend(expansion_skipped)

        # For durasi_jatuh_tempo_pmde: supplement oracle rows with default (durasi=90) rows
        # for every (id_sub_jenis_data, year) in JenisDataILAP not covered by oracle data
        if cfg.name == "durasi_jatuh_tempo_pmde":
            source_rows, expansion_skipped = self._expand_durasi_jatuh_tempo_default_rows(
                source_rows, self._pmde_discovered_years
            )
            skipped_rows_detail.extend(expansion_skipped)

        for row_idx, source_row in enumerate(source_rows, 1):
            # Check stop signal during row iteration
            if stop_checker and stop_checker():
                logger.warning(f'[{cfg.name}] Stop signal received after processing {row_idx-1} rows')
                break
            
            try:
                _, mapped = self._map_source_to_target(cfg, target_model, source_row)
                normalized_rows.append(mapped)
                key_values.append(mapped["__sync_key__"])
            except ValueError as exc:
                # For PMDE syncs and PIC syncs, skip rows with missing FK references instead of failing
                if cfg.name in ("jenis_prioritas_data", "durasi_jatuh_tempo_pmde", "pic_p3de", "pic_pide", "pic_pmde", "pic_pmde_ref") and "referensi" in str(exc):
                    row_key = source_row.get(cfg.source_key_column.upper()) if isinstance(source_row, dict) else None
                    skipped_rows_detail.append({
                        'row_number': row_idx,
                        'key': str(row_key) if row_key is not None else '-',
                        'reason': str(exc),
                    })
                    logger.info(f"Skipping row in {cfg.name} (key={row_key}): {exc}")
                else:
                    errors.append(str(exc))
            except Exception as exc:
                errors.append(str(exc))

        match_fields = cfg.match_fields or (cfg.target_key_field,)

        def _storage_field_name(field_name: str) -> str:
            field_obj = target_model._meta.get_field(field_name)
            return field_obj.attname if field_obj.is_relation else field_name

        inserts: list[dict[str, Any]] = []
        updates: list[tuple[Any, dict[str, Any]]] = []
        unchanged = 0
        inserted_keys: list[str] = []
        updated_keys: list[str] = []

        for mapped in normalized_rows:
            key_value = mapped["__sync_key__"]
            # Strip the sentinel before any DB operations
            model_data = {k: v for k, v in mapped.items() if k != "__sync_key__"}
            lookup_kwargs: dict[str, Any] = {}
            for field_name in match_fields:
                stored_name = _storage_field_name(field_name)
                lookup_kwargs[stored_name] = model_data.get(stored_name)
            obj = target_model.objects.filter(**lookup_kwargs).first()

            if obj is None:
                inserts.append(model_data)
                inserted_keys.append(str(key_value))
                continue

            changed_fields: dict[str, Any] = {}
            for field_name, new_value in model_data.items():
                current_value = getattr(obj, field_name)
                if self._normalize_value(current_value) != self._normalize_value(new_value):
                    changed_fields[field_name] = new_value

            if changed_fields:
                updates.append((obj, changed_fields))
                updated_keys.append(str(key_value))
            else:
                unchanged += 1

        summary = OracleSyncSummary(
            table_name=cfg.name,
            source_table=cfg.source_table or "<query>",
            target_model=cfg.target_model_label,
            source_rows=len(source_rows),
            inserts=len(inserts),
            updates=len(updates),
            unchanged=unchanged,
            errors=errors,
            inserted_keys=inserted_keys[:20],
            updated_keys=updated_keys[:20],
            skipped_rows_detail=skipped_rows_detail,
        )
        
        if skipped_rows_detail:
            logger.info(f"[{cfg.name}] Skipped {len(skipped_rows_detail)} rows due to missing foreign key references")
        
        return summary, target_model, inserts, updates

    def _apply_operations(
        self,
        target_model,
        inserts: list[dict[str, Any]],
        updates: list[tuple[Any, dict[str, Any]]],
    ):
        if inserts:
            try:
                target_model.objects.bulk_create([target_model(**data) for data in inserts])
            except IntegrityError as exc:
                # Handle duplicate unique constraint violations by trying individual inserts
                logger.warning(f"IntegrityError on bulk_create: {exc}. Attempting individual inserts with fallback to skip.")
                for idx, data in enumerate(inserts):
                    try:
                        target_model.objects.create(**data)
                    except IntegrityError as ie:
                        # Skip duplicate records, FK constraint violations, and other constraint issues
                        error_msg = str(ie).lower()
                        # Check if this is a FK constraint error or duplicate
                        if "foreign key" in error_msg or "integrity" in error_msg or "unique" in error_msg:
                            logger.info(f"Skipping insert due to constraint violation: {dict(data)} - {ie}")
                        else:
                            logger.warning(f"Skipping insert: {dict(data)} - {ie}")
                    except Exception as row_exc:
                        logger.error(f"Error on row {idx}: {dict(data)}", exc_info=True)
            except Exception as exc:
                # Try to find which row caused the error
                logger.error(f"Bulk create error: {exc}", exc_info=True)
                for idx, data in enumerate(inserts):
                    try:
                        target_model.objects.create(**data)
                    except IntegrityError as ie:
                        # Skip duplicates and FK constraint violations
                        error_msg = str(ie).lower()
                        if "foreign key" in error_msg or "integrity" in error_msg or "unique" in error_msg:
                            logger.info(f"Skipping insert due to constraint violation: {dict(data)} - {ie}")
                        else:
                            logger.warning(f"Skipping insert: {dict(data)} - {ie}")
                    except Exception as row_exc:
                        logger.error(f"Error on row {idx}: {dict(data)}", exc_info=True)

        for obj, changed_fields in updates:
            for field_name, value in changed_fields.items():
                setattr(obj, field_name, value)
            try:
                obj.save(update_fields=list(changed_fields.keys()))
            except Exception as exc:
                logger.error(f"Error updating object key={getattr(obj, 'pk', 'unknown')}, changes={dict(changed_fields)}", exc_info=True)

    def _build_batch_summary(self, table_summaries: list[OracleSyncSummary]) -> OracleSyncBatchSummary:
        errors: list[str] = []
        inserted_keys: list[str] = []
        updated_keys: list[str] = []
        source_rows = inserts = updates = unchanged = 0

        for summary in table_summaries:
            source_rows += summary.source_rows
            inserts += summary.inserts
            updates += summary.updates
            unchanged += summary.unchanged
            errors.extend([f"[{summary.table_name}] {err}" for err in summary.errors])
            inserted_keys.extend(summary.inserted_keys)
            updated_keys.extend(summary.updated_keys)

        return OracleSyncBatchSummary(
            source_rows=source_rows,
            inserts=inserts,
            updates=updates,
            unchanged=unchanged,
            errors=errors,
            inserted_keys=inserted_keys[:20],
            updated_keys=updated_keys[:20],
            table_summaries=table_summaries,
        )

    def _run_sequential(self, apply_changes: bool, progress_callback=None, stop_checker=None) -> OracleSyncBatchSummary:
        """Run sync/check sequentially over all configured tables.

        Args:
            apply_changes: whether to persist inserts/updates to the DB.
            progress_callback: optional callable(current, total, table_name, cumulative_inserts,
                cumulative_updates, cumulative_errors) called after each table finishes.
            stop_checker: optional callable() that returns True if sync should stop.
        """
        table_summaries: list[OracleSyncSummary] = []
        total_tables = len(HARD_CODED_SYNC_TABLES)
        cumulative_inserts = 0
        cumulative_updates = 0
        cumulative_errors = 0

        for idx, cfg in enumerate(HARD_CODED_SYNC_TABLES, start=1):
            # Check stop signal before processing each table
            if stop_checker and stop_checker():
                logger.info(f'Stop signal received before processing table {idx}/{total_tables}')
                break
                
            try:
                summary, target_model, inserts, updates = self._calculate_diff_for_config(cfg, stop_checker=stop_checker)
                table_summaries.append(summary)

                if apply_changes and not summary.errors:
                    self._apply_operations(target_model, inserts, updates)

                cumulative_inserts += summary.inserts
                cumulative_updates += summary.updates
                cumulative_errors += len(summary.errors)
            except Exception as exc:
                err_summary = OracleSyncSummary(
                    table_name=cfg.name,
                    source_table=cfg.source_table or "<query>",
                    target_model=cfg.target_model_label,
                    source_rows=0,
                    inserts=0,
                    updates=0,
                    unchanged=0,
                    errors=[str(exc)],
                    inserted_keys=[],
                    updated_keys=[],
                    skipped_rows_detail=[],
                )
                table_summaries.append(err_summary)
                cumulative_errors += 1

            if progress_callback is not None:
                try:
                    progress_callback(
                        current=idx,
                        total=total_tables,
                        table_name=cfg.name,
                        inserts=cumulative_inserts,
                        updates=cumulative_updates,
                        errors=cumulative_errors,
                    )
                except Exception:
                    pass  # never let progress reporting crash the sync

        return self._build_batch_summary(table_summaries)

    def check(self, progress_callback=None, stop_checker=None) -> OracleSyncBatchSummary:
        """Check differences without applying changes (runs in atomic transaction and rolls back).
        
        Args:
            progress_callback: optional callable for progress reporting.
            stop_checker: optional callable() that returns True if check should stop.
        """
        # Simulasikan apply dalam 1 transaksi agar dependency antar tabel (parent-child)
        # bisa tervalidasi, lalu rollback supaya data tidak tersimpan.
        with transaction.atomic():
            summary = self._run_sequential(apply_changes=True, progress_callback=progress_callback, stop_checker=stop_checker)
            transaction.set_rollback(True)
            return summary

    def sync(self, progress_callback=None, stop_checker=None) -> OracleSyncBatchSummary:
        """Sync reference data from Oracle to Django models, applying changes to DB.
        
        Args:
            progress_callback: optional callable for progress reporting.
            stop_checker: optional callable() that returns True if sync should stop.
        """
        with transaction.atomic():
            summary = self._run_sequential(apply_changes=True, progress_callback=progress_callback, stop_checker=stop_checker)
            if summary.errors:
                transaction.set_rollback(True)
            return summary