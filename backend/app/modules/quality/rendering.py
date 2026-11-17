"""Deterministic CPU-only GLB inspection renderer.

This is deliberately a small software rasterizer, not a photorealistic renderer. It supports
embedded GLB 2.0 triangle meshes, node transforms, material base colors and embedded base-color
textures. Skins, animations, morph targets and compressed mesh extensions are not evaluated.
The output is useful only as a consistently labelled input to Ayna's advisory checks.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import struct
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from PIL import Image

RENDER_VIEWS = ("front", "left", "right", "back")
_JSON_CHUNK = 0x4E4F534A
_BIN_CHUNK = 0x004E4942
_COMPONENTS = {
    5120: ("b", 1),
    5121: ("B", 1),
    5122: ("h", 2),
    5123: ("H", 2),
    5125: ("I", 4),
    5126: ("f", 4),
}
_TYPE_WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
_MAX_GLB_BYTES = 32 * 1024 * 1024
_MAX_ACCESSOR_ELEMENTS = 100_000
_MAX_NODE_DEPTH = 256
_MAX_PIXEL_WORK_PER_VIEW = 5_000_000
_CAMERAS = {
    "front": (0.0, 0.0, 1.0),
    "left": (-1.0, 0.0, 0.0),
    "right": (1.0, 0.0, 0.0),
    "back": (0.0, 0.0, -1.0),
}


class GlbRenderError(ValueError):
    """The GLB cannot be safely parsed or rendered by the CPU baseline."""


class ViewRenderError(RuntimeError):
    """One deterministic camera view could not be rendered."""


@dataclass(frozen=True)
class Triangle:
    points: tuple[tuple[float, float, float], ...]
    color: tuple[int, int, int]


@dataclass(frozen=True)
class RenderMesh:
    triangles: tuple[Triangle, ...]
    center: tuple[float, float, float]
    radius: float


@dataclass(frozen=True)
class RenderBatch:
    images: dict[str, bytes]
    metadata: dict
    failures: dict[str, str]


ViewRenderer = Callable[[RenderMesh, str, int], bytes]
BatchRenderer = Callable[[bytes, int], RenderBatch]


def _identity() -> tuple[float, ...]:
    return (
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
    )


def _matrix_multiply(left: tuple[float, ...], right: tuple[float, ...]) -> tuple[float, ...]:
    # glTF matrices are column-major.
    return tuple(
        sum(left[k * 4 + row] * right[column * 4 + k] for k in range(4))
        for column in range(4)
        for row in range(4)
    )


def _node_matrix(node: dict) -> tuple[float, ...]:
    if "matrix" in node:
        matrix = tuple(float(value) for value in node["matrix"])
        if len(matrix) != 16 or not all(math.isfinite(value) for value in matrix):
            raise GlbRenderError("A node contains an invalid transformation matrix")
        return matrix

    translation = tuple(float(value) for value in node.get("translation", (0, 0, 0)))
    rotation = tuple(float(value) for value in node.get("rotation", (0, 0, 0, 1)))
    scale = tuple(float(value) for value in node.get("scale", (1, 1, 1)))
    if len(translation) != 3 or len(rotation) != 4 or len(scale) != 3:
        raise GlbRenderError("A node contains an invalid TRS transform")
    if not all(math.isfinite(value) for value in (*translation, *rotation, *scale)):
        raise GlbRenderError("A node transform contains a non-finite value")

    x, y, z, w = rotation
    length = math.sqrt(x * x + y * y + z * z + w * w)
    if length == 0:
        raise GlbRenderError("A node contains an empty rotation quaternion")
    x, y, z, w = x / length, y / length, z / length, w / length
    sx, sy, sz = scale
    tx, ty, tz = translation
    return (
        (1 - 2 * (y * y + z * z)) * sx,
        (2 * (x * y + z * w)) * sx,
        (2 * (x * z - y * w)) * sx,
        0.0,
        (2 * (x * y - z * w)) * sy,
        (1 - 2 * (x * x + z * z)) * sy,
        (2 * (y * z + x * w)) * sy,
        0.0,
        (2 * (x * z + y * w)) * sz,
        (2 * (y * z - x * w)) * sz,
        (1 - 2 * (x * x + y * y)) * sz,
        0.0,
        tx,
        ty,
        tz,
        1.0,
    )


def _transform(point: tuple[float, float, float], matrix: tuple[float, ...]):
    x, y, z = point
    result = (
        matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12],
        matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13],
        matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14],
    )
    if not all(math.isfinite(value) for value in result):
        raise GlbRenderError("A transformed vertex is not finite")
    return result


def _parse_glb(data: bytes) -> tuple[dict, bytes]:
    if len(data) > _MAX_GLB_BYTES:
        raise GlbRenderError("GLB exceeds the 32 MiB CPU-rendering limit")
    if len(data) < 20:
        raise GlbRenderError("GLB data is truncated")
    magic, version, declared_length = struct.unpack_from("<III", data)
    if magic != 0x46546C67 or version != 2:
        raise GlbRenderError("Only GLB 2.0 files are supported")
    if declared_length != len(data):
        raise GlbRenderError("GLB length does not match its header")

    offset = 12
    document: dict | None = None
    binary: bytes | None = None
    while offset < len(data):
        if offset + 8 > len(data):
            raise GlbRenderError("GLB chunk header is truncated")
        length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        end = offset + length
        if end > len(data):
            raise GlbRenderError("GLB chunk exceeds the declared file length")
        payload = data[offset:end]
        offset = end
        if chunk_type == _JSON_CHUNK and document is None:
            try:
                document = json.loads(payload.rstrip(b" \t\r\n\0").decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise GlbRenderError("GLB JSON is invalid") from exc
        elif chunk_type == _BIN_CHUNK and binary is None:
            binary = payload
    if not isinstance(document, dict) or binary is None:
        raise GlbRenderError("GLB must contain JSON and embedded binary chunks")
    return document, binary


def _accessor(document: dict, binary: bytes, index: int) -> list[tuple[float | int, ...]]:
    try:
        accessor = document["accessors"][index]
        view = document["bufferViews"][accessor["bufferView"]]
        component_type = int(accessor["componentType"])
        value_type = accessor["type"]
        count = int(accessor["count"])
        fmt, component_size = _COMPONENTS[component_type]
        width = _TYPE_WIDTH[value_type]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise GlbRenderError("GLB accessor metadata is invalid") from exc
    if view.get("buffer", 0) != 0 or count < 0:
        raise GlbRenderError("Only the embedded GLB buffer is supported")
    if count > _MAX_ACCESSOR_ELEMENTS:
        raise GlbRenderError("GLB accessor exceeds the 100,000-element CPU limit")
    element_size = component_size * width
    stride = int(view.get("byteStride", element_size))
    if stride < element_size:
        raise GlbRenderError("GLB accessor stride is smaller than its element")
    start = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    if start < 0:
        raise GlbRenderError("GLB accessor offset is invalid")

    values: list[tuple[float | int, ...]] = []
    unpack = struct.Struct("<" + fmt * width)
    for item in range(count):
        offset = start + item * stride
        if offset + element_size > len(binary):
            raise GlbRenderError("GLB accessor exceeds its binary buffer")
        values.append(unpack.unpack_from(binary, offset))
    return values


def _material_color(document: dict, primitive: dict) -> tuple[int, int, int]:
    try:
        material = document.get("materials", [])[primitive.get("material", -1)]
        factor = material.get("pbrMetallicRoughness", {}).get("baseColorFactor", [0.65] * 3)
        if len(factor) < 3:
            raise ValueError
        channels = [max(0, min(255, round(float(value) * 255))) for value in factor[:3]]
        return channels[0], channels[1], channels[2]
    except (IndexError, KeyError, TypeError, ValueError):
        return (166, 166, 166)


def _embedded_texture(document: dict, binary: bytes, primitive: dict) -> Image.Image | None:
    """Load an embedded base-color texture; external URIs stay explicitly unsupported."""
    material_index = primitive.get("material")
    if material_index is None:
        return None
    try:
        material = document.get("materials", [])[material_index]
        texture_info = material.get("pbrMetallicRoughness", {}).get("baseColorTexture")
        if texture_info is None:
            return None
        texture_index = texture_info["index"]
        image_index = document["textures"][texture_index]["source"]
        image = document["images"][image_index]
        if "bufferView" not in image:
            raise GlbRenderError("External texture URIs are not supported for inspection")
        view = document["bufferViews"][image["bufferView"]]
        if view.get("buffer", 0) != 0:
            raise GlbRenderError("Texture references a non-embedded buffer")
        start = int(view.get("byteOffset", 0))
        end = start + int(view["byteLength"])
        if start < 0 or end > len(binary):
            raise GlbRenderError("Embedded texture exceeds its binary buffer")
        with Image.open(io.BytesIO(binary[start:end])) as decoded:
            return decoded.convert("RGB")
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, GlbRenderError):
            raise
        raise GlbRenderError("Embedded base-color texture metadata is invalid") from exc


def _texture_color(texture: Image.Image, uv: tuple[float, float]) -> tuple[int, int, int]:
    u, v = uv[0] % 1.0, uv[1] % 1.0
    x = min(texture.width - 1, max(0, round(u * (texture.width - 1))))
    y = min(texture.height - 1, max(0, round((1.0 - v) * (texture.height - 1))))
    pixel = texture.getpixel((x, y))
    return int(pixel[0]), int(pixel[1]), int(pixel[2])


def _mesh_instances(document: dict) -> Iterable[tuple[int, tuple[float, ...]]]:
    nodes = document.get("nodes", [])
    scenes = document.get("scenes", [])
    if scenes:
        scene_index = int(document.get("scene", 0))
        try:
            roots = scenes[scene_index].get("nodes", [])
        except (IndexError, TypeError) as exc:
            raise GlbRenderError("GLB scene metadata is invalid") from exc
    else:
        child_nodes = {child for node in nodes for child in node.get("children", [])}
        roots = [index for index in range(len(nodes)) if index not in child_nodes]

    def visit(index: int, parent: tuple[float, ...], path: frozenset[int]):
        if index in path:
            raise GlbRenderError("GLB node graph contains a cycle")
        if len(path) >= _MAX_NODE_DEPTH:
            raise GlbRenderError("GLB node graph exceeds the CPU-safe depth limit")
        try:
            node = nodes[index]
        except (IndexError, TypeError) as exc:
            raise GlbRenderError("GLB node index is invalid") from exc
        world = _matrix_multiply(parent, _node_matrix(node))
        if "mesh" in node:
            yield int(node["mesh"]), world
        for child in node.get("children", []):
            yield from visit(int(child), world, path | {index})

    for root in roots:
        yield from visit(int(root), _identity(), frozenset())


def load_render_mesh(data: bytes, max_triangles: int = 20_000) -> RenderMesh:
    """Parse supported GLB triangles and normalize their shared inspection bounds."""
    document, binary = _parse_glb(data)
    meshes = document.get("meshes", [])
    triangles: list[Triangle] = []
    points: list[tuple[float, float, float]] = []
    for mesh_index, matrix in _mesh_instances(document):
        try:
            primitives = meshes[mesh_index]["primitives"]
        except (IndexError, KeyError, TypeError) as exc:
            raise GlbRenderError("GLB mesh metadata is invalid") from exc
        for primitive in primitives:
            if primitive.get("mode", 4) != 4:
                continue
            if primitive.get("extensions"):
                raise GlbRenderError("Compressed or extended mesh primitives are not supported")
            try:
                position_index = primitive["attributes"]["POSITION"]
            except (KeyError, TypeError) as exc:
                raise GlbRenderError("A triangle primitive has no POSITION accessor") from exc
            raw_positions = _accessor(document, binary, int(position_index))
            if any(len(position) != 3 for position in raw_positions):
                raise GlbRenderError("POSITION accessors must contain VEC3 values")
            positions = [
                _transform((float(position[0]), float(position[1]), float(position[2])), matrix)
                for position in raw_positions
            ]
            if "indices" in primitive:
                raw_indices = _accessor(document, binary, int(primitive["indices"]))
                indices = [int(value[0]) for value in raw_indices]
            else:
                indices = list(range(len(positions)))
            if len(indices) % 3:
                raise GlbRenderError("Triangle index count must be divisible by three")
            color = _material_color(document, primitive)
            texture = _embedded_texture(document, binary, primitive)
            texcoords = None
            vertex_colors = None
            if texture is not None:
                texture_accessor = primitive.get("attributes", {}).get("TEXCOORD_0")
                if texture_accessor is None:
                    raise GlbRenderError("A base-color texture has no TEXCOORD_0 accessor")
                texcoords = _accessor(document, binary, int(texture_accessor))
                if len(texcoords) != len(positions) or any(len(uv) != 2 for uv in texcoords):
                    raise GlbRenderError("Texture coordinates do not match mesh positions")
            color_accessor = primitive.get("attributes", {}).get("COLOR_0")
            if color_accessor is not None:
                vertex_colors = _accessor(document, binary, int(color_accessor))
                if len(vertex_colors) != len(positions) or any(
                    len(value) not in {3, 4} for value in vertex_colors
                ):
                    raise GlbRenderError("Vertex colors do not match mesh positions")
            for offset in range(0, len(indices), 3):
                try:
                    triangle_points = tuple(
                        positions[index] for index in indices[offset : offset + 3]
                    )
                except IndexError as exc:
                    raise GlbRenderError("Triangle index is outside the POSITION accessor") from exc
                if len(set(triangle_points)) < 3:
                    continue
                triangle_color = color
                if texture is not None and texcoords is not None:
                    uv_points = [texcoords[index] for index in indices[offset : offset + 3]]
                    sampled = _texture_color(
                        texture,
                        (
                            sum(float(uv[0]) for uv in uv_points) / 3,
                            sum(float(uv[1]) for uv in uv_points) / 3,
                        ),
                    )
                    triangle_color = (
                        round(sampled[0] * color[0] / 255),
                        round(sampled[1] * color[1] / 255),
                        round(sampled[2] * color[2] / 255),
                    )
                elif vertex_colors is not None:
                    color_points = [vertex_colors[index] for index in indices[offset : offset + 3]]
                    channels = [
                        sum(float(value[channel]) for value in color_points) / 3
                        for channel in range(3)
                    ]
                    scale = 255 if max(channels) <= 1.0 else 1
                    triangle_color = (
                        max(0, min(255, round(channels[0] * scale))),
                        max(0, min(255, round(channels[1] * scale))),
                        max(0, min(255, round(channels[2] * scale))),
                    )
                triangles.append(Triangle(triangle_points, triangle_color))
                points.extend(triangle_points)
                if len(triangles) > max_triangles:
                    raise GlbRenderError(f"GLB exceeds the {max_triangles:,} triangle CPU limit")
    if not triangles or not points:
        raise GlbRenderError("GLB contains no supported triangle geometry")
    mins = tuple(min(point[axis] for point in points) for axis in range(3))
    maxs = tuple(max(point[axis] for point in points) for axis in range(3))
    center = (
        (mins[0] + maxs[0]) / 2,
        (mins[1] + maxs[1]) / 2,
        (mins[2] + maxs[2]) / 2,
    )
    radius = max((high - low) / 2 for low, high in zip(mins, maxs, strict=True))
    if not math.isfinite(radius) or radius <= 1e-9:
        raise GlbRenderError("GLB geometry has empty bounds")
    return RenderMesh(tuple(triangles), center, radius)


def _project(point: tuple[float, float, float], view: str) -> tuple[float, float, float]:
    x, y, z = point
    if view == "front":
        return x, y, z
    if view == "back":
        return -x, y, -z
    if view == "left":
        return z, y, -x
    if view == "right":
        return -z, y, x
    raise ViewRenderError(f"Unknown deterministic camera view: {view}")


def _edge(a: tuple[float, float], b: tuple[float, float], p: tuple[float, float]) -> float:
    return (p[0] - a[0]) * (b[1] - a[1]) - (p[1] - a[1]) * (b[0] - a[0])


def _shade(triangle: Triangle, camera: tuple[float, float, float]) -> tuple[int, int, int]:
    a, b, c = triangle.points
    ab = tuple(b[i] - a[i] for i in range(3))
    ac = tuple(c[i] - a[i] for i in range(3))
    normal = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    length = math.sqrt(sum(value * value for value in normal)) or 1.0
    facing = abs(sum(normal[i] / length * camera[i] for i in range(3)))
    light = 0.68 + 0.32 * facing
    return (
        round(triangle.color[0] * light),
        round(triangle.color[1] * light),
        round(triangle.color[2] * light),
    )


def render_view_png(mesh: RenderMesh, view: str, image_size: int) -> bytes:
    """Rasterize one labelled orthographic view to a white-background PNG."""
    if view not in _CAMERAS:
        raise ViewRenderError(f"Unsupported render view: {view}")
    if not 64 <= image_size <= 1024:
        raise ViewRenderError("Render image size must be between 64 and 1024 pixels")
    image = Image.new("RGB", (image_size, image_size), (255, 255, 255))
    pixels = image.load()
    depth = [-math.inf] * (image_size * image_size)
    padding = max(4, round(image_size * 0.08))
    scale = (image_size - 2 * padding) / (2 * mesh.radius)
    cx, cy, cz = mesh.center
    pixel_work = 0

    for triangle in mesh.triangles:
        projected = []
        for point in triangle.points:
            local = (point[0] - cx, point[1] - cy, point[2] - cz)
            x, y, z = _project(local, view)
            projected.append((image_size / 2 + x * scale, image_size / 2 - y * scale, z))
        p0, p1, p2 = projected
        area = _edge(p0[:2], p1[:2], p2[:2])
        if abs(area) < 1e-8:
            continue
        min_x = max(0, math.floor(min(p0[0], p1[0], p2[0])))
        max_x = min(image_size - 1, math.ceil(max(p0[0], p1[0], p2[0])))
        min_y = max(0, math.floor(min(p0[1], p1[1], p2[1])))
        max_y = min(image_size - 1, math.ceil(max(p0[1], p1[1], p2[1])))
        pixel_work += (max_x - min_x + 1) * (max_y - min_y + 1)
        if pixel_work > _MAX_PIXEL_WORK_PER_VIEW:
            raise ViewRenderError(f"The {view} view exceeds the CPU raster-work limit")
        color = _shade(triangle, _CAMERAS[view])
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                sample = (x + 0.5, y + 0.5)
                w0 = _edge(p1[:2], p2[:2], sample) / area
                w1 = _edge(p2[:2], p0[:2], sample) / area
                w2 = 1.0 - w0 - w1
                if min(w0, w1, w2) < -1e-7:
                    continue
                z = w0 * p0[2] + w1 * p1[2] + w2 * p2[2]
                index = y * image_size + x
                if z > depth[index]:
                    depth[index] = z
                    pixels[x, y] = color
    if all(value == -math.inf for value in depth):
        raise ViewRenderError(f"The {view} camera produced no visible triangles")
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def render_glb_views(
    data: bytes,
    image_size: int = 384,
    *,
    views: tuple[str, ...] = RENDER_VIEWS,
    max_triangles: int = 20_000,
    view_renderer: ViewRenderer = render_view_png,
) -> RenderBatch:
    """Render deterministic labelled views while isolating individual camera failures."""
    mesh = load_render_mesh(data, max_triangles=max_triangles)
    images: dict[str, bytes] = {}
    failures: dict[str, str] = {}
    view_metadata: dict[str, dict] = {}
    for view in views:
        if view not in _CAMERAS:
            failures[view] = "unsupported camera label"
            continue
        try:
            images[view] = view_renderer(mesh, view, image_size)
            view_metadata[view] = {
                "camera_position": list(_CAMERAS[view]),
                "target": [0.0, 0.0, 0.0],
                "projection": "orthographic",
                "media_type": "image/png",
            }
        except Exception as exc:
            failures[view] = str(exc) or exc.__class__.__name__
    if not images:
        details = "; ".join(f"{view}: {message}" for view, message in failures.items())
        raise GlbRenderError(f"No deterministic GLB views could be rendered ({details})")
    metadata = {
        "status": "partial" if failures else "complete",
        "renderer": "ayna-cpu-raster-v2",
        "deterministic": True,
        "image_size": image_size,
        "triangle_count": len(mesh.triangles),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "views": view_metadata,
        "failed_views": failures,
        "limitations": [
            "embedded base-color textures are sampled once per triangle for inspection",
            "vertex colors are averaged once per triangle for inspection",
            "metallic/roughness maps, skins, animation and compressed meshes are not evaluated",
        ],
    }
    return RenderBatch(images=images, metadata=metadata, failures=failures)
