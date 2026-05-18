import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import transaction


logger = logging.getLogger(__name__)


class OracleSyncConfigError(Exception):
    """Raised when Oracle sync configuration is invalid."""


@dataclass
class OracleSyncSummary:
    source_rows: int
    inserts: int
    updates: int
    unchanged: int
    errors: list[str]
    inserted_keys: list[str]
    updated_keys: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_rows": self.source_rows,
            "inserts": self.inserts,
            "updates": self.updates,
            "unchanged": self.unchanged,
            "errors": self.errors,
            "inserted_keys": self.inserted_keys,
            "updated_keys": self.updated_keys,
        }


class OracleDataSyncService:
    """Sync rows from Oracle table into a configured Django model."""

    _IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$.]*$")

    def __init__(self):
        self.oracle_user = os.getenv("ORACLE_USER", "").strip()
        self.oracle_password = os.getenv("ORACLE_PASSWORD", "").strip()
        self.oracle_host = os.getenv("ORACLE_HOST", "").strip()
        self.oracle_port = int(os.getenv("ORACLE_PORT", "1521"))
        self.oracle_service_name = os.getenv("ORACLE_SERVICE_NAME", "").strip()
        self.oracle_sid = os.getenv("ORACLE_SID", "").strip()

        self.source_table = os.getenv("ORACLE_SYNC_SOURCE_TABLE", "").strip()
        self.target_model_label = os.getenv("ORACLE_SYNC_TARGET_MODEL", "").strip()
        self.target_key_field = os.getenv("ORACLE_SYNC_TARGET_KEY_FIELD", "").strip()
        self.source_key_column = os.getenv("ORACLE_SYNC_SOURCE_KEY_COLUMN", "").strip()
        self.field_map_json = os.getenv("ORACLE_SYNC_FIELD_MAP_JSON", "").strip()
        self.where_clause = os.getenv("ORACLE_SYNC_SOURCE_WHERE", "").strip()

        self._validate_config()
        self.target_model = apps.get_model(self.target_model_label)
        self.field_map = self._load_field_map()

    def _validate_identifier(self, value: str, label: str):
        if not self._IDENTIFIER_RE.match(value):
            raise OracleSyncConfigError(f"{label} tidak valid: {value}")

    def _validate_config(self):
        required_values = {
            "ORACLE_USER": self.oracle_user,
            "ORACLE_PASSWORD": self.oracle_password,
            "ORACLE_HOST": self.oracle_host,
            "ORACLE_SYNC_SOURCE_TABLE": self.source_table,
            "ORACLE_SYNC_TARGET_MODEL": self.target_model_label,
            "ORACLE_SYNC_TARGET_KEY_FIELD": self.target_key_field,
            "ORACLE_SYNC_SOURCE_KEY_COLUMN": self.source_key_column,
            "ORACLE_SYNC_FIELD_MAP_JSON": self.field_map_json,
        }
        missing = [name for name, value in required_values.items() if not value]
        if missing:
            raise OracleSyncConfigError(
                "Konfigurasi Oracle sync belum lengkap: " + ", ".join(missing)
            )

        if not self.oracle_service_name and not self.oracle_sid:
            raise OracleSyncConfigError(
                "Set ORACLE_SERVICE_NAME atau ORACLE_SID di .env"
            )

        self._validate_identifier(self.source_table, "ORACLE_SYNC_SOURCE_TABLE")
        self._validate_identifier(self.source_key_column, "ORACLE_SYNC_SOURCE_KEY_COLUMN")

    def _load_field_map(self) -> dict[str, str]:
        try:
            mapping = json.loads(self.field_map_json)
        except json.JSONDecodeError as exc:
            raise OracleSyncConfigError(
                "ORACLE_SYNC_FIELD_MAP_JSON harus format JSON object"
            ) from exc

        if not isinstance(mapping, dict) or not mapping:
            raise OracleSyncConfigError(
                "ORACLE_SYNC_FIELD_MAP_JSON harus object non-empty"
            )

        normalized: dict[str, str] = {}
        for target_field, source_column in mapping.items():
            if not isinstance(target_field, str) or not isinstance(source_column, str):
                raise OracleSyncConfigError(
                    "Field map hanya boleh berisi pasangan string"
                )
            source_column = source_column.strip()
            self._validate_identifier(source_column, "Source column")
            normalized[target_field.strip()] = source_column

            try:
                field_obj = self.target_model._meta.get_field(target_field)
                if field_obj.is_relation:
                    raise OracleSyncConfigError(
                        f"Field relasi belum didukung untuk sync otomatis: {target_field}"
                    )
            except FieldDoesNotExist as exc:
                raise OracleSyncConfigError(
                    f"Field target tidak ada di model: {target_field}"
                ) from exc

        return normalized

    def _connect_oracle(self):
        try:
            import cx_Oracle
        except Exception as exc:
            raise OracleSyncConfigError(
                "Library cx_Oracle belum terpasang. Install dependency terlebih dahulu."
            ) from exc

        dsn = None
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

    def _build_select_sql(self) -> str:
        columns = [self.source_key_column, *self.field_map.values()]
        dedup_columns: list[str] = []
        for c in columns:
            if c not in dedup_columns:
                dedup_columns.append(c)

        columns_sql = ", ".join(dedup_columns)
        sql = f"SELECT {columns_sql} FROM {self.source_table}"
        if self.where_clause:
            sql = f"{sql} WHERE {self.where_clause}"
        return sql

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

    def _coerce_model_value(self, model_field_name: str, value: Any) -> Any:
        field_obj = self.target_model._meta.get_field(model_field_name)
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

    def _fetch_oracle_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        sql = self._build_select_sql()
        logger.info("Oracle sync query: %s", sql)

        with self._connect_oracle() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                columns = [col[0].upper() for col in cursor.description]

                for row in cursor.fetchall():
                    mapped = {columns[idx]: self._normalize_value(value) for idx, value in enumerate(row)}
                    rows.append(mapped)

        return rows

    def _map_source_to_target(self, source_row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        key = source_row.get(self.source_key_column.upper())
        if key is None:
            raise ValueError(f"Key source column {self.source_key_column} bernilai NULL")

        mapped_values: dict[str, Any] = {}
        for target_field, source_column in self.field_map.items():
            raw_value = source_row.get(source_column.upper())
            mapped_values[target_field] = self._coerce_model_value(target_field, raw_value)

        key_value = self._coerce_model_value(self.target_key_field, key)
        mapped_values[self.target_key_field] = key_value
        return str(key_value), mapped_values

    def _calculate_diff(self) -> tuple[OracleSyncSummary, list[dict[str, Any]], list[tuple[Any, dict[str, Any]]]]:
        source_rows = self._fetch_oracle_rows()
        key_field = self.target_key_field

        normalized_rows: list[dict[str, Any]] = []
        key_values: list[Any] = []
        errors: list[str] = []

        for source_row in source_rows:
            try:
                _, mapped = self._map_source_to_target(source_row)
                normalized_rows.append(mapped)
                key_values.append(mapped[key_field])
            except Exception as exc:
                errors.append(str(exc))

        existing = self.target_model.objects.in_bulk(key_values, field_name=key_field)

        inserts: list[dict[str, Any]] = []
        updates: list[tuple[Any, dict[str, Any]]] = []
        unchanged = 0
        inserted_keys: list[str] = []
        updated_keys: list[str] = []

        for mapped in normalized_rows:
            key_value = mapped[key_field]
            obj = existing.get(key_value)
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
            source_rows=len(source_rows),
            inserts=len(inserts),
            updates=len(updates),
            unchanged=unchanged,
            errors=errors,
            inserted_keys=inserted_keys[:20],
            updated_keys=updated_keys[:20],
        )
        return summary, inserts, updates

    def check(self) -> OracleSyncSummary:
        summary, _, _ = self._calculate_diff()
        return summary

    def sync(self) -> OracleSyncSummary:
        summary, inserts, updates = self._calculate_diff()
        if summary.errors:
            return summary

        with transaction.atomic():
            if inserts:
                self.target_model.objects.bulk_create([
                    self.target_model(**data) for data in inserts
                ])

            for obj, changed_fields in updates:
                for field_name, value in changed_fields.items():
                    setattr(obj, field_name, value)
                update_fields = list(changed_fields.keys())
                obj.save(update_fields=update_fields)

        return summary