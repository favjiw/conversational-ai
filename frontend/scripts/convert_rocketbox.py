"""Convert a Microsoft Rocketbox avatar (FBX, MIT license) into a /stage GLB.

The *_facial.fbx variant carries the ARKit blendshapes (named AK_NN_Xxx) and
the 15 Oculus visemes (AA_VI_NN_Xx). This script:
  - renames them to the exact ARKit names (jawOpen, ...) and to Oculus
    viseme names (viseme_sil, viseme_PP, ...), and drops every other shape key
    (FACS action units, Headbox extras) to keep the file small;
  - rebuilds the body/head/opacity materials as PBR from the color, normal and
    opacity textures, downscaled to keep GPU memory low on laptops;
  - exports a GLB in metres, Y-up, with skin and morph targets.

Usage (Blender headless):
    blender --background --factory-startup --python frontend/scripts/convert_rocketbox.py -- \\
        <avatar.fbx> <texture_dir> <texture_prefix e.g. m011> <out.glb> [texture_size]
"""

import os
import re
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
FBX, TEX_DIR, PREFIX, OUT = args[:4]
TEX_SIZE = int(args[4]) if len(args) > 4 else 1024

# Rocketbox AA_VI order matches the Oculus/OVR viseme set.
VISEMES = ["sil", "PP", "FF", "TH", "DD", "kk", "CH", "SS", "nn", "RR", "aa", "E", "I", "O", "U"]
ROUGHNESS = {"body": 0.8, "head": 0.55, "opacity": 0.7}


def rename_shape_keys(mesh_obj):
    keys = mesh_obj.data.shape_keys.key_blocks
    kept = {"arkit": 0, "viseme": 0}
    for key in list(keys):
        if key.name == "Basis":
            continue
        m = re.match(r"AK_\d+_(\w+)$", key.name)
        if m:
            name = m.group(1)
            key.name = name[0].lower() + name[1:]
            kept["arkit"] += 1
            continue
        m = re.match(r"AA_VI_(\d+)_\w+$", key.name)
        if m:
            key.name = f"viseme_{VISEMES[int(m.group(1))]}"
            kept["viseme"] += 1
            continue
        mesh_obj.shape_key_remove(key)
    return kept


def load_image(kind, non_color=False):
    path = os.path.join(TEX_DIR, f"{PREFIX}_{kind}.tga")
    img = bpy.data.images.load(path)
    if img.size[0] > TEX_SIZE:
        img.scale(TEX_SIZE, TEX_SIZE)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    return img


def build_material(mat, part):
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = ROUGHNESS[part]

    color = nodes.new("ShaderNodeTexImage")
    color.image = load_image(f"{part}_color" if part != "opacity" else "opacity_color")
    links.new(color.outputs["Color"], bsdf.inputs["Base Color"])

    if part == "opacity":
        # Hair cards and eyelashes: alpha from the texture (cut out in three.js)
        links.new(color.outputs["Alpha"], bsdf.inputs["Alpha"])
        return

    normal_tex = nodes.new("ShaderNodeTexImage")
    normal_tex.image = load_image(f"{part}_normal", non_color=True)
    normal_map = nodes.new("ShaderNodeNormalMap")
    links.new(normal_tex.outputs["Color"], normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=FBX)

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.data.shape_keys]
    if not meshes:
        raise SystemExit("No mesh with shape keys found (use the *_facial.fbx file)")
    for ob in meshes:
        print(f"{ob.name}: kept {rename_shape_keys(ob)}")

    for mat in bpy.data.materials:
        part = next((p for p in ("body", "head", "opacity") if mat.name.endswith(f"_{p}")), None)
        if part:
            build_material(mat, part)

    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=OUT,
        export_format="GLB",
        export_image_format="WEBP",
        export_morph=True,
        export_morph_normal=True,
        export_skins=True,
        export_animations=False,
        export_yup=True,
    )
    print(f"Wrote {OUT} ({os.path.getsize(OUT) / 1e6:.1f} MB)")


main()
