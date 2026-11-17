"""Blender-side GLB decimation entry point; invoked only by the isolated worker adapter."""

import sys
from pathlib import Path

import bpy


def main() -> None:
    source, output, target_raw = sys.argv[sys.argv.index("--") + 1 :]
    target = int(target_raw)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(Path(source).resolve()))
    meshes = [item for item in bpy.context.scene.objects if item.type == "MESH"]
    total = sum(len(item.data.polygons) for item in meshes)
    if total > target:
        ratio = max(0.02, target / total)
        for item in meshes:
            if len(item.data.polygons) < 20:
                continue
            modifier = item.modifiers.new(name="Ayna bounded decimation", type="DECIMATE")
            modifier.ratio = ratio
            modifier.use_collapse_triangulate = True
            bpy.context.view_layer.objects.active = item
            item.select_set(True)
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            item.select_set(False)
    bpy.ops.export_scene.gltf(
        filepath=str(Path(output).resolve()),
        export_format="GLB",
        export_yup=True,
        export_materials="EXPORT",
        export_texcoords=True,
        export_normals=True,
        export_apply=False,
    )


if __name__ == "__main__":
    main()
