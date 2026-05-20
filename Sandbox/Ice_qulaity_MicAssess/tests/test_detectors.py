import pytest

from cryoassess.core.detectors import DETECTOR_WIDTH, IMAGE_HEIGHT, detector_width


def test_image_height_is_494():
    assert IMAGE_HEIGHT == 494


def test_detector_width_known_detectors():
    assert detector_width("K2") == 512
    assert detector_width("K3") == 696


def test_detector_width_rejects_unknown_detector():
    with pytest.raises(ValueError, match="unknown detector"):
        detector_width("K9")


def test_detector_width_matches_table():
    for detector, width in DETECTOR_WIDTH.items():
        assert detector_width(detector) == width
