"""Linking Leginon images to their parents."""
import uuid

from models.sqlalchemy_models import Image
from services.leginon_frame_transfer_job_service import LeginonFrameTransferJobService, recorded_parents

HOLE = "s_00009sq_v02_00002hl_v02"
TILT = HOLE + "_00002tom2_001"


def _row(image_id, filename, parent=None):
    return {"image_id": image_id, "filename": filename, "parent_image_id": parent}


def _link(rows):
    images = [Image(oid=uuid.uuid4(), name=row["filename"]) for row in rows]
    by_name = {image.name: image for image in images}
    LeginonFrameTransferJobService()._link_parent_images(
        images, {image.name: image.oid for image in images}, recorded_parents(rows))
    return lambda name: next((i.name for i in images if i.oid == by_name[name].parent_id), None)


def test_tilt_image_goes_under_the_recorded_hole():
    parent_of = _link([_row(1, HOLE), _row(2, TILT, 1)])
    assert parent_of(TILT) == HOLE


def test_tilt_image_without_a_record_stays_at_the_top():
    parent_of = _link([_row(1, HOLE), _row(2, TILT)])
    assert parent_of(TILT) is None


def test_the_name_is_used_when_nothing_is_recorded():
    parent_of = _link([_row(1, "s_00031gr"), _row(2, "s_00031gr_00001sq")])
    assert parent_of("s_00031gr_00001sq") == "s_00031gr"


def test_a_versioned_name_still_finds_its_parent_without_a_record():
    parent_of = _link([_row(1, "s_00031gr"), _row(2, "s_00031gr_00001sq_v01")])
    assert parent_of("s_00031gr_00001sq_v01") == "s_00031gr"


def test_the_record_wins_over_the_name():
    parent_of = _link([_row(1, "s_00031gr"), _row(2, "s_00032gr"), _row(3, "s_00031gr_00001sq", 2)])
    assert parent_of("s_00031gr_00001sq") == "s_00032gr"


def test_a_recorded_parent_outside_the_import_falls_back_to_the_name():
    parent_of = _link([_row(1, "s_00031gr"), _row(2, "s_00031gr_00001sq", 999)])
    assert parent_of("s_00031gr_00001sq") == "s_00031gr"


def test_a_grid_tile_has_no_parent():
    parent_of = _link([_row(1, "s_00031gr")])
    assert parent_of("s_00031gr") is None
