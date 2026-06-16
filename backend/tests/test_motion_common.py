from __future__ import annotations

import pytest
from PIL import Image

from app.services.generation.modules.common import frames_to_animation


def _frames(count=3, size=(64, 64)):
    return [Image.new("RGB", size, color=(index * 60, 100, 180)) for index in range(count)]


def test_frames_to_animation_gif():
    result = frames_to_animation(_frames(), fps=12, output_format="gif")
    assert result.startswith(b"GIF")


def test_frames_to_animation_webp():
    result = frames_to_animation(_frames(), fps=12, output_format="webp")
    assert result.startswith(b"RIFF")


def test_frames_to_animation_rejects_empty_frames():
    with pytest.raises(ValueError, match="empty"):
        frames_to_animation([], fps=12, output_format="gif")


def test_frames_to_animation_rejects_invalid_fps():
    with pytest.raises(ValueError, match="fps"):
        frames_to_animation(_frames(), fps=0, output_format="gif")
