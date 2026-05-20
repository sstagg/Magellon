import numpy as np

from cryoassess.core.labels import (
    LABEL_LIST,
    assign_label,
    assign_labels,
    is_good,
)


def test_label_list_has_six_classes():
    assert len(LABEL_LIST) == 6


def test_assign_label_great():
    # binary head says good (low bad-prob), good head says great (low decent-prob)
    assert assign_label([0.0], [0.0], [1, 0, 0, 0]) == 0


def test_assign_label_decent():
    # binary head says good, good head says decent (high decent-prob)
    assert assign_label([0.0], [1.0], [1, 0, 0, 0]) == 1


def test_assign_label_bad_uses_argmax_plus_two():
    # binary head says bad; bad head argmax 2 -> six-class label 4
    assert assign_label([1.0], [0.0], [0, 0, 1, 0]) == 4
    assert assign_label([1.0], [0.0], [0, 1, 0, 0]) == 3


def test_t1_tolerance_shifts_good_bad_boundary():
    binary_prob = [0.85]
    # default t1=0.1 -> good cut 0.9 -> 0.85 is good
    assert assign_label(binary_prob, [0.0], [1, 0, 0, 0], t1=0.1) == 0
    # t1=0.2 -> good cut 0.8 -> 0.85 is now bad
    assert assign_label(binary_prob, [0.0], [1, 0, 0, 0], t1=0.2) >= 2


def test_t2_tolerance_shifts_great_decent_boundary():
    good_prob = [0.85]
    # t2=0.1 -> great cut 0.9 -> 0.85 < 0.9 -> great
    assert assign_label([0.0], good_prob, [1, 0, 0, 0], t2=0.1) == 0
    # t2=0.2 -> great cut 0.8 -> 0.85 >= 0.8 -> decent
    assert assign_label([0.0], good_prob, [1, 0, 0, 0], t2=0.2) == 1


def test_assign_labels_batch():
    binary = np.array([[0.0], [1.0]])
    good = np.array([[0.0], [0.0]])
    bad = np.array([[1, 0, 0, 0], [0, 1, 0, 0]])
    assert list(assign_labels(binary, good, bad)) == [0, 3]


def test_is_good():
    assert is_good(0)
    assert is_good(1)
    assert not is_good(2)
    assert not is_good(5)
