import pytest

from avatar import ffmpeg
from avatar.prepare import load_clips, parse_time, prepare


def test_parse_time():
    assert parse_time("00:02") == 2
    assert parse_time("01:00:02.5") == 3602.5


def test_load_clips_rejects_reversed_span(tmp_path):
    f = tmp_path / "clips.yaml"
    f.write_text('a: "00:09-00:02"\n')
    with pytest.raises(ValueError, match="se termine avant"):
        load_clips(f)


def test_prepare_extracts_refs_and_clips(project):
    prepare(project)

    wav = ffmpeg.probe(project.path("ref_wav"))["streams"][0]
    assert wav["channels"] == 1 and wav["sample_rate"] == "24000"
    assert 15 <= ffmpeg.duration(project.path("ref_wav")) <= 20.05

    png = ffmpeg.probe(project.path("ref_png"))["streams"][0]
    assert (png["width"], png["height"]) == (1920, 1080)

    for name, (start, end) in load_clips(project.path("clips")).items():
        clip = project.path("clips_dir") / f"{name}.mp4"
        assert ffmpeg.duration(clip) == pytest.approx(end - start, abs=0.1)
