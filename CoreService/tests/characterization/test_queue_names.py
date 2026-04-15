"""Characterization tests for RabbitMQ queue naming.

Plugins listen on specific queue names. If the mapping from TaskCategory to
queue name changes without coordination, messages vanish silently. These
tests pin the current mapping.
"""
from __future__ import annotations

import pytest

from config import app_settings
from core.helper import get_queue_name_by_task_type
from models.plugins_models import (
    CTF_TASK,
    FFT_TASK,
    MOTIONCOR_TASK,
    PARTICLE_PICKING,
    TWO_D_CLASSIFICATION,
)


@pytest.mark.characterization
def test_ctf_queue_names():
    assert get_queue_name_by_task_type(CTF_TASK, is_result=False) == "ctf_tasks_queue"
    assert get_queue_name_by_task_type(CTF_TASK, is_result=True) == "ctf_out_tasks_queue"


@pytest.mark.characterization
def test_motioncor_queue_names():
    assert get_queue_name_by_task_type(MOTIONCOR_TASK, is_result=False) == "motioncor_tasks_queue"
    assert get_queue_name_by_task_type(MOTIONCOR_TASK, is_result=True) == "motioncor_out_tasks_queue"


@pytest.mark.characterization
def test_fft_queue_names():
    assert get_queue_name_by_task_type(FFT_TASK, is_result=False) == "fft_tasks_queue"
    assert get_queue_name_by_task_type(FFT_TASK, is_result=True) == "fft_out_tasks_queue"


@pytest.mark.characterization
def test_unmapped_categories_return_none():
    """Categories without a queue mapping return None (not raise).

    Pins today's permissive behaviour so we notice if it tightens.
    """
    assert get_queue_name_by_task_type(PARTICLE_PICKING, is_result=False) is None
    assert get_queue_name_by_task_type(TWO_D_CLASSIFICATION, is_result=False) is None


@pytest.mark.characterization
def test_app_settings_queue_values():
    """Settings loaded from YAML match the hardcoded expectations in the mapping."""
    r = app_settings.rabbitmq_settings
    assert r.CTF_QUEUE_NAME == "ctf_tasks_queue"
    assert r.CTF_OUT_QUEUE_NAME == "ctf_out_tasks_queue"
    assert r.MOTIONCOR_QUEUE_NAME == "motioncor_tasks_queue"
    assert r.MOTIONCOR_OUT_QUEUE_NAME == "motioncor_out_tasks_queue"
    assert r.FFT_QUEUE_NAME == "fft_tasks_queue"
    assert r.FFT_OUT_QUEUE_NAME == "fft_out_tasks_queue"
