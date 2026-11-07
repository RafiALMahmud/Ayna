import io

import pytest
from PIL import Image, ImageDraw

from app.modules.quality.opencv_alignment import align_with_opencv

cv2 = pytest.importorskip("cv2", reason="OpenCV is an isolated optional dependency")
np = pytest.importorskip("numpy", reason="OpenCV requires NumPy")


def detailed_fixture() -> bytes:
    image = Image.new("RGB", (256, 256), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((28, 25, 228, 231), radius=25, fill="#315f9b", outline="black", width=4)
    for index in range(8):
        x = 45 + (index % 4) * 48
        y = 55 + (index // 4) * 105
        draw.rectangle((x, y, x + 20, y + 20), fill=(220, 60 + index * 12, 40))
        draw.line((x, 100, x + 28, 130), fill="white", width=3)
    draw.text((84, 110), "AYNA", fill="white", stroke_fill="black", stroke_width=1)
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def warped_fixture(data: bytes) -> bytes:
    source = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    points = np.float32([[0, 0], [255, 0], [255, 255], [0, 255]])
    target = np.float32([[10, 7], [247, 13], [251, 245], [5, 250]])
    matrix = cv2.getPerspectiveTransform(points, target)
    warped = cv2.warpPerspective(source, matrix, (256, 256), borderValue=(255, 255, 255))
    ok, encoded = cv2.imencode(".png", warped)
    assert ok
    return encoded.tobytes()


def test_opencv_accepts_feature_supported_alignment_and_emits_diagnostics():
    reference = detailed_fixture()
    result = align_with_opencv(reference, warped_fixture(reference), 256)
    assert result.accepted is True
    assert result.aligned_render is not None
    assert result.diagnostics["inliers"] >= 8
    assert result.diagnostics["inlier_ratio"] >= 0.5
    assert "opencv_silhouette_iou" in result.metrics
    assert len(result.metrics["localized_detail_regions"]) <= 3


def test_opencv_rejects_images_without_correspondence():
    blank = io.BytesIO()
    Image.new("RGB", (256, 256), "white").save(blank, "PNG")
    result = align_with_opencv(detailed_fixture(), blank.getvalue(), 256)
    assert result.accepted is False
    assert result.aligned_render is None
    assert result.metrics == {}
