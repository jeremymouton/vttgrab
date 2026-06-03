from vttgrab.cue import Cue
from vttgrab.merge import merge_cues


def test_merge_dedupes_boundary_cue():
    # A cue straddling the seam appears at the end of seg A and start of seg B.
    seg_a = [Cue(0, 1000, "first"), Cue(1000, 2000, "boundary")]
    seg_b = [Cue(1000, 2000, "boundary"), Cue(2000, 3000, "third")]
    merged = merge_cues([seg_a, seg_b])
    assert [c.text for c in merged] == ["first", "boundary", "third"]


def test_merge_sorts_by_start_then_end():
    out = merge_cues([[Cue(3000, 4000, "c")], [Cue(1000, 2000, "a"), Cue(1000, 1500, "a2")]])
    assert [c.text for c in out] == ["a2", "a", "c"]


def test_merge_keeps_distinct_cues_with_same_time_diff_text():
    out = merge_cues([[Cue(1000, 2000, "x")], [Cue(1000, 2000, "y")]])
    assert len(out) == 2


def test_merge_empty():
    assert merge_cues([]) == []
    assert merge_cues([[], []]) == []


def test_merge_different_settings_not_deduped():
    out = merge_cues([[Cue(0, 1000, "x", settings="a")], [Cue(0, 1000, "x", settings="b")]])
    assert len(out) == 2
