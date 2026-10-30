"""Move large result values already stored in the database to files.

New results are written this way by TaskOutputProcessor (values over
OFFLOAD_BYTES go to a file next to the image's other outputs and the
database keeps {"file": path, "bytes": n}); this applies the same to rows
saved before that, e.g. MotionCor's patch-alignment data and CTFFIND's
rotational average.

    docker exec -w /app/CoreService magellon-core-container \
        python -m scripts.offload_large_metadata [--dry-run]
"""
import argparse
import json
import os

from sqlalchemy import func, or_

from config import MAGELLON_HOME_DIR, app_settings
from database import session_local
from models.sqlalchemy_models import Image, ImageMetaData, Msession
from services.task_output_processor import OFFLOAD_BYTES, TaskOutputProcessor, offload_to_file


def _destination(processor, session_name: str, row_name: str, image: Image) -> tuple[str, str]:
    """The folder new results of this kind go to, and the image's file stem."""
    step = row_name.split(" ")[0].lower()           # "MotionCor Meta Data" -> motioncor
    folder = processor._get_queue_type_output_dir(step) or step
    stem = os.path.splitext(os.path.basename(image.path or image.name or ""))[0] or str(image.oid)
    return os.path.join(MAGELLON_HOME_DIR, session_name, folder, stem), stem


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="report what would move, change nothing")
    args = parser.parse_args()

    processor = TaskOutputProcessor(db=None, out_queues=app_settings.rabbitmq_settings.OUT_QUEUES)
    moved_rows = moved_bytes = 0
    with session_local() as db:
        ids = [oid for (oid,) in db.query(ImageMetaData.oid).filter(or_(
            func.length(ImageMetaData.data) > OFFLOAD_BYTES,
            func.length(ImageMetaData.data_json) > OFFLOAD_BYTES))]
        for oid in ids:
            row = db.get(ImageMetaData, oid)
            image = db.get(Image, row.image_id) if row.image_id else None
            session = db.get(Msession, image.session_id) if image and image.session_id else None
            if session is None:
                continue
            folder, stem = _destination(processor, session.name, row.name or "", image)
            before = len(row.data or b"") + len(json.dumps(row.data_json) if row.data_json else "")

            if isinstance(row.data_json, list):         # meta data: [{"key", "value"}, ...]
                items = []
                for item in row.data_json:
                    value = item.get("value") if isinstance(item, dict) else None
                    if isinstance(value, str) and len(value) > OFFLOAD_BYTES:
                        ref = {"file": os.path.join(folder, f"{stem}_{item['key']}.json"), "bytes": len(value.encode())}
                        if not args.dry_run:
                            ref = offload_to_file(folder, stem, item["key"], value, ".json")
                        item = {**item, "value": json.dumps(ref)}
                    items.append(item)
                row.data_json = items
            if row.data:                                # output data: one JSON object
                output = json.loads(row.data)
                if isinstance(output, dict):
                    for key, value in list(output.items()):
                        text = value if isinstance(value, str) else json.dumps(value)
                        if len(text) > OFFLOAD_BYTES:
                            ext = ".txt" if isinstance(value, str) else ".json"
                            output[key] = ({"file": os.path.join(folder, f"{stem}_{key}{ext}"), "bytes": len(text.encode())}
                                           if args.dry_run else offload_to_file(folder, stem, key, text, ext))
                    row.data = json.dumps(output).encode("utf-8")

            after = len(row.data or b"") + len(json.dumps(row.data_json) if row.data_json else "")
            moved_rows += 1
            moved_bytes += before - after
            if args.dry_run:
                db.expunge(row)
            elif moved_rows % 200 == 0:
                db.commit()
        if not args.dry_run:
            db.commit()
    verb = "would move" if args.dry_run else "moved"
    print(f"{verb} {moved_bytes / 1048576:.1f} MB out of {moved_rows} metadata row(s)")


if __name__ == "__main__":
    main()
