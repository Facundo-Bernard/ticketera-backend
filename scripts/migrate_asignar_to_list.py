"""Script de migración idempotente para convertir Ticket.asignar a List[str] en MongoDB."""

import argparse
import os
import sys
from typing import Any, Dict, List, Optional

from pymongo import MongoClient, UpdateOne

# Permitir ejecutar el script directamente desde la raíz del repo o desde scripts/
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.config.settings import settings  # noqa: E402
from src.models.ticket_model import normalize_asignados  # noqa: E402


def migrate_asignar(
    mongo_uri: str,
    db_name: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Migra todos los documentos de la colección 'tickets' con asignar legado a lista normalizada."""
    client: Optional[MongoClient] = None
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        collection = client[db_name]["tickets"]

        total_docs = 0
        pending_ops: List[UpdateOne] = []
        changes: List[Dict[str, Any]] = []

        cursor = collection.find({}, {"_id": 1, "identificador": 1, "asignar": 1})
        for doc in cursor:
            total_docs += 1
            has_field = "asignar" in doc
            raw_value = doc.get("asignar")
            normalized = normalize_asignados(raw_value)

            needs_update = (
                not has_field
                or not isinstance(raw_value, list)
                or raw_value != normalized
            )
            if needs_update:
                pending_ops.append(
                    UpdateOne({"_id": doc["_id"]}, {"$set": {"asignar": normalized}})
                )
                changes.append(
                    {
                        "id": str(doc["_id"]),
                        "identificador": doc.get("identificador") or str(doc["_id"]),
                        "before": raw_value if has_field else "<missing>",
                        "after": normalized,
                    }
                )

        modified_count = 0
        if not dry_run and pending_ops:
            result = collection.bulk_write(pending_ops, ordered=False)
            modified_count = result.modified_count

        return {
            "total_scanned": total_docs,
            "pending_count": len(pending_ops),
            "modified_count": modified_count,
            "dry_run": dry_run,
            "changes": changes,
        }
    finally:
        if client is not None:
            client.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migra el campo 'asignar' de los tickets existentes en MongoDB a formato lista."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la migración sin modificar documentos en MongoDB.",
    )
    parser.add_argument(
        "--uri",
        default=settings.MONGO_URI,
        help="URI de conexión a MongoDB (por defecto usa MONGO_URI del .env).",
    )
    parser.add_argument(
        "--db",
        default=settings.MONGO_DB_NAME,
        help="Nombre de la base de datos (por defecto usa MONGO_DB_NAME del .env).",
    )
    args = parser.parse_args()

    summary = migrate_asignar(
        mongo_uri=args.uri,
        db_name=args.db,
        dry_run=args.dry_run,
    )

    mode_label = "DRY-RUN" if summary["dry_run"] else "EJECUCIÓN REAL"
    print(f"[{mode_label}] Base de datos: {args.db}")
    print(f"Documentos inspeccionados: {summary['total_scanned']}")
    print(f"Documentos a migrar: {summary['pending_count']}")

    for change in summary["changes"]:
        print(
            f"  - {change['identificador']} ({change['id']}): "
            f"{change['before']!r} -> {change['after']!r}"
        )

    if not summary["dry_run"]:
        print(f"Documentos actualizados en MongoDB: {summary['modified_count']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
