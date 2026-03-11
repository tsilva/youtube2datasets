from youtube2datasets.media import compute_resized_dimensions


def test_resize_keeps_aspect_ratio_inside_box() -> None:
    assert compute_resized_dimensions(320, 200, 128, 128) == (128, 80)


def test_resize_only_scales_down() -> None:
    assert compute_resized_dimensions(256, 192, 512, 384) == (512, 384)
    assert compute_resized_dimensions(256, 192, None, 96) == (128, 96)
