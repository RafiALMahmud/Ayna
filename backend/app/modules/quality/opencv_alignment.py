"""Optional OpenCV alignment and interpretable post-alignment appearance diagnostics."""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps


@dataclass(frozen=True)
class AlignmentResult:
    accepted: bool
    aligned_render: bytes | None
    diagnostics: dict
    metrics: dict


def _square_rgb(data: bytes, size: int):
    import cv2
    import numpy as np

    with Image.open(io.BytesIO(data)) as source:
        image = ImageOps.fit(source.convert("RGB"), (size, size))
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def _foreground(image):
    import cv2
    import numpy as np

    border = np.concatenate((image[0], image[-1], image[:, 0], image[:, -1]), axis=0)
    background = np.median(border.astype(np.float32), axis=0)
    distance = np.max(np.abs(image.astype(np.float32) - background), axis=2)
    mask = (distance >= 24).astype("uint8") * 255
    kernel = np.ones((3, 3), dtype="uint8")
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)


def _appearance_metrics(reference, aligned):
    import cv2
    import numpy as np

    reference_mask = _foreground(reference)
    aligned_mask = _foreground(aligned)
    intersection = (reference_mask > 0) & (aligned_mask > 0)
    union = (reference_mask > 0) | (aligned_mask > 0)
    if int(intersection.sum()) < 256 or int(union.sum()) == 0:
        return {}

    silhouette = float(intersection.sum() / union.sum())
    reference_lab = cv2.cvtColor(reference, cv2.COLOR_BGR2LAB).astype(np.float32)
    aligned_lab = cv2.cvtColor(aligned, cv2.COLOR_BGR2LAB).astype(np.float32)
    # Normalize only luminance so color/texture checks are less sensitive to global lighting.
    ref_l = reference_lab[:, :, 0][intersection]
    aligned_l = aligned_lab[:, :, 0][intersection]
    aligned_std = max(float(aligned_l.std()), 1.0)
    normalized_l = (aligned_lab[:, :, 0] - float(aligned_l.mean())) * (
        max(float(ref_l.std()), 1.0) / aligned_std
    ) + float(ref_l.mean())
    aligned_lab[:, :, 0] = np.clip(normalized_l, 0, 255)
    normalized = cv2.cvtColor(aligned_lab.astype("uint8"), cv2.COLOR_LAB2BGR)

    chroma = np.abs(reference_lab[:, :, 1:3] - aligned_lab[:, :, 1:3])
    chroma_distance = float(chroma[intersection].mean() / 255)
    ref_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    aligned_gray = cv2.cvtColor(normalized, cv2.COLOR_BGR2GRAY)
    ref_gradient = cv2.magnitude(
        cv2.Sobel(ref_gray, cv2.CV_32F, 1, 0),
        cv2.Sobel(ref_gray, cv2.CV_32F, 0, 1),
    )
    aligned_gradient = cv2.magnitude(
        cv2.Sobel(aligned_gray, cv2.CV_32F, 1, 0),
        cv2.Sobel(aligned_gray, cv2.CV_32F, 0, 1),
    )
    texture_difference = float(np.abs(ref_gradient - aligned_gradient)[intersection].mean() / 255)
    pixel_difference = np.abs(reference.astype(np.float32) - normalized.astype(np.float32)).mean(2)
    names = (
        ("top_left", 0, 0),
        ("top", 0, 1),
        ("top_right", 0, 2),
        ("middle_left", 1, 0),
        ("center", 1, 1),
        ("middle_right", 1, 2),
        ("bottom_left", 2, 0),
        ("bottom", 2, 1),
        ("bottom_right", 2, 2),
    )
    regions: list[dict[str, str | float]] = []
    height, width = reference.shape[:2]
    for name, row, column in names:
        y0, y1 = row * height // 3, (row + 1) * height // 3
        x0, x1 = column * width // 3, (column + 1) * width // 3
        local_mask = intersection[y0:y1, x0:x1]
        if int(local_mask.sum()) >= 32:
            difference = float(pixel_difference[y0:y1, x0:x1][local_mask].mean() / 255)
            regions.append({"region": name, "difference": round(difference, 4)})
    regions.sort(key=lambda item: float(item["difference"]), reverse=True)
    return {
        "opencv_silhouette_iou": round(silhouette, 4),
        "opencv_lighting_normalized_chroma_distance": round(chroma_distance, 4),
        "opencv_texture_gradient_difference": round(texture_difference, 4),
        "localized_detail_regions": regions[:3],
    }


def align_with_opencv(reference: bytes, render: bytes, size: int) -> AlignmentResult:
    """Accept alignment only after bounded ORB correspondence and RANSAC geometry checks."""
    import cv2
    import numpy as np

    size = max(128, min(size, 512))
    reference_image = _square_rgb(reference, size)
    render_image = _square_rgb(render, size)
    reference_gray = cv2.cvtColor(reference_image, cv2.COLOR_BGR2GRAY)
    render_gray = cv2.cvtColor(render_image, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=800, edgeThreshold=15, fastThreshold=10)
    reference_points, reference_descriptors = orb.detectAndCompute(reference_gray, None)
    render_points, render_descriptors = orb.detectAndCompute(render_gray, None)
    diagnostics = {
        "method": "opencv-orb-ransac-v1",
        "reference_keypoints": len(reference_points),
        "render_keypoints": len(render_points),
        "accepted": False,
    }
    if reference_descriptors is None or render_descriptors is None:
        diagnostics["reason"] = "insufficient_descriptors"
        return AlignmentResult(False, None, diagnostics, {})
    matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(
        render_descriptors, reference_descriptors, k=2
    )
    good = [first for first, second in matches if first.distance < 0.75 * second.distance]
    diagnostics["good_matches"] = len(good)
    if len(good) < 12:
        diagnostics["reason"] = "insufficient_correspondence"
        return AlignmentResult(False, None, diagnostics, {})
    source = np.float32([render_points[item.queryIdx].pt for item in good]).reshape(-1, 1, 2)
    target = np.float32([reference_points[item.trainIdx].pt for item in good]).reshape(-1, 1, 2)
    homography, inlier_mask = cv2.findHomography(source, target, cv2.RANSAC, 3.0)
    if homography is None or inlier_mask is None or not np.isfinite(homography).all():
        diagnostics["reason"] = "homography_unavailable"
        return AlignmentResult(False, None, diagnostics, {})
    inliers = int(inlier_mask.sum())
    ratio = inliers / len(good)
    corners = np.float32([[[0, 0], [size, 0], [size, size], [0, size]]])
    projected = cv2.perspectiveTransform(corners, homography)[0]
    area_ratio = abs(float(cv2.contourArea(projected))) / (size * size)
    diagnostics.update(
        {"inliers": inliers, "inlier_ratio": round(ratio, 4), "area_ratio": round(area_ratio, 4)}
    )
    if inliers < 8 or ratio < 0.5 or not 0.35 <= area_ratio <= 2.8:
        diagnostics["reason"] = "ambiguous_camera_alignment"
        return AlignmentResult(False, None, diagnostics, {})
    aligned = cv2.warpPerspective(
        render_image,
        homography,
        (size, size),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )
    ok, encoded = cv2.imencode(".png", aligned)
    if not ok:
        diagnostics["reason"] = "aligned_image_encode_failed"
        return AlignmentResult(False, None, diagnostics, {})
    diagnostics["accepted"] = True
    diagnostics["reason"] = "sufficient_feature_geometry"
    return AlignmentResult(
        True,
        encoded.tobytes(),
        diagnostics,
        _appearance_metrics(reference_image, aligned),
    )
