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


logger = logging.getLogger(__name__)


class OracleSyncConfigError(Exception):
    """Raised when Oracle sync configuration is invalid."""


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
HARD_CODED_SYNC_TABLES: list[OracleSyncTableConfig] = [
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
        name="ilap",
        source_table="PROD.APP_ILAP",
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
    OracleSyncTableConfig(
        name="jenis_data_ilap",
        source_query="""
            SELECT
                a.id_ilap,
                a.ID_JENIS_DATA,
                b.ID_TABEL_DATA AS ID_SUB_JENIS_DATA,
                a.NAMA_JENIS_DATA,
                a.NAMA_JENIS_DATA AS NAMA_SUB_JENIS_DATA,
                b.NAMA_TABEL_TIP AS NAMA_TABEL_I,
                b.NAMA_TABEL_TIP || '_U' AS NAMA_TABEL_U,
                CASE
                    WHEN c."JENIS TABEL" = 'MASTER' THEN 'Diidentifikasi'
                    WHEN c."JENIS TABEL" = 'TRANSAKSI' THEN 'Tidak Diidentifikasi'
                    WHEN c."JENIS TABEL" = 'UNSTRUCTURE' THEN 'Tidak Terstruktur'
                    ELSE NULL
                END JENIS_TABEL,
                'Data Utama' STATUS_DATA
            FROM
                (
                SELECT
                    *
                FROM
                    PROD.APP_JENIS_DATA_ILAP) a
            JOIN 
                (
                SELECT
                    *
                FROM
                    PROD.APP_TABEL_DATA_ILAP) b
            ON
                a.ID_JENIS_DATA = b.ID_JENIS_DATA
            JOIN 
                (
                SELECT
                    *
                FROM
                    PVPTD.ZA_REKAP_KOLOM_TABEL_PIC) c 
            ON
                b.NAMA_TABEL_TIP = c.NM_TABEL_FINAL
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
        name="dasar_hukum",
        source_table="PROD.REF_DASAR_HUKUM",
        target_model_label="diamond_web.DasarHukum",
        target_key_field="deskripsi",
        source_key_column="NAMA_DASAR_HUKUM",
        field_map={
            "kategori": "ID_KATEGORI_DASAR_HUKUM",
            "deskripsi": "NAMA_DASAR_HUKUM",
        },
        where_clause="",
    ),
]


class OracleDataSyncService:
    """Sync rows from Oracle tables into one or more configured Django models."""

    _IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$.]*$")

    def __init__(self):
        self.oracle_user = os.getenv("ORACLE_USER", "").strip()
        self.oracle_password = os.getenv("ORACLE_PASSWORD", "").strip()
        self.oracle_host = os.getenv("ORACLE_HOST", "").strip()
        self.oracle_port = int(os.getenv("ORACLE_PORT", "1521"))
        self.oracle_service_name = os.getenv("ORACLE_SERVICE_NAME", "").strip()
        self.oracle_sid = os.getenv("ORACLE_SID", "").strip()

        self._target_model_cache: dict[str, Any] = {}

        self._validate_connection_config()
        self._validate_sync_configs(HARD_CODED_SYNC_TABLES)

    def _validate_identifier(self, value: str, label: str):
        if not self._IDENTIFIER_RE.match(value):
            raise OracleSyncConfigError(f"{label} tidak valid: {value}")

    def _validate_connection_config(self):
        required_values = {
            "ORACLE_USER": self.oracle_user,
            "ORACLE_PASSWORD": self.oracle_password,
            "ORACLE_HOST": self.oracle_host,
        }
        missing = [name for name, value in required_values.items() if not value]
        if missing:
            raise OracleSyncConfigError(
                "Konfigurasi Oracle belum lengkap: " + ", ".join(missing)
            )

        if not self.oracle_service_name and not self.oracle_sid:
            raise OracleSyncConfigError("Set ORACLE_SERVICE_NAME atau ORACLE_SID di .env")

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

    def _connect_oracle(self):
        try:
            import cx_Oracle
        except Exception as exc:
            raise OracleSyncConfigError(
                "Library cx_Oracle belum terpasang. Install dependency terlebih dahulu."
            ) from exc

        if self.oracle_service_name:
            dsn = cx_Oracle.makedsn(
                self.oracle_host,
                self.oracle_port,
                service_name=self.oracle_service_name,
            )
        else:
            dsn = cx_Oracle.makedsn(
                self.oracle_host,
                self.oracle_port,
                sid=self.oracle_sid,
            )

        return cx_Oracle.connect(
            user=self.oracle_user,
            password=self.oracle_password,
            dsn=dsn,
        )

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
        logger.debug("Oracle sync query [%s]: %s", cfg.name, sql)

        with self._connect_oracle() as conn:
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
        mapped_values[cfg.target_key_field] = key_value
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

        raise ValueError(f"Rule derived tidak dikenali: {rule_name}")

    def _calculate_diff_for_config(
        self,
        cfg: OracleSyncTableConfig,
    ) -> tuple[OracleSyncSummary, Any, list[dict[str, Any]], list[tuple[Any, dict[str, Any]]]]:
        target_model = self._get_target_model(cfg.target_model_label)
        source_rows = self._fetch_oracle_rows(cfg)

        normalized_rows: list[dict[str, Any]] = []
        key_values: list[Any] = []
        errors: list[str] = []

        for source_row in source_rows:
            try:
                _, mapped = self._map_source_to_target(cfg, target_model, source_row)
                normalized_rows.append(mapped)
                key_values.append(mapped[cfg.target_key_field])
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
            key_value = mapped[cfg.target_key_field]
            lookup_kwargs: dict[str, Any] = {}
            for field_name in match_fields:
                stored_name = _storage_field_name(field_name)
                lookup_kwargs[stored_name] = mapped.get(stored_name)
            obj = target_model.objects.filter(**lookup_kwargs).first()
            
            if obj is None:
                inserts.append(mapped)
                inserted_keys.append(str(key_value))
                continue

            changed_fields: dict[str, Any] = {}
            for field_name, new_value in mapped.items():
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
        )
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
            except Exception as exc:
                # Try to find which row caused the error
                for idx, data in enumerate(inserts):
                    try:
                        target_model.objects.create(**data)
                    except Exception as row_exc:
                        error_details = f"Row {idx}: {dict(data)}"
                        raise Exception(f"{exc.__class__.__name__}: {str(exc)}\n{error_details}") from row_exc
                raise

        for obj, changed_fields in updates:
            for field_name, value in changed_fields.items():
                setattr(obj, field_name, value)
            try:
                obj.save(update_fields=list(changed_fields.keys()))
            except Exception as exc:
                error_details = f"Object key={getattr(obj, 'pk', 'unknown')}, changes={dict(changed_fields)}"
                raise Exception(f"{exc.__class__.__name__}: {str(exc)}\n{error_details}") from exc

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

    def _run_sequential(self, apply_changes: bool) -> OracleSyncBatchSummary:
        table_summaries: list[OracleSyncSummary] = []

        for cfg in HARD_CODED_SYNC_TABLES:
            try:
                summary, target_model, inserts, updates = self._calculate_diff_for_config(cfg)
                table_summaries.append(summary)

                if apply_changes and not summary.errors:
                    self._apply_operations(target_model, inserts, updates)
            except Exception as exc:
                table_summaries.append(
                    OracleSyncSummary(
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
                    )
                )

        return self._build_batch_summary(table_summaries)

    def check(self) -> OracleSyncBatchSummary:
        # Simulasikan apply dalam 1 transaksi agar dependency antar tabel (parent-child)
        # bisa tervalidasi, lalu rollback supaya data tidak tersimpan.
        with transaction.atomic():
            summary = self._run_sequential(apply_changes=True)
            transaction.set_rollback(True)
            return summary

    def sync(self) -> OracleSyncBatchSummary:
        with transaction.atomic():
            summary = self._run_sequential(apply_changes=True)
            if summary.errors:
                transaction.set_rollback(True)
            return summary