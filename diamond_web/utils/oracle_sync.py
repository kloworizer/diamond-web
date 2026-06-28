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
            where TABEL_I <> 'KPDE_DATA_UNSTRUCTURED'
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
                    except related_model.MultipleObjectsReturned:
                        # When multiple FK records match (e.g. duplicate id_sub_jenis_data in
                        # JenisDataILAP), pick the first match and log a warning instead of
                        # skipping the entire row.
                        related_obj = (
                            related_model.objects
                            .filter(**{lookup_field: raw_value})
                            .only("pk")
                            .first()
                        )
                        if related_obj is None:
                            raise ValueError(
                                f"{cfg.name}: referensi {target_field} tidak ditemukan untuk nilai {raw_value}"
                            )
                        logger.warning(
                            f"{cfg.name}: Multiple records found for {lookup_field}={raw_value} "
                            f"in {related_model._meta.label}. Using first match (pk={related_obj.pk})"
                        )
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
        """Supplement durasi_jatuh_tempo_pmde oracle rows with default rows (durasi=85)
        for every (id_sub_jenis_data, year) pair in JenisDataILAP that has no PMDE
        PRIORITAS record in oracle_rows.

        Example: if oracle has records for LM0081401 in 2025 and 2026, and
        discovered_years = [2022, 2023, 2024, 2025, 2026], then default rows are
        generated for LM0081401 × [2022, 2023, 2024] with durasi=85.
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
                        "DURASI": 85,
                    })

        logger.info(
            f"[durasi_jatuh_tempo_pmde] Oracle rows: {len(oracle_rows)}, "
            f"Default rows generated: {len(default_rows)}"
        )
        # No skipped rows for this expansion (all generated rows have valid IDs from Django)
        return oracle_rows + default_rows, []

    def _pre_process_kategori_ilap_kw(self, apply_changes: bool) -> OracleSyncSummary:
        """Before syncing kategori_ilap, ensure KW record exists in KategoriILAP.

        Inserts id_kategori='KW' / nama_kategori='KW' if it doesn't already exist.

        Args:
            apply_changes: whether to persist the insert to DB.

        Returns:
            OracleSyncSummary describing what was done.
        """
        from diamond_web.models import KategoriILAP

        # Check if KW already exists
        if KategoriILAP.objects.filter(id_kategori='KW').exists():
            logger.info("[pre_kategori_ilap] KW record already exists, skipping")
            return OracleSyncSummary(
                table_name="pre_kategori_ilap_kw",
                source_table="<pre-process>",
                target_model="diamond_web.KategoriILAP",
                source_rows=1,
                inserts=0,
                updates=0,
                unchanged=1,
                errors=[],
            )

        if apply_changes:
            try:
                KategoriILAP.objects.create(id_kategori='KW', nama_kategori='KW')
                logger.info("[pre_kategori_ilap] Inserted KW record into KategoriILAP")
            except Exception as exc:
                logger.error(f"[pre_kategori_ilap] Failed to insert KW record: {exc}")
                return OracleSyncSummary(
                    table_name="pre_kategori_ilap_kw",
                    source_table="<pre-process>",
                    target_model="diamond_web.KategoriILAP",
                    source_rows=1,
                    inserts=0,
                    updates=0,
                    unchanged=0,
                    errors=[str(exc)],
                )

        return OracleSyncSummary(
            table_name="pre_kategori_ilap_kw",
            source_table="<pre-process>",
            target_model="diamond_web.KategoriILAP",
            source_rows=1,
            inserts=1 if apply_changes else 0,
            updates=0,
            unchanged=0,
            errors=[],
            inserted_keys=['KW'] if apply_changes else [],
        )

    def _post_process_ilap_insert_defaults(self, apply_changes: bool) -> OracleSyncSummary:
        """After syncing ilap, insert additional ILAP records that don't exist in Oracle.

        These are hardcoded ILAP entries (mostly KW, PL, PV, PD, EI codes) that need to
        exist in the database but may not be present in the Oracle source tables.

        For each record:
        - id_ilap and nama_ilap are set to the code (e.g. 'KW020')
        - id_kategori is resolved from the 2-letter prefix via KategoriILAP
        - id_kategori_wilayah is determined by prefix:
            'EI' -> 'Internasional'
            'PV' or 'PD' -> 'Regional'
            else -> 'Nasional'
        - All other columns are left as NULL

        Args:
            apply_changes: whether to persist inserts to DB.

        Returns:
            OracleSyncSummary describing what was done.
        """
        from diamond_web.models import KategoriILAP, KategoriWilayah, ILAP

        ILAP_CODES = [
            'EI952',
            'KW020', 'KW070', 'KW080', 'KW140', 'KW150',
            'KW170', 'KW180', 'KW190', 'KW230', 'KW240',
            'KW250', 'KW260', 'KW270', 'KW290', 'KW330',
            'PD908',
            'PL801', 'PL807', 'PL808', 'PL845',
            'PL900', 'PL901', 'PL902',
            'PV908',
        ]

        inserts = 0
        unchanged = 0
        errors: list[str] = []
        inserted_keys: list[str] = []

        for code in ILAP_CODES:
            prefix = code[:2].upper()

            # Check if already exists
            if ILAP.objects.filter(id_ilap=code).exists():
                logger.info(f"[post_ilap_defaults] ILAP {code} already exists, skipping")
                unchanged += 1
                continue

            # Resolve id_kategori from prefix
            try:
                kategori = KategoriILAP.objects.get(id_kategori=prefix)
            except KategoriILAP.DoesNotExist:
                err = f"KategoriILAP with id_kategori='{prefix}' not found for ILAP {code}"
                logger.error(f"[post_ilap_defaults] {err}")
                errors.append(err)
                continue

            # Resolve id_kategori_wilayah from prefix
            if prefix == 'EI':
                wilayah_name = 'Internasional'
            elif prefix in ('PV', 'PD'):
                wilayah_name = 'Regional'
            else:
                wilayah_name = 'Nasional'

            try:
                kategori_wilayah = KategoriWilayah.objects.get(deskripsi=wilayah_name)
            except KategoriWilayah.DoesNotExist:
                err = f"KategoriWilayah with deskripsi='{wilayah_name}' not found for ILAP {code}"
                logger.error(f"[post_ilap_defaults] {err}")
                errors.append(err)
                continue

            if apply_changes:
                try:
                    ILAP.objects.create(
                        id_ilap=code,
                        nama_ilap=code,
                        id_kategori=kategori,
                        id_kategori_wilayah=kategori_wilayah,
                    )
                    logger.info(f"[post_ilap_defaults] Inserted ILAP {code}")
                    inserts += 1
                    inserted_keys.append(code)
                except Exception as exc:
                    err = f"Failed to insert ILAP {code}: {exc}"
                    logger.error(f"[post_ilap_defaults] {err}")
                    errors.append(err)
            else:
                inserts += 1
                inserted_keys.append(code)

        logger.info(
            f"[post_ilap_defaults] Completed: {inserts} inserts, {unchanged} unchanged, "
            f"{len(errors)} errors"
        )

        return OracleSyncSummary(
            table_name="post_ilap_insert_defaults",
            source_table="<post-process>",
            target_model="diamond_web.ILAP",
            source_rows=len(ILAP_CODES),
            inserts=inserts,
            updates=0,
            unchanged=unchanged,
            errors=errors,
            inserted_keys=inserted_keys,
        )

    def _post_process_jenis_data_ilap_aeoi_domestic(self, apply_changes: bool) -> OracleSyncSummary:
        """After syncing jenis_data_ilap, insert AEOI Domestic financial information data.

        Queries JenisDataILAP where id_jenis_data='EI95001' to get reference FK values,
        then inserts a new row for the domestic AEOI account data type (EI9500102).

        Args:
            apply_changes: whether to persist the insert to DB.

        Returns:
            OracleSyncSummary describing what was done.
        """
        from diamond_web.models import JenisDataILAP

        # Query existing data to get reference FK values
        existing = JenisDataILAP.objects.filter(id_jenis_data='EI95001').first()
        if not existing:
            logger.warning(
                "[post_jenis_data_ilap] No existing JenisDataILAP found with "
                "id_jenis_data='EI95001' \u2013 skipping AEOI domestic insert"
            )
            return OracleSyncSummary(
                table_name="post_jenis_data_ilap_aeoi_domestic",
                source_table="<post-process>",
                target_model="diamond_web.JenisDataILAP",
                source_rows=0,
                inserts=0,
                updates=0,
                unchanged=0,
                errors=["Reference row id_jenis_data='EI95001' not found in JenisDataILAP"],
            )

        # Check if target row already exists
        if JenisDataILAP.objects.filter(id_sub_jenis_data='EI9500102').exists():
            logger.info("[post_jenis_data_ilap] Target row EI9500102 already exists, skipping")
            return OracleSyncSummary(
                table_name="post_jenis_data_ilap_aeoi_domestic",
                source_table="<post-process>",
                target_model="diamond_web.JenisDataILAP",
                source_rows=1,
                inserts=0,
                updates=0,
                unchanged=1,
                errors=[],
            )

        new_row_data = {
            "id_jenis_data": 'EI95001',
            "id_sub_jenis_data": 'EI9500102',
            "nama_jenis_data": 'DATA INFORMASI KEUANGAN DOMESTIK',
            "nama_sub_jenis_data": 'DATA INFORMASI KEUANGAN DOMESTIK',
            "nama_tabel_I": 'KPDE_AEOI_DOMESTIC_ACC_DATA',
            "nama_tabel_U": 'KPDE_AEOI_DOMESTIC_ACC_DATA_U',
            "id_ilap": existing.id_ilap,
            "id_jenis_tabel": existing.id_jenis_tabel,
            "id_status_data": existing.id_status_data,
        }

        if apply_changes:
            try:
                JenisDataILAP.objects.create(**new_row_data)
                logger.info("[post_jenis_data_ilap] Inserted new row: EI9500102")
            except Exception as exc:
                logger.error(f"[post_jenis_data_ilap] Failed to insert row: {exc}")
                return OracleSyncSummary(
                    table_name="post_jenis_data_ilap_aeoi_domestic",
                    source_table="<post-process>",
                    target_model="diamond_web.JenisDataILAP",
                    source_rows=1,
                    inserts=0,
                    updates=0,
                    unchanged=0,
                    errors=[str(exc)],
                )

        return OracleSyncSummary(
            table_name="post_jenis_data_ilap_aeoi_domestic",
            source_table="<post-process>",
            target_model="diamond_web.JenisDataILAP",
            source_rows=1,
            inserts=1 if apply_changes else 0,
            updates=0,
            unchanged=0,
            errors=[],
            inserted_keys=['EI9500102'] if apply_changes else [],
        )

    def _post_process_jenis_data_ilap_additional(self, apply_changes: bool) -> OracleSyncSummary:
        """After syncing jenis_data_ilap, insert additional records from hardcoded data.

        These additional JenisDataILAP records (sourced from additional_jenis_data_ilap.csv)
        need to exist in the database but are not covered by the Oracle sync queries.

        For each record, FK references are resolved:
        - id_ilap → ILAP via id_ilap field
        - id_jenis_tabel → JenisTabel via deskripsi field
        - id_status_data → StatusData via deskripsi field (nullable)

        Args:
            apply_changes: whether to persist the insert to DB.

        Returns:
            OracleSyncSummary describing what was done.
        """
        from diamond_web.models import JenisDataILAP, ILAP, JenisTabel, StatusData

        # (id_ilap, id_jenis_data, id_sub_jenis_data, nama_jenis_data,
        #  nama_sub_jenis_data, nama_tabel_I, nama_tabel_U,
        #  id_jenis_tabel, status_data)
        # '-' means empty string; '-_U' means empty string (no base table name)
        ADDITIONAL_RECORDS = [
            ('AS001', 'AS00104', 'AS0010401', '', '', 'KPDE_GAIKINDO_IMPOR', 'KPDE_GAIKINDO_IMPOR_U', 'Diidentifikasi', ''),
            ('EI950', 'EI95001', 'EI9500102', 'DATA INFORMASI KEUANGAN DOMESTIK', 'DATA INFORMASI KEUANGAN DOMESTIK', 'KPDE_AEOI_DOMESTIC_ACC_DATA', 'KPDE_AEOI_DOMESTIC_ACC_DATA_U', 'Diidentifikasi', ''),
            ('EI951', 'EI95101', 'EI9510102', '', '', 'KPDE_AEOI_INBOUND_RESTRUCT', 'KPDE_AEOI_INBOUND_RESTRUCT_U', 'Diidentifikasi', ''),
            ('EI952', 'EI95201', 'EI9520102', '', '', 'KPDE_AEOI_INBOUND_CBCR', 'KPDE_AEOI_INBOUND_CBCR_U', 'Diidentifikasi', ''),
            ('KM002', 'KM00206', 'KM0020601', 'DANA BANTUAN OPERASIONAL SEKOLAH (BOS)', 'DANA BANTUAN OPERASIONAL SEKOLAH (BOS)', 'KPDE_KEMDIKBUD_BANTUAN_BOS', 'KPDE_KEMDIKBUD_BANTUAN_BOS_U', 'Tidak Diidentifikasi', ''),
            ('KM005', 'KM00513', 'KM0051301', 'DAFTAR KLINIK', 'DAFTAR KLINIK', 'KPDE_ADHOC_KEMENKES_KLINIK', 'KPDE_ADHOC_KEMENKES_KLINIK_U', 'Diidentifikasi', ''),
            ('KM005', 'KM00514', 'KM0051401', 'DATA LABORATORIUM/BANK JARINGAN', 'DATA LABORATORIUM/BANK JARINGAN', 'KPDE_ADHOC_KEMENKES_LABJRNGN', 'KPDE_ADHOC_KEMENKES_LABJRNGN_U', 'Diidentifikasi', ''),
            ('KM009', 'KM00902', 'KM0090201', 'DATA PELAPORAN HASIL MONITORING DAN EVALUASI KSWP', 'DATA PELAPORAN HASIL MONITORING DAN EVALUASI KSWP', '', '', 'Diidentifikasi', ''),
            ('KM014', 'KM01407', 'KM0140701', 'DATA PNBP UNTUK DSAB', 'DATA PNBP UNTUK DSAB', 'KPDE_ADHOC_DJA_PNBP_DSAB', 'KPDE_ADHOC_DJA_PNBP_DSAB_U', 'Diidentifikasi', ''),
            ('KM015', 'KM01507', 'KM0150702', 'ADHOC - DATA PEMADANAN NPWP SUPPLIER SPAN', 'ADHOC - DATA PEMADANAN NPWP SUPPLIER SPAN', 'KPDE_ADHOC_UMKM_AKAD', 'KPDE_ADHOC_UMKM_AKAD_U', 'Diidentifikasi', ''),
            ('KM015', 'KM01508', 'KM0150801', 'DATA KUR', 'DATA KUR', 'KPDE_DJPBN_KUR_AKAD', 'KPDE_DJPBN_KUR_AKAD_U', 'Tidak Diidentifikasi', ''),
            ('KM015', 'KM01508', 'KM0150801', 'DATA KUR', 'DATA KUR', 'KPDE_ADHOC_ASN_TNI_POLRI', 'KPDE_ADHOC_ASN_TNI_POLRI_U', 'Tidak Diidentifikasi', ''),
            ('KM015', 'KM01508', 'KM0150802', 'DATA KUR', 'DATA KUR', 'KPDE_DJPBN_KUR_DEBITUR', 'KPDE_DJPBN_KUR_DEBITUR_U', 'Diidentifikasi', ''),
            ('KM015', 'KM01509', 'KM0150901', 'DATA REKENING PENAMPUNGAN AKHIR TAHUN ANGGARAN (RPATA)', 'DATA REKENING PENAMPUNGAN AKHIR TAHUN ANGGARAN (RPATA)', 'KPDE_ADHOC_DJPBN_RPATA', 'KPDE_ADHOC_DJPBN_RPATA_U', 'Diidentifikasi', ''),
            ('KM018', 'KM01819', 'KM0181901', 'DATA ENDORSEMENT', 'DATA ENDORSEMENT', 'KPDE_ADHOC_BC_PPFTZ03ENDORSE', 'KPDE_ADHOC_BC_PPFTZ03ENDORSE_U', 'Diidentifikasi', ''),
            ('KM018', 'KM01852', 'KM0185216', 'DATA ADHOC', 'DATA ADHOC', 'KPDE_ADHOC_BC_CK1_HSLTMBKAU', 'KPDE_ADHOC_BC_CK1_HSLTMBKAU_U', 'Diidentifikasi', ''),
            ('KM019', 'KM01902', 'KM0190201', '', '', 'KPDE_DJP_MFWPOP_PADAN', 'KPDE_DJP_MFWPOP_PADAN_U', 'Diidentifikasi', ''),
            ('KM019', 'KM01902', 'KM0190201', '', '', 'KPDE_DJP_MFWPOP_PADAN_TAHAP2', 'KPDE_DJP_MFWPOP_PADAN_TAHAP2_U', 'Diidentifikasi', ''),
            ('KM019', 'KM01902', 'KM0190201', '', '', 'KPDE_DJP_MFWPOP_PADAN_TAHAP3', 'KPDE_DJP_MFWPOP_PADAN_TAHAP3_U', 'Diidentifikasi', ''),
            ('KM019', 'KM01902', 'KM0190202', '', '', 'KPDE_DJP_MFWPOP_PADAN_TAHAP3', 'KPDE_DJP_MFWPOP_PADAN_TAHAP3_U', 'Diidentifikasi', ''),
            ('KM021', 'KM02106', 'KM0210602', 'DATA LALU LINTAS IKAN DI DALAM DAN LUAR NEGERI', 'DATA LALU LINTAS IKAN DI DALAM DAN LUAR NEGERI', 'KPDE_KKP_DATA_LALIKAN', 'KPDE_KKP_DATA_LALIKAN_U', 'Diidentifikasi', ''),
            ('KM029', 'KM02931', 'KM0293101', 'DATA PEMEGANG IZIN SIUPAL ATAU SIOPSUS DIBEKUKAN', 'DATA PEMEGANG IZIN SIUPAL ATAU SIOPSUS DIBEKUKAN', 'KPDE_ADHOC_HUBLA_PBEKUANIZIN', 'KPDE_ADHOC_HUBLA_PBEKUANIZIN_U', 'Diidentifikasi', ''),
            ('KW020', 'KW02001', 'KW0200101', 'ADHOC - DATA PBB P2', 'ADHOC - DATA PBB P2', 'KPDE_PBB_P2', 'KPDE_PBB_P2_U', 'Diidentifikasi', ''),
            ('KW070', 'KW07001', 'KW0700101', 'ADHOC - DATA PBB P2', 'ADHOC - DATA PBB P2', 'KPDE_PBB_P2', 'KPDE_PBB_P2_U', 'Diidentifikasi', ''),
            ('KW080', 'KW08001', 'KW0800101', 'ADHOC - DATA PBB P2', 'ADHOC - DATA PBB P2', 'KPDE_PBB_P2', 'KPDE_PBB_P2_U', 'Diidentifikasi', ''),
            ('KW140', 'KW14001', 'KW1400101', 'ADHOC - DATA PBB P2', 'ADHOC - DATA PBB P2', 'KPDE_PBB_P2', 'KPDE_PBB_P2_U', 'Diidentifikasi', ''),
            ('KW150', 'KW15001', 'KW1500101', 'ADHOC - DATA PBB P2', 'ADHOC - DATA PBB P2', 'KPDE_PBB_P2', 'KPDE_PBB_P2_U', 'Diidentifikasi', ''),
            ('KW170', 'KW17001', 'KW1700101', 'ADHOC - DATA PBB P2', 'ADHOC - DATA PBB P2', 'KPDE_PBB_P2', 'KPDE_PBB_P2_U', 'Diidentifikasi', ''),
            ('KW180', 'KW18001', 'KW1800101', 'ADHOC - DATA PBB P2', 'ADHOC - DATA PBB P2', 'KPDE_PBB_P2', 'KPDE_PBB_P2_U', 'Diidentifikasi', ''),
            ('KW190', 'KW19001', 'KW1900101', 'ADHOC - DATA PBB P2', 'ADHOC - DATA PBB P2', 'KPDE_PBB_P2', 'KPDE_PBB_P2_U', 'Diidentifikasi', ''),
            ('KW230', 'KW23001', 'KW2300101', 'ADHOC - DATA PBB P2', 'ADHOC - DATA PBB P2', 'KPDE_PBB_P2', 'KPDE_PBB_P2_U', 'Diidentifikasi', ''),
            ('KW240', 'KW24001', 'KW2400101', 'ADHOC - DATA PBB P2', 'ADHOC - DATA PBB P2', 'KPDE_PBB_P2', 'KPDE_PBB_P2_U', 'Diidentifikasi', ''),
            ('KW250', 'KW25001', 'KW2500101', 'ADHOC - DATA PBB P2', 'ADHOC - DATA PBB P2', 'KPDE_PBB_P2', 'KPDE_PBB_P2_U', 'Diidentifikasi', ''),
            ('KW260', 'KW26001', 'KW2600101', 'ADHOC - DATA PBB P2', 'ADHOC - DATA PBB P2', 'KPDE_PBB_P2', 'KPDE_PBB_P2_U', 'Diidentifikasi', ''),
            ('KW270', 'KW27001', 'KW2700101', 'ADHOC - DATA PBB P2', 'ADHOC - DATA PBB P2', 'KPDE_PBB_P2', 'KPDE_PBB_P2_U', 'Diidentifikasi', ''),
            ('KW290', 'KW29001', 'KW2900101', 'ADHOC - DATA PBB P2', 'ADHOC - DATA PBB P2', 'KPDE_PBB_P2', 'KPDE_PBB_P2_U', 'Diidentifikasi', ''),
            ('KW330', 'KW33001', 'KW3300101', 'ADHOC - DATA PBB P2', 'ADHOC - DATA PBB P2', 'KPDE_PBB_P2', 'KPDE_PBB_P2_U', 'Diidentifikasi', ''),
            ('LK101', 'LK10190', 'LK1019000', '', '', 'KPDE_LJK_PASAR_MODAL', 'KPDE_LJK_PASAR_MODAL_U', 'Diidentifikasi', ''),
            ('LK102', 'LK10290', 'LK1029000', '', '', 'KPDE_LJK_FINTECH', 'KPDE_LJK_FINTECH_U', 'Diidentifikasi', ''),
            ('LK103', 'LK10390', 'LK1039000', '', '', 'KPDE_LJK_KUKM', 'KPDE_LJK_KUKM_U', 'Diidentifikasi', ''),
            ('LK103', 'LK10390', 'LK1039000', '', '', 'TBL_ADHOC_ND32_KSP', 'TBL_ADHOC_ND32_KSP_U', 'Diidentifikasi', ''),
            ('LK103', 'LK10390', 'LK1039000', '', '', 'TBL_ADHOC_ND32_LKM', 'TBL_ADHOC_ND32_LKM_U', 'Diidentifikasi', ''),
            ('LK104', 'LK10490', 'LK1049000', '', '', 'TBL_ADHOC_ND32_PLG_BRJGKA', 'TBL_ADHOC_ND32_PLG_BRJGKA_U', 'Diidentifikasi', ''),
            ('LK105', 'LK10590', 'LK1059000', '', '', 'KPDE_LJK_BPR', 'KPDE_LJK_BPR_U', 'Diidentifikasi', ''),
            ('LK106', 'LK10690', 'LK1069000', '', '', 'TBL_ADHOC_ND32_MAN_INVES', 'TBL_ADHOC_ND32_MAN_INVES_U', 'Diidentifikasi', ''),
            ('LK107', 'LK10790', 'LK1079000', '', '', 'KPDE_LJK_BANK_UMUM', 'KPDE_LJK_BANK_UMUM_U', 'Diidentifikasi', ''),
            ('LK108', 'LK10890', 'LK1089000', '', '', 'KPDE_LJK_ASURANSI_JIWA', 'KPDE_LJK_ASURANSI_JIWA_U', 'Diidentifikasi', ''),
            ('LK109', 'LK10990', 'LK1099000', '', '', 'KPDE_LJK_REKSADANA', 'KPDE_LJK_REKSADANA_U', 'Diidentifikasi', ''),
            ('LK109', 'LK10990', 'LK1099000', '', '', 'TBL_ADHOC_ND32_KIK', 'TBL_ADHOC_ND32_KIK_U', 'Diidentifikasi', ''),
            ('LM008', 'LM00802', 'LM0080203', 'DATA KONTRAK MIGAS AKTIF', 'DATA KONTRAK MIGAS AKTIF', 'KPDE_SKKM_01_PRBHN_OPERATOR', 'KPDE_SKKM_01_PRBHN_OPERATOR_U', 'Diidentifikasi', ''),
            ('LM008', 'LM00802', 'LM0080204', 'DATA KONTRAK MIGAS AKTIF', 'DATA KONTRAK MIGAS AKTIF', '', '', 'Diidentifikasi', ''),
            ('LM008', 'LM00805', 'LM0080502', 'DATA FINANCIAL QUARTERLY REPORT (FQR)', 'DATA FINANCIAL QUARTERLY REPORT (FQR)', 'KPDE_SKKM_06_FQR_REPORT_1_1', 'KPDE_SKKM_06_FQR_REPORT_1_1_U', 'Diidentifikasi', ''),
            ('LM008', 'LM00805', 'LM0080504', 'DATA FINANCIAL QUARTERLY REPORT (FQR)', 'DATA FINANCIAL QUARTERLY REPORT (FQR)', 'KPDE_SKKM_06_FQR_REPORT_3', 'KPDE_SKKM_06_FQR_REPORT_3_U', 'Diidentifikasi', ''),
            ('LM008', 'LM00805', 'LM0080506', 'DATA FINANCIAL QUARTERLY REPORT (FQR)', 'DATA FINANCIAL QUARTERLY REPORT (FQR)', '', '', 'Diidentifikasi', ''),
            ('LM008', 'LM00852', 'LM0085201', '(PKS) - DATA UNSTRUCTURED, DATA KONTRAK DARI WILAYAH KERJA (WK)', '(PKS) - DATA UNSTRUCTURED, DATA KONTRAK DARI WILAYAH KERJA (WK)', '', '', 'Tidak Terstruktur', ''),
            ('LM016', 'LM01602', 'LM0160201', 'DATA PROFIL WAJIB LAPOR ATAS LAPORAN HARTA KEKAYAAN PENYELENGGARA NEGARA (LHKPN)', 'DATA PROFIL WAJIB LAPOR ATAS LAPORAN HARTA KEKAYAAN PENYELENGGARA NEGARA (LHKPN)', 'KPDE_ADHOC_KPK_PROFIL_WL_LHK', 'KPDE_ADHOC_KPK_PROFIL_WL_LHK_U', 'Diidentifikasi', ''),
            ('LM020', 'LM02003', 'LM0200301', 'DATA PEGAWAI BIG UNTUK PENGECEKAN KEPATUHAN PELAPORAN SPT TAHUNAN', 'DATA PEGAWAI BIG UNTUK PENGECEKAN KEPATUHAN PELAPORAN SPT TAHUNAN', 'KPDE_BIG_NPWP_PEGAWAI', 'KPDE_BIG_NPWP_PEGAWAI_U', 'Diidentifikasi', ''),
            ('PB001', 'PB00101', 'PB0010101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB002', 'PB00201', 'PB0020101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB003', 'PB00301', 'PB0030101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB004', 'PB00401', 'PB0040101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB005', 'PB00501', 'PB0050101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB006', 'PB00601', 'PB0060101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB007', 'PB00701', 'PB0070101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB008', 'PB00801', 'PB0080101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB009', 'PB00901', 'PB0090101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB010', 'PB01001', 'PB0100101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB011', 'PB01101', 'PB0110101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB012', 'PB01201', 'PB0120101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB013', 'PB01301', 'PB0130101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB015', 'PB01501', 'PB0150101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB017', 'PB01701', 'PB0170101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB019', 'PB01901', 'PB0190101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB020', 'PB02001', 'PB0200101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB022', 'PB02201', 'PB0220101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB023', 'PB02301', 'PB0230101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB024', 'PB02401', 'PB0240101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB025', 'PB02501', 'PB0250101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PB026', 'PB02601', 'PB0260101', 'DATA PEMADANAN BULK', 'DATA PEMADANAN BULK', 'KPDE_ADHOC_PADAN_BULK', 'KPDE_ADHOC_PADAN_BULK_U', 'Diidentifikasi', ''),
            ('PD031', 'PD03179', 'PD0317901', 'DATA USAHA PERIKANAN', 'DATA USAHA PERIKANAN', 'KPDE_PEMDA_PERUSH_LAUT_IKAN', 'KPDE_PEMDA_PERUSH_LAUT_IKAN_U', 'Diidentifikasi', ''),
            ('PD389', 'PD38905', 'PD3890502', 'DATA USAHA HIBURAN', 'DATA USAHA HIBURAN', 'KPDE_PEMDA_HIBURAN', 'KPDE_PEMDA_HIBURAN_U', 'Diidentifikasi', ''),
            ('PD464', 'PD46408', 'PD4640801', '', '', '', '', 'Tidak Diidentifikasi', ''),
            ('PD469', 'PD46908', 'PD4690801', '', '', '', '', 'Tidak Diidentifikasi', ''),
            ('PD483', 'PD48308', 'PD4830801', '', '', '', '', 'Tidak Diidentifikasi', ''),
            ('PD487', 'PD48708', 'PD4870801', '', '', '', '', 'Tidak Diidentifikasi', ''),
            ('PD488', 'PD48808', 'PD4880801', '', '', '', '', 'Tidak Diidentifikasi', ''),
            ('PD493', 'PD49308', 'PD4930801', '', '', '', '', 'Tidak Diidentifikasi', ''),
            ('PD498', 'PD49808', 'PD4980801', '', '', '', '', 'Tidak Diidentifikasi', ''),
            ('PD511', 'PD51149', 'PD5114901', 'DATA INFORMASI KEUANGAN DAERAH', 'DATA INFORMASI KEUANGAN DAERAH', '', '', 'Tidak Terstruktur', ''),
            ('PD908', 'PD90801', 'PD9080101', '', '', 'KPDE_PEMDA_SETORAN_MASA', 'KPDE_PEMDA_SETORAN_MASA_U', 'Tidak Diidentifikasi', ''),
            ('PD908', 'PD90802', 'PD9080201', '', '', 'KPDE_PEMDA_SETORAN_MASA', 'KPDE_PEMDA_SETORAN_MASA_U', 'Tidak Diidentifikasi', ''),
            ('PD908', 'PD90804', 'PD9080401', '', '', 'KPDE_PEMDA_SETORAN_MASA', 'KPDE_PEMDA_SETORAN_MASA_U', 'Tidak Diidentifikasi', ''),
            ('PK013', 'PK01302', 'PK0130201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK023', 'PK02302', 'PK0230201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK037', 'PK03701', 'PK0370101', 'DATA MARKET PLACE - PEGI PEGI', 'DATA MARKET PLACE - PEGI PEGI', 'KPDE_ADHOC_OMP_PEGI', 'KPDE_ADHOC_OMP_PEGI_U', 'Tidak Diidentifikasi', ''),
            ('PK040', 'PK04002', 'PK0400201', 'DATA PEMADANAN NPWP', 'DATA PEMADANAN NPWP', 'KPDE_ADHOC_REQ_CEKCARI_NPWP', 'KPDE_ADHOC_REQ_CEKCARI_NPWP_U', 'Diidentifikasi', ''),
            ('PK042', 'PK04202', 'PK0420201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK055', 'PK05502', 'PK0550201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK087', 'PK08701', 'PK0870101', 'DATA MARKET PLACE - HOTEL', 'DATA MARKET PLACE - HOTEL', 'KPDE_ADHOC_MP_HOTEL', 'KPDE_ADHOC_MP_HOTEL_U', 'Diidentifikasi', ''),
            ('PK092', 'PK09202', 'PK0920201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK111', 'PK11102', 'PK1110201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK119', 'PK11902', 'PK1190201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK125', 'PK12502', 'PK1250201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK127', 'PK12702', 'PK1270201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK212', 'PK21202', 'PK2120201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK214', 'PK21402', 'PK2140201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK328', 'PK32802', 'PK3280201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK406', 'PK40602', 'PK4060201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK441', 'PK44102', 'PK4410201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK443', 'PK44302', 'PK4430201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK505', 'PK50502', 'PK5050201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK509', 'PK50902', 'PK5090201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK518', 'PK51802', 'PK5180201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK521', 'PK52102', 'PK5210201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK541', 'PK54102', 'PK5410201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK606', 'PK60602', 'PK6060201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK614', 'PK61402', 'PK6140201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK625', 'PK62502', 'PK6250201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK631', 'PK63102', 'PK6310201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK645', 'PK64502', 'PK6450201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK648', 'PK64802', 'PK6480201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK652', 'PK65202', 'PK6520201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK653', 'PK65302', 'PK6530201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK702', 'PK70202', 'PK7020201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK712', 'PK71202', 'PK7120201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK713', 'PK71302', 'PK7130201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK904', 'PK90402', 'PK9040201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK905', 'PK90502', 'PK9050201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK907', 'PK90702', 'PK9070201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK908', 'PK90802', 'PK9080201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK908', 'PK90807', 'PK9080701', '', '', 'KPDE_ADHOC_PKP_AIRBNB', 'KPDE_ADHOC_PKP_AIRBNB_U', 'Diidentifikasi', ''),
            ('PK911', 'PK91102', 'PK9110201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PK942', 'PK94202', 'PK9420201', '', '', 'KPDE_ADHOC_DRKB', 'KPDE_ADHOC_DRKB_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04710', 'PL0471011', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04710', 'PL0471017', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04710', 'PL0471039', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04710', 'PL0471041', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04710', 'PL0471044', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04710', 'PL0471087', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471121', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471182', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471183', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471184', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471185', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471186', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471187', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471188', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471189', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471190', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471191', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471192', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471193', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471194', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471195', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471196', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471197', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04711', 'PL0471199', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04712', 'PL0471200', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472002', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472003', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472004', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472005', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472006', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472007', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472008', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472009', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472010', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472011', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472012', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472013', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472014', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472015', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472016', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472018', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472019', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472020', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472021', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472022', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472023', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472024', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472025', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472026', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472028', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472029', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472030', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472031', '', '', '', '', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472032', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472033', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472034', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472035', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472036', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472037', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472038', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472039', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472040', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472041', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472042', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472043', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472044', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472046', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472047', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472048', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472049', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472050', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472051', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472052', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472053', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472054', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472055', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472056', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472057', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472058', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472059', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472060', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472061', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472062', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472063', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472064', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472065', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472066', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472067', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472068', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472069', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472070', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472071', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472072', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472073', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472074', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472075', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472076', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472077', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472078', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472080', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472081', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472082', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472083', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472084', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472085', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472086', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472087', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472088', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472089', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472090', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472091', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472092', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472093', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472094', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472095', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472096', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472097', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472098', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04720', 'PL0472099', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472100', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472101', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472102', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472103', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472104', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472105', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472106', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472107', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472108', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472109', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472110', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472111', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472112', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472113', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472114', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472115', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472116', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472117', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472118', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472119', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472120', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472121', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472122', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472124', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472125', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472126', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472127', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472128', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472129', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472130', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472131', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472132', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472133', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472134', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472135', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472137', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472138', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472139', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472140', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472141', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472142', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472143', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472145', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472146', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472147', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472148', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472149', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472150', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472151', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472152', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472153', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472154', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472155', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472156', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472157', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472159', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472160', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472161', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472162', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472163', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472164', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472165', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472166', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472167', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472168', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472169', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472170', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472171', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472172', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472173', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472174', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472175', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472176', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472177', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472178', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472179', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472180', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL047', 'PL04721', 'PL0472181', '', '', 'KPDE_DAPEN_DPLK_DPPK', 'KPDE_DAPEN_DPLK_DPPK_U', 'Diidentifikasi', ''),
            ('PL050', 'PL05001', 'PL0500101', 'DATA MITRA GOJEK', 'DATA MITRA GOJEK', 'KPDE_ADHOC_GOJEK_MITRA', 'KPDE_ADHOC_GOJEK_MITRA_U', 'Diidentifikasi', ''),
            ('PL801', 'PL80101', 'PL8010101', '', '', 'KPDE_ADHOC_NASABAH_MANDIRI', 'KPDE_ADHOC_NASABAH_MANDIRI_U', 'Diidentifikasi', ''),
            ('PL807', 'PL80700', 'PL8070003', '', '', 'KPDE_KENDARAAN', 'KPDE_KENDARAAN_U', 'Diidentifikasi', ''),
            ('PL808', 'PL80870', 'PL8087001', '', '', 'KPDE_ADHOC_OMP', 'KPDE_ADHOC_OMP_U', 'Diidentifikasi', ''),
            ('PL845', 'PL84560', 'PL8456001', '', '', 'KPDE_ADHOC_OMP', 'KPDE_ADHOC_OMP_U', 'Diidentifikasi', ''),
            ('PL845', 'PL84560', 'PL8456002', '', '', 'KPDE_ADHOC_OMP', 'KPDE_ADHOC_OMP_U', 'Diidentifikasi', ''),
            ('PL845', 'PL84560', 'PL8456003', '', '', 'KPDE_ADHOC_OMP', 'KPDE_ADHOC_OMP_U', 'Diidentifikasi', ''),
            ('PL845', 'PL84560', 'PL8456004', '', '', 'KPDE_ADHOC_OMP', 'KPDE_ADHOC_OMP_U', 'Diidentifikasi', ''),
            ('PL845', 'PL84560', 'PL8456005', '', '', 'KPDE_ADHOC_OMP', 'KPDE_ADHOC_OMP_U', 'Diidentifikasi', ''),
            ('PL845', 'PL84560', 'PL8456006', '', '', 'KPDE_ADHOC_OMP', 'KPDE_ADHOC_OMP_U', 'Diidentifikasi', ''),
            ('PL845', 'PL84560', 'PL8456007', '', '', 'KPDE_ADHOC_OMP', 'KPDE_ADHOC_OMP_U', 'Diidentifikasi', ''),
            ('PL845', 'PL84560', 'PL8456008', '', '', 'KPDE_ADHOC_OMP', 'KPDE_ADHOC_OMP_U', 'Diidentifikasi', ''),
            ('PL845', 'PL84560', 'PL8456009', '', '', 'KPDE_ADHOC_OMP', 'KPDE_ADHOC_OMP_U', 'Diidentifikasi', ''),
            ('PL845', 'PL84560', 'PL8456010', '', '', 'KPDE_ADHOC_OMP', 'KPDE_ADHOC_OMP_U', 'Diidentifikasi', ''),
            ('PL845', 'PL84560', 'PL8456011', '', '', 'KPDE_ADHOC_OMP', 'KPDE_ADHOC_OMP_U', 'Diidentifikasi', ''),
            ('PL845', 'PL84560', 'PL8456012', '', '', 'KPDE_ADHOC_OMP', 'KPDE_ADHOC_OMP_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90000', 'PL9000010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90000', 'PL9000020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90000', 'PL9000030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90010', 'PL9001010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90010', 'PL9001020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90010', 'PL9001030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90020', 'PL9002020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90020', 'PL9002030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90030', 'PL9003020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90030', 'PL9003030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90040', 'PL9004010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90040', 'PL9004020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90040', 'PL9004030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90050', 'PL9005020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90050', 'PL9005030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90060', 'PL9006020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90060', 'PL9006030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90070', 'PL9007010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90070', 'PL9007020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90070', 'PL9007030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90080', 'PL9008020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90080', 'PL9008030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90090', 'PL9009020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL900', 'PL90090', 'PL9009030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90100', 'PL9010020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90100', 'PL9010030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90110', 'PL9011010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90110', 'PL9011020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90110', 'PL9011030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90120', 'PL9012010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90120', 'PL9012020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90120', 'PL9012030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90130', 'PL9013010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90130', 'PL9013020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90130', 'PL9013030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90140', 'PL9014010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90140', 'PL9014020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90140', 'PL9014030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90150', 'PL9015010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90150', 'PL9015020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90150', 'PL9015030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90160', 'PL9016010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90160', 'PL9016020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90160', 'PL9016030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90170', 'PL9017010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90180', 'PL9018010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90180', 'PL9018020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90180', 'PL9018030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90190', 'PL9019020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL901', 'PL90190', 'PL9019030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90200', 'PL9020010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90200', 'PL9020020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90200', 'PL9020030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90210', 'PL9021020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90210', 'PL9021030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90220', 'PL9022020', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90230', 'PL9023010', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90230', 'PL9023030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90240', 'PL9024030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90250', 'PL9025020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90250', 'PL9025030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90260', 'PL9026020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90260', 'PL9026030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90270', 'PL9027020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90270', 'PL9027030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90280', 'PL9028020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90280', 'PL9028030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90290', 'PL9029020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL902', 'PL90290', 'PL9029030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90300', 'PL9030020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90300', 'PL9030030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90310', 'PL9031030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90320', 'PL9032010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90320', 'PL9032020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90320', 'PL9032030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90330', 'PL9033010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90330', 'PL9033020', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90340', 'PL9034020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90340', 'PL9034030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90350', 'PL9035020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90350', 'PL9035030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90360', 'PL9036010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90360', 'PL9036020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90360', 'PL9036030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90370', 'PL9037020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90370', 'PL9037030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90380', 'PL9038010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90380', 'PL9038020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90380', 'PL9038030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90390', 'PL9039020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL903', 'PL90390', 'PL9039030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL904', 'PL90400', 'PL9040020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL904', 'PL90400', 'PL9040030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL904', 'PL90410', 'PL9041020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL904', 'PL90410', 'PL9041030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL904', 'PL90420', 'PL9042010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL904', 'PL90430', 'PL9043020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL904', 'PL90430', 'PL9043030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL904', 'PL90440', 'PL9044010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL904', 'PL90440', 'PL9044020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL904', 'PL90470', 'PL9047010', '', '', 'KPDE_GATEWAY_LAP_A', 'KPDE_GATEWAY_LAP_A_U', 'Diidentifikasi', ''),
            ('PL904', 'PL90470', 'PL9047020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL904', 'PL90470', 'PL9047030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL904', 'PL90480', 'PL9048020', '', '', 'KPDE_GATEWAY_LAP_B', 'KPDE_GATEWAY_LAP_B_U', 'Diidentifikasi', ''),
            ('PL904', 'PL90480', 'PL9048030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL905', 'PL90550', 'PL9055030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL905', 'PL90560', 'PL9056030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL905', 'PL90570', 'PL9057030', '', '', 'KPDE_GATEWAY_LAP_C', 'KPDE_GATEWAY_LAP_C_U', 'Diidentifikasi', ''),
            ('PL906', 'PL90608', 'PL9060801', 'DATA NPWP PEMILIK NOP PERKEBUNAN', 'DATA NPWP PEMILIK NOP PERKEBUNAN', 'KPDE_ADHOC_EKSTEN_PMLKNOPKBN', 'KPDE_ADHOC_EKSTEN_PMLKNOPKBN_U', 'Diidentifikasi', ''),
            ('PL908', 'PL90801', 'PL9080101', 'DATA ONLINE MARKETPLACE', 'DATA ONLINE MARKETPLACE', 'KPDE_ADHOC_OMP', 'KPDE_ADHOC_OMP_U', 'Tidak Diidentifikasi', ''),
            ('PL908', 'PL90801', 'PL9080101', 'DATA ONLINE MARKETPLACE', 'DATA ONLINE MARKETPLACE', 'KPDE_ADHOC_OMP_GOJEK', 'KPDE_ADHOC_OMP_GOJEK_U', 'Tidak Diidentifikasi', ''),
            ('PL908', 'PL90801', 'PL9080101', 'DATA ONLINE MARKETPLACE', 'DATA ONLINE MARKETPLACE', 'KPDE_ADHOC_PKP_MP_MERCHANT', 'KPDE_ADHOC_PKP_MP_MERCHANT_U', 'Tidak Diidentifikasi', ''),
            ('PL908', 'PL90801', 'PL9080102', 'DATA ONLINE MARKETPLACE', 'DATA ONLINE MARKETPLACE', 'KPDE_ADHOC_OMP_TOPED', 'KPDE_ADHOC_OMP_TOPED_U', 'Tidak Diidentifikasi', ''),
            ('PL908', 'PL90801', 'PL9080105', 'DATA ONLINE MARKETPLACE', 'DATA ONLINE MARKETPLACE', 'KPDE_ADHOC_OMP_BKLPK', 'KPDE_ADHOC_OMP_BKLPK_U', 'Tidak Diidentifikasi', ''),
            ('PL908', 'PL90801', 'PL9080105', 'DATA ONLINE MARKETPLACE', 'DATA ONLINE MARKETPLACE', 'KPDE_ADHOC_OMP_BKLPK_CAIR', 'KPDE_ADHOC_OMP_BKLPK_CAIR_U', 'Tidak Diidentifikasi', ''),
            ('PL908', 'PL90801', 'PL9080106', 'DATA ONLINE MARKETPLACE', 'DATA ONLINE MARKETPLACE', 'KPDE_ADHOC_OMP_JDID', 'KPDE_ADHOC_OMP_JDID_U', 'Tidak Diidentifikasi', ''),
            ('PL908', 'PL90801', 'PL9080107', 'DATA ONLINE MARKETPLACE', 'DATA ONLINE MARKETPLACE', 'KPDE_ADHOC_OMP_ELEV_CAIR', 'KPDE_ADHOC_OMP_ELEV_CAIR_U', 'Tidak Diidentifikasi', ''),
            ('PL908', 'PL90801', 'PL9080108', 'DATA ONLINE MARKETPLACE', 'DATA ONLINE MARKETPLACE', 'KPDE_ADHOC_OMP_BLI', 'KPDE_ADHOC_OMP_BLI_U', 'Tidak Diidentifikasi', ''),
            ('PL908', 'PL90801', 'PL9080112', 'DATA ONLINE MARKETPLACE', 'DATA ONLINE MARKETPLACE', 'KPDE_ADHOC_OMP_GOJEK', 'KPDE_ADHOC_OMP_GOJEK_U', 'Tidak Diidentifikasi', ''),
            ('PL908', 'PL90801', 'PL9080114', 'DATA ONLINE MARKETPLACE', 'DATA ONLINE MARKETPLACE', 'KPDE_ADHOC_OMP_TIKET', 'KPDE_ADHOC_OMP_TIKET_U', 'Tidak Diidentifikasi', ''),
            ('PL908', 'PL90840', 'PL9084001', '', '', 'KPDE_FAKTUR_PAJAK', 'KPDE_FAKTUR_PAJAK_U', 'Tidak Diidentifikasi', ''),
            ('PL910', 'PL91002', 'PL9100201', 'ADHOC - DATA LAPORAN KEUANGAN KLIEN', 'ADHOC - DATA LAPORAN KEUANGAN KLIEN', 'KPDE_ADHOC_P2PK_KLIEN_LAPKEU', 'KPDE_ADHOC_P2PK_KLIEN_LAPKEU_U', 'Diidentifikasi', ''),
            ('PL910', 'PL91002', 'PL9100201', 'ADHOC - DATA LAPORAN KEUANGAN KLIEN', 'ADHOC - DATA LAPORAN KEUANGAN KLIEN', 'KPDE_ADHOC_OMP', 'KPDE_ADHOC_OMP_U', 'Diidentifikasi', ''),
            ('PL910', 'PL91002', 'PL9100201', 'ADHOC - DATA LAPORAN KEUANGAN KLIEN', 'ADHOC - DATA LAPORAN KEUANGAN KLIEN', 'KPDE_ADHOC_DSE_TRAIN_2022', 'KPDE_ADHOC_DSE_TRAIN_2022_U', 'Diidentifikasi', ''),
            ('PL910', 'PL91002', 'PL9100205', 'ADHOC - DATA LAPORAN KEUANGAN KLIEN', 'ADHOC - DATA LAPORAN KEUANGAN KLIEN', 'KPDE_ADHOC_FAKTUR000', 'KPDE_ADHOC_FAKTUR000_U', 'Tidak Diidentifikasi', ''),
            ('PL910', 'PL91006', 'PL9100601', 'DATA NPWP BENDAHARA SATKER (APBN, APBD, APBDES)', 'DATA NPWP BENDAHARA SATKER (APBN, APBD, APBDES)', 'KPDE_ADHOC_NPWP_BENDAHARA', 'KPDE_ADHOC_NPWP_BENDAHARA_U', 'Diidentifikasi', ''),
            ('PL910', 'PL91007', 'PL9100701', '', '', 'KPDE_ADHOC_AIRBNB', 'KPDE_ADHOC_AIRBNB_U', 'Tidak Diidentifikasi', ''),
            ('PL914', 'PL91402', 'PL9140201', 'DATA CRYPTO', 'DATA CRYPTO', 'KPDE_ADHOC_PI_CRYPTO_USER_ID', 'KPDE_ADHOC_PI_CRYPTO_USER_ID_U', 'Diidentifikasi', ''),
            ('PL914', 'PL91402', 'PL9140202', 'DATA CRYPTO', 'DATA CRYPTO', 'KPDE_ADHOC_PI_CRYPTO_ADDRESS', 'KPDE_ADHOC_PI_CRYPTO_ADDRESS_U', 'Tidak Diidentifikasi', ''),
            ('PL914', 'PL91402', 'PL9140203', 'DATA CRYPTO', 'DATA CRYPTO', 'KPDE_ADHOC_PI_CRYPTO_TRNSACT', 'KPDE_ADHOC_PI_CRYPTO_TRNSACT_U', 'Tidak Diidentifikasi', ''),
            ('PL914', 'PL91403', 'PL9140301', 'DATA CONTENT CREATOR', 'DATA CONTENT CREATOR', 'KPDE_ADHOC_PI_CNTCREATOR_MST', 'KPDE_ADHOC_PI_CNTCREATOR_MST_U', 'Diidentifikasi', ''),
            ('PL914', 'PL91403', 'PL9140302', 'DATA CONTENT CREATOR', 'DATA CONTENT CREATOR', 'KPDE_ADHOC_PI_CNTCREATOR_TRX', 'KPDE_ADHOC_PI_CNTCREATOR_TRX_U', 'Tidak Diidentifikasi', ''),
            ('PL915', 'PL91503', 'PL9150301', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'KPDE_ADHOC_IP_MP_DETIL_OUT', 'KPDE_ADHOC_IP_MP_DETIL_OUT_U', 'Diidentifikasi', ''),
            ('PL915', 'PL91503', 'PL9150302', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'KPDE_ADHOC_IP_MP_DETIL_OUT', 'KPDE_ADHOC_IP_MP_DETIL_OUT_U', 'Tidak Diidentifikasi', ''),
            ('PL915', 'PL91503', 'PL9150303', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'KPDE_ADHOC_IP_MP_DETIL_OUT', 'KPDE_ADHOC_IP_MP_DETIL_OUT_U', 'Tidak Diidentifikasi', ''),
            ('PL915', 'PL91503', 'PL9150304', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'KPDE_ADHOC_IP_MP_DETIL_OUT', 'KPDE_ADHOC_IP_MP_DETIL_OUT_U', 'Tidak Diidentifikasi', ''),
            ('PL915', 'PL91503', 'PL9150305', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'KPDE_ADHOC_IP_MP_DETIL_OUT', 'KPDE_ADHOC_IP_MP_DETIL_OUT_U', 'Tidak Diidentifikasi', ''),
            ('PL915', 'PL91503', 'PL9150306', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'KPDE_ADHOC_IP_MP_DETIL_OUT', 'KPDE_ADHOC_IP_MP_DETIL_OUT_U', 'Tidak Diidentifikasi', ''),
            ('PL915', 'PL91503', 'PL9150307', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'KPDE_ADHOC_IP_MP_DETIL_OUT', 'KPDE_ADHOC_IP_MP_DETIL_OUT_U', 'Tidak Diidentifikasi', ''),
            ('PL915', 'PL91503', 'PL9150308', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'KPDE_ADHOC_IP_MP_DETIL_OUT', 'KPDE_ADHOC_IP_MP_DETIL_OUT_U', 'Tidak Diidentifikasi', ''),
            ('PL915', 'PL91503', 'PL9150309', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'KPDE_ADHOC_IP_MP_DETIL_OUT', 'KPDE_ADHOC_IP_MP_DETIL_OUT_U', 'Tidak Diidentifikasi', ''),
            ('PL915', 'PL91503', 'PL9150310', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'DATA UANG KELUAR DARI MARKETPLACE (DETAIL)', 'KPDE_ADHOC_IP_MP_DETIL_OUT', 'KPDE_ADHOC_IP_MP_DETIL_OUT_U', 'Tidak Diidentifikasi', ''),
            ('PL915', 'PL91505', 'PL9150501', 'INFORMASI TRANSAKSI KEUANGAN DALAM RANGKA PROGRAM PENGUNGKAPAN SUKARELA', 'INFORMASI TRANSAKSI KEUANGAN DALAM RANGKA PROGRAM PENGUNGKAPAN SUKARELA', 'KPDE_ADHOC_PPS', 'KPDE_ADHOC_PPS_U', 'Diidentifikasi', ''),
            ('PL915', 'PL91506', 'PL9150601', 'DATA PEMADANAN UNTUK PENCARIAN/IDENTIFIKASI NPWP', 'DATA PEMADANAN UNTUK PENCARIAN/IDENTIFIKASI NPWP', 'KPDE_ADHOC_IP_CEKCARI_NPWP', 'KPDE_ADHOC_IP_CEKCARI_NPWP_U', 'Diidentifikasi', ''),
            ('PL915', 'PL91507', 'PL9150701', 'DATA TIKTOK SHOP DAN TIKTOK AFFILIATOR', 'DATA TIKTOK SHOP DAN TIKTOK AFFILIATOR', 'KPDE_ADHOC_IP_TIKTOK_SHOP', 'KPDE_ADHOC_IP_TIKTOK_SHOP_U', 'Diidentifikasi', ''),
            ('PL915', 'PL91507', 'PL9150702', 'DATA TIKTOK SHOP DAN TIKTOK AFFILIATOR', 'DATA TIKTOK SHOP DAN TIKTOK AFFILIATOR', 'KPDE_ADHOC_IP_TIKTOK_AFFIL', 'KPDE_ADHOC_IP_TIKTOK_AFFIL_U', 'Diidentifikasi', ''),
            ('PL915', 'PL91508', 'PL9150801', 'DATA PERGURUAN TINGGI INDONESIA', 'DATA PERGURUAN TINGGI INDONESIA', 'KPDE_ADHOC_IP_PGURUANTINGGI', 'KPDE_ADHOC_IP_PGURUANTINGGI_U', 'Diidentifikasi', ''),
            ('PV001', 'PV00180', 'PV0018001', 'DATA SETORAN MASA', 'DATA SETORAN MASA', 'KPDE_PEMDA_SETORAN_MASA', 'KPDE_PEMDA_SETORAN_MASA_U', 'Diidentifikasi', ''),
            ('PV002', 'PV00251', 'PV0025101', '', '', '', '', 'Diidentifikasi', ''),
            ('PV003', 'PV00391', 'PV0039101', '', '', '', '', 'Diidentifikasi', ''),
            ('PV020', 'PV02047', 'PV0204701', 'DATA USAHA DAN PERIZINAN DI SEKTOR PETERNAKAN', 'DATA USAHA DAN PERIZINAN DI SEKTOR PETERNAKAN', '', '', 'Diidentifikasi', ''),
            ('PV020', 'PV02081', 'PV0208101', 'DATA USAHA DAN PERIZINAN DI SEKTOR PUPR', 'DATA USAHA DAN PERIZINAN DI SEKTOR PUPR', '', '', 'Diidentifikasi', ''),
            ('PV908', 'PV90809', 'PV9080901', '', '', 'KPDE_PEMDA_SETORAN_MASA', 'KPDE_PEMDA_SETORAN_MASA_U', 'Diidentifikasi', ''),
            ('PV908', 'PV90811', 'PV9081101', '', '', 'KPDE_SPPT_2014', 'KPDE_SPPT_2014_U', 'Diidentifikasi', ''),
            ('PV908', 'PV90870', 'PV9087001', '', '', 'KPDE_PEMDA_REKLAME', 'KPDE_PEMDA_REKLAME_U', 'Diidentifikasi', ''),
        ]

        inserts = 0
        unchanged = 0
        errors: list[str] = []
        inserted_keys: list[str] = []

        for (id_ilap_val, id_jenis_data, id_sub_jenis_data, nama_jenis_data,
             nama_sub_jenis_data, nama_tabel_I, nama_tabel_U,
             id_jenis_tabel_val, status_data_val) in ADDITIONAL_RECORDS:

            # Resolve FK references
            try:
                ilap = ILAP.objects.get(id_ilap=id_ilap_val)
            except ILAP.DoesNotExist:
                err = f"ILAP with id_ilap='{id_ilap_val}' not found for sub_jenis {id_sub_jenis_data}"
                logger.error(f"[post_jenis_data_ilap_additional] {err}")
                errors.append(err)
                continue

            try:
                jenis_tabel = JenisTabel.objects.get(deskripsi=id_jenis_tabel_val)
            except JenisTabel.DoesNotExist:
                err = f"JenisTabel with deskripsi='{id_jenis_tabel_val}' not found for sub_jenis {id_sub_jenis_data}"
                logger.error(f"[post_jenis_data_ilap_additional] {err}")
                errors.append(err)
                continue

            status_data = None
            if status_data_val:
                try:
                    status_data = StatusData.objects.get(deskripsi=status_data_val)
                except StatusData.DoesNotExist:
                    err = f"StatusData with deskripsi='{status_data_val}' not found for sub_jenis {id_sub_jenis_data}"
                    logger.error(f"[post_jenis_data_ilap_additional] {err}")
                    errors.append(err)
                    continue

            # Convert '-' sentinel values to empty string for CharField compatibility
            nama_jns = '' if nama_jenis_data == '-' else nama_jenis_data
            nama_sub = '' if nama_sub_jenis_data == '-' else nama_sub_jenis_data
            tbl_I = '' if nama_tabel_I == '-' else nama_tabel_I
            tbl_U = '' if nama_tabel_U == '-' or nama_tabel_U == '-_U' else nama_tabel_U

            # Check if record already exists by id_sub_jenis_data and nama_tabel_I
            existing_filter = {'id_sub_jenis_data': id_sub_jenis_data}
            if tbl_I:
                existing_filter['nama_tabel_I'] = tbl_I
            if JenisDataILAP.objects.filter(**existing_filter).exists():
                logger.info(
                    f"[post_jenis_data_ilap_additional] Record {id_sub_jenis_data} "
                    f"(tabel_I={tbl_I or '<empty>'}) already exists, skipping"
                )
                unchanged += 1
                continue

            if apply_changes:
                try:
                    JenisDataILAP.objects.create(
                        id_ilap=ilap,
                        id_jenis_data=id_jenis_data,
                        id_sub_jenis_data=id_sub_jenis_data,
                        nama_jenis_data=nama_jns,
                        nama_sub_jenis_data=nama_sub,
                        nama_tabel_I=tbl_I,
                        nama_tabel_U=tbl_U,
                        id_jenis_tabel=jenis_tabel,
                        id_status_data=status_data,
                    )
                    logger.info(
                        f"[post_jenis_data_ilap_additional] Inserted {id_sub_jenis_data} "
                        f"(tabel_I={tbl_I or '<empty>'})"
                    )
                    inserts += 1
                    inserted_keys.append(id_sub_jenis_data)
                except Exception as exc:
                    err = f"Failed to insert {id_sub_jenis_data} (tabel_I={tbl_I}): {exc}"
                    logger.error(f"[post_jenis_data_ilap_additional] {err}")
                    errors.append(err)
            else:
                inserts += 1
                inserted_keys.append(id_sub_jenis_data)

        logger.info(
            f"[post_jenis_data_ilap_additional] Completed: {inserts} inserts, "
            f"{unchanged} unchanged, {len(errors)} errors"
        )

        return OracleSyncSummary(
            table_name="post_jenis_data_ilap_additional",
            source_table="<post-process>",
            target_model="diamond_web.JenisDataILAP",
            source_rows=len(ADDITIONAL_RECORDS),
            inserts=inserts,
            updates=0,
            unchanged=unchanged,
            errors=errors,
            inserted_keys=inserted_keys,
        )

    def _post_process_periode_jenis_data_additional(self, apply_changes: bool) -> OracleSyncSummary:
        """After syncing periode_jenis_data, insert additional records from hardcoded data.

        These additional PeriodeJenisData records (sourced from additional_periode_jenis_data.csv)
        need to exist in the database but are not covered by the Oracle sync queries.

        For each record, FK references are resolved:
        - id_sub_jenis_data_ilap → JenisDataILAP via id_sub_jenis_data field
        - id_periode_pengiriman → PeriodePengiriman via periode_penyampaian field

        Default values:
        - start_date = 2015-01-01
        - akhir_penyampaian = 0

        Args:
            apply_changes: whether to persist the insert to DB.

        Returns:
            OracleSyncSummary describing what was done.
        """
        from datetime import date as _date
        from diamond_web.models import JenisDataILAP, PeriodePengiriman, PeriodeJenisData

        # (id_sub_jenis_data, periode_penyampaian)
        ADDITIONAL_RECORDS = [
            ('AS0010401', 'Tahunan'),
            ('EI9510102', 'Tahunan'),
            ('EI9500102', 'Tahunan'),
            ('EI9520102', 'Tahunan'),
            ('KM0020601', 'Bulanan'),
            ('KM0051301', 'Bulanan'),
            ('KM0051401', 'Bulanan'),
            ('KM0051501', 'Bulanan'),
            ('KM0090201', 'Triwulanan'),
            ('KM0140701', 'Tahunan'),
            ('KM0140701', 'Bulanan'),
            ('KM0141501', 'Bulanan'),
            ('KM0141501', 'Tahunan'),
            ('KM0150702', 'Tahunan'),
            ('KM0150801', 'Tahunan'),
            ('KM0150802', 'Tahunan'),
            ('KM0150901', 'Bulanan'),
            ('KM0181901', 'Tahunan'),
            ('KM0185216', 'Bulanan'),
            ('KM0190201', 'Tahunan'),
            ('KM0190202', 'Tahunan'),
            ('KM0210602', 'Tahunan'),
            ('KM0293101', 'Bulanan'),
            ('KW0200101', 'Tahunan'),
            ('KW0700101', 'Tahunan'),
            ('KW0800101', 'Tahunan'),
            ('KW1400101', 'Tahunan'),
            ('KW1500101', 'Tahunan'),
            ('KW1700101', 'Tahunan'),
            ('KW1800101', 'Tahunan'),
            ('KW1900101', 'Tahunan'),
            ('KW2300101', 'Tahunan'),
            ('KW2400101', 'Tahunan'),
            ('KW2500101', 'Tahunan'),
            ('KW2600101', 'Tahunan'),
            ('KW2700101', 'Tahunan'),
            ('KW2900101', 'Tahunan'),
            ('KW3300101', 'Tahunan'),
            ('LK1019000', 'Tahunan'),
            ('LK1029000', 'Tahunan'),
            ('LK1039000', 'Bulanan'),
            ('LK1049000', 'Bulanan'),
            ('LK1059000', 'Bulanan'),
            ('LK1069000', 'Bulanan'),
            ('LK1079000', 'Tahunan'),
            ('LK1089000', 'Tahunan'),
            ('LK1099000', 'Bulanan'),
            ('LM0080203', 'Tahunan'),
            ('LM0080204', 'Tahunan'),
            ('LM0080502', 'Tahunan'),
            ('LM0080504', 'Tahunan'),
            ('LM0080506', 'Tahunan'),
            ('LM0085201', 'Bulanan'),
            ('LM0160201', 'Tahunan'),
            ('LM0200301', 'Bulanan'),
            ('PB0010101', 'Tahunan'),
            ('PB0020101', 'Tahunan'),
            ('PB0030101', 'Tahunan'),
            ('PB0040101', 'Tahunan'),
            ('PB0050101', 'Tahunan'),
            ('PB0060101', 'Tahunan'),
            ('PB0070101', 'Tahunan'),
            ('PB0080101', 'Tahunan'),
            ('PB0090101', 'Tahunan'),
            ('PB0100101', 'Tahunan'),
            ('PB0110101', 'Tahunan'),
            ('PB0120101', 'Tahunan'),
            ('PB0130101', 'Tahunan'),
            ('PB0150101', 'Tahunan'),
            ('PB0170101', 'Tahunan'),
            ('PB0190101', 'Tahunan'),
            ('PB0200101', 'Tahunan'),
            ('PB0220101', 'Tahunan'),
            ('PB0230101', 'Tahunan'),
            ('PB0240101', 'Tahunan'),
            ('PB0250101', 'Tahunan'),
            ('PB0260101', 'Tahunan'),
            ('PD0317901', 'Bulanan'),
            ('PD3890502', 'Tahunan'),
            ('PD4640801', 'Tahunan'),
            ('PD4690801', 'Tahunan'),
            ('PD4830801', 'Tahunan'),
            ('PD4870801', 'Tahunan'),
            ('PD4880801', 'Tahunan'),
            ('PD4930801', 'Tahunan'),
            ('PD4980801', 'Tahunan'),
            ('PD5114901', 'Bulanan'),
            ('PD9080101', 'Tahunan'),
            ('PD9080201', 'Tahunan'),
            ('PD9080401', 'Tahunan'),
            ('PK0130201', 'Tahunan'),
            ('PK0230201', 'Tahunan'),
            ('PK0370101', 'Tahunan'),
            ('PK0400201', 'Tahunan'),
            ('PK0420201', 'Tahunan'),
            ('PK0550201', 'Tahunan'),
            ('PK0870101', 'Tahunan'),
            ('PK0920201', 'Tahunan'),
            ('PK1110201', 'Tahunan'),
            ('PK1190201', 'Tahunan'),
            ('PK1250201', 'Tahunan'),
            ('PK1270201', 'Tahunan'),
            ('PK2120201', 'Tahunan'),
            ('PK2140201', 'Tahunan'),
            ('PK3280201', 'Tahunan'),
            ('PK4060201', 'Tahunan'),
            ('PK4410201', 'Tahunan'),
            ('PK4430201', 'Tahunan'),
            ('PK5050201', 'Tahunan'),
            ('PK5090201', 'Tahunan'),
            ('PK5180201', 'Tahunan'),
            ('PK5210201', 'Tahunan'),
            ('PK5410201', 'Tahunan'),
            ('PK6060201', 'Tahunan'),
            ('PK6140201', 'Tahunan'),
            ('PK6250201', 'Tahunan'),
            ('PK6310201', 'Tahunan'),
            ('PK6450201', 'Tahunan'),
            ('PK6480201', 'Tahunan'),
            ('PK6520201', 'Tahunan'),
            ('PK6530201', 'Tahunan'),
            ('PK7020201', 'Tahunan'),
            ('PK7120201', 'Tahunan'),
            ('PK7130201', 'Tahunan'),
            ('PK9040201', 'Tahunan'),
            ('PK9050201', 'Tahunan'),
            ('PK9070201', 'Tahunan'),
            ('PK9080201', 'Tahunan'),
            ('PK9080701', 'Tahunan'),
            ('PK9110201', 'Tahunan'),
            ('PK9420201', 'Tahunan'),
            ('PL0471011', 'Bulanan'),
            ('PL0471017', 'Bulanan'),
            ('PL0471039', 'Bulanan'),
            ('PL0471041', 'Bulanan'),
            ('PL0471044', 'Bulanan'),
            ('PL0471087', 'Bulanan'),
            ('PL0471121', 'Bulanan'),
            ('PL0471182', 'Bulanan'),
            ('PL0471183', 'Bulanan'),
            ('PL0471184', 'Bulanan'),
            ('PL0471185', 'Bulanan'),
            ('PL0471186', 'Bulanan'),
            ('PL0471187', 'Bulanan'),
            ('PL0471188', 'Bulanan'),
            ('PL0471189', 'Bulanan'),
            ('PL0471190', 'Bulanan'),
            ('PL0471191', 'Bulanan'),
            ('PL0471192', 'Bulanan'),
            ('PL0471193', 'Bulanan'),
            ('PL0471194', 'Bulanan'),
            ('PL0471195', 'Bulanan'),
            ('PL0471196', 'Bulanan'),
            ('PL0471197', 'Bulanan'),
            ('PL0471199', 'Bulanan'),
            ('PL0471200', 'Bulanan'),
            ('PL0472002', 'Bulanan'),
            ('PL0472003', 'Bulanan'),
            ('PL0472004', 'Bulanan'),
            ('PL0472005', 'Bulanan'),
            ('PL0472006', 'Bulanan'),
            ('PL0472007', 'Bulanan'),
            ('PL0472008', 'Bulanan'),
            ('PL0472009', 'Bulanan'),
            ('PL0472010', 'Bulanan'),
            ('PL0472011', 'Tahunan'),
            ('PL0472012', 'Bulanan'),
            ('PL0472013', 'Bulanan'),
            ('PL0472014', 'Bulanan'),
            ('PL0472015', 'Tahunan'),
            ('PL0472016', 'Bulanan'),
            ('PL0472018', 'Bulanan'),
            ('PL0472019', 'Bulanan'),
            ('PL0472020', 'Tahunan'),
            ('PL0472021', 'Bulanan'),
            ('PL0472022', 'Bulanan'),
            ('PL0472023', 'Bulanan'),
            ('PL0472024', 'Bulanan'),
            ('PL0472025', 'Bulanan'),
            ('PL0472026', 'Bulanan'),
            ('PL0472028', 'Bulanan'),
            ('PL0472029', 'Bulanan'),
            ('PL0472030', 'Bulanan'),
            ('PL0472031', 'Bulanan'),
            ('PL0472032', 'Bulanan'),
            ('PL0472033', 'Tahunan'),
            ('PL0472034', 'Bulanan'),
            ('PL0472035', 'Bulanan'),
            ('PL0472036', 'Bulanan'),
            ('PL0472037', 'Bulanan'),
            ('PL0472038', 'Bulanan'),
            ('PL0472039', 'Bulanan'),
            ('PL0472040', 'Tahunan'),
            ('PL0472041', 'Bulanan'),
            ('PL0472042', 'Bulanan'),
            ('PL0472043', 'Bulanan'),
            ('PL0472044', 'Bulanan'),
            ('PL0472046', 'Bulanan'),
            ('PL0472047', 'Bulanan'),
            ('PL0472048', 'Tahunan'),
            ('PL0472049', 'Bulanan'),
            ('PL0472050', 'Bulanan'),
            ('PL0472051', 'Bulanan'),
            ('PL0472052', 'Bulanan'),
            ('PL0472053', 'Bulanan'),
            ('PL0472054', 'Bulanan'),
            ('PL0472055', 'Bulanan'),
            ('PL0472056', 'Bulanan'),
            ('PL0472057', 'Bulanan'),
            ('PL0472058', 'Bulanan'),
            ('PL0472059', 'Bulanan'),
            ('PL0472060', 'Bulanan'),
            ('PL0472061', 'Bulanan'),
            ('PL0472062', 'Bulanan'),
            ('PL0472063', 'Bulanan'),
            ('PL0472064', 'Bulanan'),
            ('PL0472065', 'Bulanan'),
            ('PL0472066', 'Bulanan'),
            ('PL0472067', 'Bulanan'),
            ('PL0472068', 'Bulanan'),
            ('PL0472069', 'Tahunan'),
            ('PL0472070', 'Bulanan'),
            ('PL0472071', 'Tahunan'),
            ('PL0472072', 'Bulanan'),
            ('PL0472073', 'Bulanan'),
            ('PL0472074', 'Bulanan'),
            ('PL0472075', 'Bulanan'),
            ('PL0472076', 'Bulanan'),
            ('PL0472077', 'Bulanan'),
            ('PL0472078', 'Bulanan'),
            ('PL0472080', 'Bulanan'),
            ('PL0472081', 'Bulanan'),
            ('PL0472082', 'Bulanan'),
            ('PL0472083', 'Bulanan'),
            ('PL0472084', 'Bulanan'),
            ('PL0472085', 'Bulanan'),
            ('PL0472086', 'Bulanan'),
            ('PL0472087', 'Tahunan'),
            ('PL0472088', 'Bulanan'),
            ('PL0472089', 'Bulanan'),
            ('PL0472090', 'Bulanan'),
            ('PL0472091', 'Bulanan'),
            ('PL0472092', 'Bulanan'),
            ('PL0472093', 'Bulanan'),
            ('PL0472094', 'Bulanan'),
            ('PL0472095', 'Bulanan'),
            ('PL0472096', 'Bulanan'),
            ('PL0472097', 'Bulanan'),
            ('PL0472098', 'Bulanan'),
            ('PL0472099', 'Bulanan'),
            ('PL0472100', 'Bulanan'),
            ('PL0472101', 'Bulanan'),
            ('PL0472102', 'Bulanan'),
            ('PL0472103', 'Bulanan'),
            ('PL0472104', 'Bulanan'),
            ('PL0472105', 'Bulanan'),
            ('PL0472106', 'Bulanan'),
            ('PL0472107', 'Tahunan'),
            ('PL0472108', 'Tahunan'),
            ('PL0472109', 'Bulanan'),
            ('PL0472110', 'Bulanan'),
            ('PL0472111', 'Bulanan'),
            ('PL0472112', 'Bulanan'),
            ('PL0472113', 'Bulanan'),
            ('PL0472114', 'Bulanan'),
            ('PL0472115', 'Bulanan'),
            ('PL0472116', 'Bulanan'),
            ('PL0472117', 'Bulanan'),
            ('PL0472118', 'Bulanan'),
            ('PL0472119', 'Tahunan'),
            ('PL0472120', 'Bulanan'),
            ('PL0472121', 'Bulanan'),
            ('PL0472122', 'Bulanan'),
            ('PL0472124', 'Bulanan'),
            ('PL0472125', 'Bulanan'),
            ('PL0472126', 'Bulanan'),
            ('PL0472127', 'Bulanan'),
            ('PL0472128', 'Bulanan'),
            ('PL0472129', 'Bulanan'),
            ('PL0472130', 'Bulanan'),
            ('PL0472131', 'Bulanan'),
            ('PL0472132', 'Bulanan'),
            ('PL0472133', 'Bulanan'),
            ('PL0472134', 'Bulanan'),
            ('PL0472135', 'Bulanan'),
            ('PL0472137', 'Bulanan'),
            ('PL0472138', 'Bulanan'),
            ('PL0472139', 'Bulanan'),
            ('PL0472140', 'Bulanan'),
            ('PL0472141', 'Bulanan'),
            ('PL0472142', 'Bulanan'),
            ('PL0472143', 'Bulanan'),
            ('PL0472145', 'Bulanan'),
            ('PL0472146', 'Bulanan'),
            ('PL0472147', 'Bulanan'),
            ('PL0472148', 'Bulanan'),
            ('PL0472149', 'Bulanan'),
            ('PL0472150', 'Bulanan'),
            ('PL0472151', 'Bulanan'),
            ('PL0472152', 'Tahunan'),
            ('PL0472153', 'Bulanan'),
            ('PL0472154', 'Bulanan'),
            ('PL0472155', 'Tahunan'),
            ('PL0472156', 'Bulanan'),
            ('PL0472157', 'Bulanan'),
            ('PL0472159', 'Bulanan'),
            ('PL0472160', 'Bulanan'),
            ('PL0472161', 'Bulanan'),
            ('PL0472162', 'Bulanan'),
            ('PL0472163', 'Bulanan'),
            ('PL0472164', 'Bulanan'),
            ('PL0472165', 'Bulanan'),
            ('PL0472166', 'Tahunan'),
            ('PL0472167', 'Bulanan'),
            ('PL0472168', 'Bulanan'),
            ('PL0472169', 'Bulanan'),
            ('PL0472170', 'Bulanan'),
            ('PL0472171', 'Bulanan'),
            ('PL0472172', 'Tahunan'),
            ('PL0472173', 'Bulanan'),
            ('PL0472174', 'Bulanan'),
            ('PL0472175', 'Bulanan'),
            ('PL0472176', 'Bulanan'),
            ('PL0472177', 'Bulanan'),
            ('PL0472178', 'Bulanan'),
            ('PL0472179', 'Bulanan'),
            ('PL0472180', 'Bulanan'),
            ('PL0472181', 'Bulanan'),
            ('PL0500101', 'Tahunan'),
            ('PL8010101', 'Tahunan'),
            ('PL8070003', 'Tahunan'),
            ('PL8087001', 'Bulanan'),
            ('PL8456001', 'Tahunan'),
            ('PL8456002', 'Tahunan'),
            ('PL8456003', 'Tahunan'),
            ('PL8456004', 'Tahunan'),
            ('PL8456005', 'Tahunan'),
            ('PL8456006', 'Tahunan'),
            ('PL8456007', 'Tahunan'),
            ('PL8456008', 'Tahunan'),
            ('PL8456009', 'Tahunan'),
            ('PL8456010', 'Tahunan'),
            ('PL8456011', 'Tahunan'),
            ('PL8456012', 'Tahunan'),
            ('PL9000010', 'Tahunan'),
            ('PL9000020', 'Tahunan'),
            ('PL9000030', 'Tahunan'),
            ('PL9001010', 'Tahunan'),
            ('PL9001020', 'Tahunan'),
            ('PL9001030', 'Tahunan'),
            ('PL9002020', 'Tahunan'),
            ('PL9002030', 'Tahunan'),
            ('PL9003020', 'Tahunan'),
            ('PL9003030', 'Tahunan'),
            ('PL9004010', 'Tahunan'),
            ('PL9004020', 'Tahunan'),
            ('PL9004030', 'Tahunan'),
            ('PL9005020', 'Tahunan'),
            ('PL9005030', 'Tahunan'),
            ('PL9006020', 'Tahunan'),
            ('PL9006030', 'Tahunan'),
            ('PL9007010', 'Tahunan'),
            ('PL9007020', 'Tahunan'),
            ('PL9007030', 'Tahunan'),
            ('PL9008020', 'Tahunan'),
            ('PL9008030', 'Tahunan'),
            ('PL9009020', 'Tahunan'),
            ('PL9009030', 'Tahunan'),
            ('PL9010020', 'Tahunan'),
            ('PL9010030', 'Tahunan'),
            ('PL9011010', 'Tahunan'),
            ('PL9011020', 'Tahunan'),
            ('PL9011030', 'Tahunan'),
            ('PL9012010', 'Tahunan'),
            ('PL9012020', 'Tahunan'),
            ('PL9012030', 'Tahunan'),
            ('PL9013010', 'Tahunan'),
            ('PL9013020', 'Tahunan'),
            ('PL9013030', 'Tahunan'),
            ('PL9014010', 'Tahunan'),
            ('PL9014020', 'Tahunan'),
            ('PL9014030', 'Tahunan'),
            ('PL9015010', 'Tahunan'),
            ('PL9015020', 'Tahunan'),
            ('PL9015030', 'Tahunan'),
            ('PL9016010', 'Tahunan'),
            ('PL9016020', 'Tahunan'),
            ('PL9016030', 'Tahunan'),
            ('PL9017010', 'Tahunan'),
            ('PL9018010', 'Tahunan'),
            ('PL9018020', 'Tahunan'),
            ('PL9018030', 'Tahunan'),
            ('PL9019020', 'Tahunan'),
            ('PL9019030', 'Tahunan'),
            ('PL9020010', 'Tahunan'),
            ('PL9020020', 'Tahunan'),
            ('PL9020030', 'Tahunan'),
            ('PL9021020', 'Tahunan'),
            ('PL9021030', 'Tahunan'),
            ('PL9022020', 'Tahunan'),
            ('PL9023010', 'Tahunan'),
            ('PL9023030', 'Tahunan'),
            ('PL9024030', 'Tahunan'),
            ('PL9025020', 'Tahunan'),
            ('PL9025030', 'Tahunan'),
            ('PL9026020', 'Tahunan'),
            ('PL9026030', 'Tahunan'),
            ('PL9027020', 'Tahunan'),
            ('PL9027030', 'Tahunan'),
            ('PL9028020', 'Tahunan'),
            ('PL9028030', 'Tahunan'),
            ('PL9029020', 'Tahunan'),
            ('PL9029030', 'Tahunan'),
            ('PL9030020', 'Tahunan'),
            ('PL9030030', 'Tahunan'),
            ('PL9031030', 'Tahunan'),
            ('PL9032010', 'Tahunan'),
            ('PL9032020', 'Tahunan'),
            ('PL9032030', 'Tahunan'),
            ('PL9033010', 'Tahunan'),
            ('PL9033020', 'Tahunan'),
            ('PL9034020', 'Tahunan'),
            ('PL9034030', 'Tahunan'),
            ('PL9035020', 'Tahunan'),
            ('PL9035030', 'Tahunan'),
            ('PL9036010', 'Tahunan'),
            ('PL9036020', 'Tahunan'),
            ('PL9036030', 'Tahunan'),
            ('PL9037020', 'Tahunan'),
            ('PL9037030', 'Tahunan'),
            ('PL9038010', 'Tahunan'),
            ('PL9038020', 'Tahunan'),
            ('PL9038030', 'Tahunan'),
            ('PL9039020', 'Tahunan'),
            ('PL9039030', 'Tahunan'),
            ('PL9040020', 'Tahunan'),
            ('PL9040030', 'Tahunan'),
            ('PL9041020', 'Tahunan'),
            ('PL9041030', 'Tahunan'),
            ('PL9042010', 'Tahunan'),
            ('PL9043020', 'Tahunan'),
            ('PL9043030', 'Tahunan'),
            ('PL9044010', 'Tahunan'),
            ('PL9044020', 'Tahunan'),
            ('PL9047010', 'Tahunan'),
            ('PL9047020', 'Tahunan'),
            ('PL9047030', 'Tahunan'),
            ('PL9048020', 'Tahunan'),
            ('PL9048030', 'Tahunan'),
            ('PL9055030', 'Tahunan'),
            ('PL9056030', 'Tahunan'),
            ('PL9057030', 'Tahunan'),
            ('PL9060801', 'Tahunan'),
            ('PL9080101', 'Tahunan'),
            ('PL9080102', 'Tahunan'),
            ('PL9080105', 'Tahunan'),
            ('PL9080106', 'Tahunan'),
            ('PL9080107', 'Tahunan'),
            ('PL9080108', 'Tahunan'),
            ('PL9080112', 'Tahunan'),
            ('PL9080114', 'Tahunan'),
            ('PL9084001', 'Tahunan'),
            ('PL9100201', 'Tahunan'),
            ('PL9100205', 'Tahunan'),
            ('PL9100601', 'Tahunan'),
            ('PL9100701', 'Tahunan'),
            ('PL9140201', 'Bulanan'),
            ('PL9140202', 'Bulanan'),
            ('PL9140203', 'Bulanan'),
            ('PL9140301', 'Bulanan'),
            ('PL9140302', 'Bulanan'),
            ('PL9150301', 'Tahunan'),
            ('PL9150302', 'Tahunan'),
            ('PL9150303', 'Tahunan'),
            ('PL9150304', 'Tahunan'),
            ('PL9150305', 'Tahunan'),
            ('PL9150306', 'Tahunan'),
            ('PL9150307', 'Tahunan'),
            ('PL9150308', 'Tahunan'),
            ('PL9150309', 'Tahunan'),
            ('PL9150310', 'Tahunan'),
            ('PL9150501', 'Tahunan'),
            ('PL9150601', 'Tahunan'),
            ('PL9150701', 'Tahunan'),
            ('PL9150702', 'Tahunan'),
            ('PL9150801', 'Bulanan'),
            ('PV0018001', 'Tahunan'),
            ('PV0025101', 'Bulanan'),
            ('PV0039101', 'Bulanan'),
            ('PV0204701', 'Bulanan'),
            ('PV0208101', 'Bulanan'),
            ('PV9080901', 'Tahunan'),
            ('PV9081101', 'Tahunan'),
            ('PV9087001', 'Tahunan'),
        ]

        inserts = 0
        unchanged = 0
        errors: list[str] = []
        inserted_keys: list[str] = []

        for id_sub_jenis_data, periode_penyampaian in ADDITIONAL_RECORDS:
            # Resolve FK references
            jenis_data_ilap = JenisDataILAP.objects.filter(id_sub_jenis_data=id_sub_jenis_data).first()
            if not jenis_data_ilap:
                err = f"JenisDataILAP with id_sub_jenis_data='{id_sub_jenis_data}' not found"
                logger.error(f"[post_periode_jenis_data_additional] {err}")
                errors.append(err)
                continue

            try:
                periode = PeriodePengiriman.objects.get(periode_penyampaian=periode_penyampaian)
            except PeriodePengiriman.DoesNotExist:
                err = f"PeriodePengiriman with periode_penyampaian='{periode_penyampaian}' not found"
                logger.error(f"[post_periode_jenis_data_additional] {err}")
                errors.append(err)
                continue

            # Check if record already exists by FK fields
            if PeriodeJenisData.objects.filter(
                id_sub_jenis_data_ilap=jenis_data_ilap,
                id_periode_pengiriman=periode,
            ).exists():
                logger.info(
                    f"[post_periode_jenis_data_additional] Record {id_sub_jenis_data} / "
                    f"{periode_penyampaian} already exists, skipping"
                )
                unchanged += 1
                continue

            if apply_changes:
                try:
                    PeriodeJenisData.objects.create(
                        id_sub_jenis_data_ilap=jenis_data_ilap,
                        id_periode_pengiriman=periode,
                        start_date=_date(2015, 1, 1),
                        akhir_penyampaian=0,
                    )
                    logger.info(
                        f"[post_periode_jenis_data_additional] Inserted {id_sub_jenis_data} / "
                        f"{periode_penyampaian}"
                    )
                    inserts += 1
                    inserted_keys.append(id_sub_jenis_data)
                except Exception as exc:
                    err = f"Failed to insert {id_sub_jenis_data} / {periode_penyampaian}: {exc}"
                    logger.error(f"[post_periode_jenis_data_additional] {err}")
                    errors.append(err)
            else:
                inserts += 1
                inserted_keys.append(id_sub_jenis_data)

        logger.info(
            f"[post_periode_jenis_data_additional] Completed: {inserts} inserts, "
            f"{unchanged} unchanged, {len(errors)} errors"
        )

        return OracleSyncSummary(
            table_name="post_periode_jenis_data_additional",
            source_table="<post-process>",
            target_model="diamond_web.PeriodeJenisData",
            source_rows=len(ADDITIONAL_RECORDS),
            inserts=inserts,
            updates=0,
            unchanged=unchanged,
            errors=errors,
            inserted_keys=inserted_keys,
        )

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

        # For durasi_jatuh_tempo_pmde: supplement oracle rows with default (durasi=85) rows
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

    def _post_process_update_nama_tabel_I_from_dde(self, apply_changes: bool) -> OracleSyncSummary:
        """After syncing jenis_data_ilap, update nama_tabel_I from ZA_DDE_TABEL_FACT.

        Runs a query against the primary Oracle connection to fetch distinct
        (id_sub_jenis_data, nama_tabel_dbbd) pairs from PVPTD.ZA_DDE_TABEL_FACT
        where each id_sub_jenis_data maps to exactly one nama_tabel_dbbd.
        Then updates the matching JenisDataILAP records with the new nama_tabel_I value.

        The Oracle query applies an id_tiket transformation:
        - If id_tiket length = 16 and starts with 'E', replace the 2nd char with 'I'
        - Then take the first 9 characters as id_sub_jenis_data

        Args:
            apply_changes: whether to persist the updates to DB.

        Returns:
            OracleSyncSummary describing what was done.
        """
        from diamond_web.models import JenisDataILAP

        update_query = """
            WITH unique_data AS (
                SELECT DISTINCT 
                    SUBSTR(CASE 
                        WHEN LENGTH(id_tiket) = 16 AND SUBSTR(id_tiket,1,1) = 'E' 
                        THEN SUBSTR(id_tiket, 1, 1) || 'I' || SUBSTR(id_tiket, 2)
                        ELSE id_tiket 
                    END, 1, 9) AS id_sub_jenis_data,
                    nama_tabel_dbbd
                FROM
                    PVPTD.ZA_DDE_TABEL_FACT
                WHERE 
                    nama_tabel_dbbd IS NOT NULL
            ),
            counted_data AS (
                SELECT 
                    id_sub_jenis_data,
                    nama_tabel_dbbd,
                    COUNT(*) OVER (PARTITION BY id_sub_jenis_data) AS total_count
                FROM 
                    unique_data
            )
            SELECT 
                id_sub_jenis_data,
                nama_tabel_dbbd nama_tabel_I
            FROM 
                counted_data
            WHERE 
                total_count = 1
        """

        source_rows_count = 0
        updates_count = 0
        unchanged_count = 0
        errors: list[str] = []
        updated_keys: list[str] = []

        try:
            with self._connect_oracle("primary") as conn:
                with conn.cursor() as cursor:
                    cursor.execute(update_query)
                    columns = [col[0].upper() for col in cursor.description]
                    rows = cursor.fetchall()
                    source_rows_count = len(rows)

                    logger.info(
                        f"[post_update_nama_tabel_I] Fetched {source_rows_count} rows from "
                        f"PVPTD.ZA_DDE_TABEL_FACT for nama_tabel_I update"
                    )

                    for row in rows:
                        row_dict = {
                            columns[idx]: self._normalize_value(value)
                            for idx, value in enumerate(row)
                        }
                        id_sub_jenis_data = row_dict.get("ID_SUB_JENIS_DATA")
                        new_nama_tabel_I = row_dict.get("NAMA_TABEL_I")

                        if not id_sub_jenis_data or not new_nama_tabel_I:
                            continue

                        # Find matching JenisDataILAP records (id_sub_jenis_data may not be unique)
                        jdi_list = list(JenisDataILAP.objects.filter(
                            id_sub_jenis_data=id_sub_jenis_data
                        ))

                        if not jdi_list:
                            logger.info(
                                f"[post_update_nama_tabel_I] No JenisDataILAP found for "
                                f"id_sub_jenis_data={id_sub_jenis_data}, skipping"
                            )
                            unchanged_count += 1
                            continue

                        any_updated = False
                        for jdi in jdi_list:
                            if jdi.nama_tabel_I == new_nama_tabel_I:
                                unchanged_count += 1
                                continue

                            if apply_changes:
                                try:
                                    new_nama_tabel_U = new_nama_tabel_I + '_U'
                                    jdi.nama_tabel_I = new_nama_tabel_I
                                    jdi.nama_tabel_U = new_nama_tabel_U
                                    jdi.save(update_fields=["nama_tabel_I", "nama_tabel_U"])
                                    logger.info(
                                        f"[post_update_nama_tabel_I] Updated {id_sub_jenis_data}: "
                                        f"nama_tabel_I '{new_nama_tabel_I}', "
                                        f"nama_tabel_U '{new_nama_tabel_U}'"
                                    )
                                except Exception as exc:
                                    err = (
                                        f"Failed to update {id_sub_jenis_data}: {exc}"
                                    )
                                    logger.error(f"[post_update_nama_tabel_I] {err}")
                                    errors.append(err)
                                    continue

                            any_updated = True
                            updated_keys.append(str(id_sub_jenis_data))

                        if any_updated:
                            updates_count += 1

        except Exception as exc:
            err = f"Failed to query PVPTD.ZA_DDE_TABEL_FACT: {exc}"
            logger.error(f"[post_update_nama_tabel_I] {err}")
            errors.append(err)

        logger.info(
            f"[post_update_nama_tabel_I] Completed: {updates_count} updates, "
            f"{unchanged_count} unchanged, {len(errors)} errors"
        )

        return OracleSyncSummary(
            table_name="post_update_nama_tabel_I_from_dde",
            source_table="PVPTD.ZA_DDE_TABEL_FACT",
            target_model="diamond_web.JenisDataILAP",
            source_rows=source_rows_count,
            inserts=0,
            updates=updates_count,
            unchanged=unchanged_count,
            errors=errors,
            inserted_keys=[],
            updated_keys=updated_keys[:20],
            skipped_rows_detail=[],
        )

    def _post_process_update_id_jenis_tabel_from_dde(self, apply_changes: bool) -> OracleSyncSummary:
        """After syncing jenis_data_ilap, update id_jenis_tabel from ZA_DDE_TABEL_FACT.

        Runs a query against the primary Oracle connection to fetch distinct
        (id_sub_jenis_data, JENIS_TABEL) pairs from PVPTD.ZA_DDE_TABEL_FACT
        where each id_sub_jenis_data maps to exactly one JENIS_TABEL.
        Then updates the matching JenisDataILAP records by resolving JENIS_TABEL
        to a JenisTabel FK reference via the deskripsi field.

        The Oracle query applies an id_tiket transformation:
        - If id_tiket length = 16 and starts with 'E', replace the 2nd char with 'I'
        - Then take the first 9 characters as id_sub_jenis_data

        Args:
            apply_changes: whether to persist the updates to DB.

        Returns:
            OracleSyncSummary describing what was done.
        """
        from diamond_web.models import JenisDataILAP, JenisTabel

        update_query = """
            WITH unique_data AS (
                SELECT DISTINCT 
                    SUBSTR(CASE 
                        WHEN LENGTH(id_tiket) = 16 AND SUBSTR(id_tiket,1,1) = 'E' 
                        THEN SUBSTR(id_tiket, 1, 1) || 'I' || SUBSTR(id_tiket, 2)
                        ELSE id_tiket 
                    END, 1, 9) AS id_sub_jenis_data,
                    JENIS_TABEL
                FROM
                    PVPTD.ZA_DDE_TABEL_FACT
                WHERE 
                    JENIS_TABEL IS NOT NULL
            ),
            counted_data AS (
                SELECT 
                    id_sub_jenis_data,
                    JENIS_TABEL,
                    COUNT(*) OVER (PARTITION BY id_sub_jenis_data) AS total_count
                FROM 
                    unique_data
            )
            SELECT 
                id_sub_jenis_data,
                JENIS_TABEL
            FROM 
                counted_data
            WHERE 
                total_count = 1
        """

        source_rows_count = 0
        updates_count = 0
        unchanged_count = 0
        errors: list[str] = []
        updated_keys: list[str] = []

        try:
            with self._connect_oracle("primary") as conn:
                with conn.cursor() as cursor:
                    cursor.execute(update_query)
                    columns = [col[0].upper() for col in cursor.description]
                    rows = cursor.fetchall()
                    source_rows_count = len(rows)

                    logger.info(
                        f"[post_update_id_jenis_tabel] Fetched {source_rows_count} rows from "
                        f"PVPTD.ZA_DDE_TABEL_FACT for id_jenis_tabel update"
                    )

                    for row in rows:
                        row_dict = {
                            columns[idx]: self._normalize_value(value)
                            for idx, value in enumerate(row)
                        }
                        id_sub_jenis_data = row_dict.get("ID_SUB_JENIS_DATA")
                        jenis_tabel_value = row_dict.get("JENIS_TABEL")

                        if not id_sub_jenis_data or not jenis_tabel_value:
                            continue

                        # Resolve JenisTabel FK reference via deskripsi
                        try:
                            jenis_tabel_obj = JenisTabel.objects.get(
                                deskripsi=jenis_tabel_value
                            )
                        except JenisTabel.DoesNotExist:
                            err = (
                                f"JenisTabel with deskripsi='{jenis_tabel_value}' "
                                f"not found for {id_sub_jenis_data}"
                            )
                            logger.warning(f"[post_update_id_jenis_tabel] {err}")
                            errors.append(err)
                            unchanged_count += 1
                            continue

                        # Find matching JenisDataILAP records (id_sub_jenis_data may not be unique)
                        jdi_list = list(JenisDataILAP.objects.filter(
                            id_sub_jenis_data=id_sub_jenis_data
                        ))

                        if not jdi_list:
                            logger.info(
                                f"[post_update_id_jenis_tabel] No JenisDataILAP found for "
                                f"id_sub_jenis_data={id_sub_jenis_data}, skipping"
                            )
                            unchanged_count += 1
                            continue

                        any_updated = False
                        for jdi in jdi_list:
                            if jdi.id_jenis_tabel_id == jenis_tabel_obj.pk:
                                unchanged_count += 1
                                continue

                            if apply_changes:
                                try:
                                    jdi.id_jenis_tabel = jenis_tabel_obj
                                    jdi.save(update_fields=["id_jenis_tabel"])
                                    logger.info(
                                        f"[post_update_id_jenis_tabel] Updated {id_sub_jenis_data}: "
                                        f"id_jenis_tabel -> '{jenis_tabel_value}' (pk={jenis_tabel_obj.pk})"
                                    )
                                except Exception as exc:
                                    err = (
                                        f"Failed to update {id_sub_jenis_data}: {exc}"
                                    )
                                    logger.error(f"[post_update_id_jenis_tabel] {err}")
                                    errors.append(err)
                                    continue

                            any_updated = True
                            updated_keys.append(str(id_sub_jenis_data))

                        if any_updated:
                            updates_count += 1

        except Exception as exc:
            err = f"Failed to query PVPTD.ZA_DDE_TABEL_FACT: {exc}"
            logger.error(f"[post_update_id_jenis_tabel] {err}")
            errors.append(err)

        logger.info(
            f"[post_update_id_jenis_tabel] Completed: {updates_count} updates, "
            f"{unchanged_count} unchanged, {len(errors)} errors"
        )

        return OracleSyncSummary(
            table_name="post_update_id_jenis_tabel_from_dde",
            source_table="PVPTD.ZA_DDE_TABEL_FACT",
            target_model="diamond_web.JenisDataILAP",
            source_rows=source_rows_count,
            inserts=0,
            updates=updates_count,
            unchanged=unchanged_count,
            errors=errors,
            inserted_keys=[],
            updated_keys=updated_keys[:20],
            skipped_rows_detail=[],
        )

    def _post_process_set_unstructured_jenis_tabel(self, apply_changes: bool) -> OracleSyncSummary:
        """After syncing jenis_data_ilap, set id_jenis_tabel to 'Tidak Terstruktur'
        for all records where nama_tabel_I = 'KPDE_DATA_UNSTRUCTURED'.

        Args:
            apply_changes: whether to persist the updates to DB.

        Returns:
            OracleSyncSummary describing what was done.
        """
        from diamond_web.models import JenisDataILAP, JenisTabel

        # Look up the 'Tidak Terstruktur' JenisTabel reference
        try:
            unstructured = JenisTabel.objects.get(deskripsi='Tidak Terstruktur')
        except JenisTabel.DoesNotExist:
            err = "JenisTabel with deskripsi='Tidak Terstruktur' not found"
            logger.error(f"[post_set_unstructured_jenis_tabel] {err}")
            return OracleSyncSummary(
                table_name="post_set_unstructured_jenis_tabel",
                source_table="<post-process>",
                target_model="diamond_web.JenisDataILAP",
                source_rows=0,
                inserts=0,
                updates=0,
                unchanged=0,
                errors=[err],
                inserted_keys=[],
                updated_keys=[],
                skipped_rows_detail=[],
            )

        # Find all records with nama_tabel_I = 'KPDE_DATA_UNSTRUCTURED'
        jdi_list = list(JenisDataILAP.objects.filter(
            nama_tabel_I='KPDE_DATA_UNSTRUCTURED'
        ))
        source_rows_count = len(jdi_list)

        updates_count = 0
        unchanged_count = 0
        errors: list[str] = []
        updated_keys: list[str] = []

        for jdi in jdi_list:
            if jdi.id_jenis_tabel_id == unstructured.pk:
                unchanged_count += 1
                continue

            if apply_changes:
                try:
                    jdi.id_jenis_tabel = unstructured
                    jdi.save(update_fields=["id_jenis_tabel"])
                    logger.info(
                        f"[post_set_unstructured_jenis_tabel] Updated {jdi.id_sub_jenis_data}: "
                        f"id_jenis_tabel -> 'Tidak Terstruktur' (pk={unstructured.pk})"
                    )
                except Exception as exc:
                    err = f"Failed to update {jdi.id_sub_jenis_data}: {exc}"
                    logger.error(f"[post_set_unstructured_jenis_tabel] {err}")
                    errors.append(err)
                    continue

            updates_count += 1
            updated_keys.append(str(jdi.id_sub_jenis_data))

        logger.info(
            f"[post_set_unstructured_jenis_tabel] Completed: {updates_count} updates, "
            f"{unchanged_count} unchanged, {len(errors)} errors"
        )

        return OracleSyncSummary(
            table_name="post_set_unstructured_jenis_tabel",
            source_table="<post-process>",
            target_model="diamond_web.JenisDataILAP",
            source_rows=source_rows_count,
            inserts=0,
            updates=updates_count,
            unchanged=unchanged_count,
            errors=errors,
            inserted_keys=[],
            updated_keys=updated_keys[:20],
            skipped_rows_detail=[],
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

            # Wrap each table in a nested savepoint so a failure in one table
            # does not break the outer transaction for subsequent tables.
            # This prevents "can't execute queries until end of atomic block" errors
            # cascading to dependent tables like pic_pmde_ref / durasi_jatuh_tempo_pmde.
            try:
                with transaction.atomic():
                    summary, target_model, inserts, updates = self._calculate_diff_for_config(cfg, stop_checker=stop_checker)
                    table_summaries.append(summary)

                    if apply_changes and not summary.errors:
                        self._apply_operations(target_model, inserts, updates)

                    cumulative_inserts += summary.inserts
                    cumulative_updates += summary.updates
                    cumulative_errors += len(summary.errors)

                    # Pre-process: before kategori_ilap sync, ensure KW record exists
                    if cfg.name == "kategori_ilap":
                        pre_summary = self._pre_process_kategori_ilap_kw(
                            apply_changes=apply_changes
                        )
                        if pre_summary:
                            table_summaries.append(pre_summary)
                            cumulative_inserts += pre_summary.inserts
                            cumulative_updates += pre_summary.updates
                            cumulative_errors += len(pre_summary.errors)

                    # Post-process: after ilap sync, insert additional default ILAP records
                    if cfg.name == "ilap":
                        post_summary = self._post_process_ilap_insert_defaults(
                            apply_changes=apply_changes
                        )
                        if post_summary:
                            table_summaries.append(post_summary)
                            cumulative_inserts += post_summary.inserts
                            cumulative_updates += post_summary.updates
                            cumulative_errors += len(post_summary.errors)

                    # Post-process: after jenis_data_ilap sync, insert AEOI domestic row
                    # and additional hardcoded records from additional_jenis_data_ilap.csv
                    if cfg.name == "jenis_data_ilap":
                        post_summary = self._post_process_jenis_data_ilap_aeoi_domestic(
                            apply_changes=apply_changes
                        )
                        if post_summary:
                            table_summaries.append(post_summary)
                            cumulative_inserts += post_summary.inserts
                            cumulative_updates += post_summary.updates
                            cumulative_errors += len(post_summary.errors)

                        post_summary = self._post_process_jenis_data_ilap_additional(
                            apply_changes=apply_changes
                        )
                        if post_summary:
                            table_summaries.append(post_summary)
                            cumulative_inserts += post_summary.inserts
                            cumulative_updates += post_summary.updates
                            cumulative_errors += len(post_summary.errors)

                        # Post-process: after jenis_data_ilap sync, update nama_tabel_I from ZA_DDE_TABEL_FACT
                        post_summary = self._post_process_update_nama_tabel_I_from_dde(
                            apply_changes=apply_changes
                        )
                        if post_summary:
                            table_summaries.append(post_summary)
                            cumulative_inserts += post_summary.inserts
                            cumulative_updates += post_summary.updates
                            cumulative_errors += len(post_summary.errors)

                        # Post-process: after jenis_data_ilap sync, update id_jenis_tabel from ZA_DDE_TABEL_FACT
                        post_summary = self._post_process_update_id_jenis_tabel_from_dde(
                            apply_changes=apply_changes
                        )
                        if post_summary:
                            table_summaries.append(post_summary)
                            cumulative_inserts += post_summary.inserts
                            cumulative_updates += post_summary.updates
                            cumulative_errors += len(post_summary.errors)

                        # Post-process: after jenis_data_ilap sync, set id_jenis_tabel to 'Tidak Terstruktur'
                        # for records with nama_tabel_I = 'KPDE_DATA_UNSTRUCTURED'
                        post_summary = self._post_process_set_unstructured_jenis_tabel(
                            apply_changes=apply_changes
                        )
                        if post_summary:
                            table_summaries.append(post_summary)
                            cumulative_inserts += post_summary.inserts
                            cumulative_updates += post_summary.updates
                            cumulative_errors += len(post_summary.errors)

                    # Post-process: after periode_jenis_data sync, insert additional records
                    if cfg.name == "periode_jenis_data":
                        post_summary = self._post_process_periode_jenis_data_additional(
                            apply_changes=apply_changes
                        )
                        if post_summary:
                            table_summaries.append(post_summary)
                            cumulative_inserts += post_summary.inserts
                            cumulative_updates += post_summary.updates
                            cumulative_errors += len(post_summary.errors)

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