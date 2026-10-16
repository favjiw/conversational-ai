"""Generate a tiny ARKit-52 test character for the /stage GLB pipeline.

Not a real presenter: a sphere head on a cylinder body whose 52 shape keys are
named exactly like ARKit and each deform a matching region, so FaceDriver,
the name validation and the debug sliders can be tested without any licensed
asset. Run with Blender (headless):

    blender --background --python frontend/scripts/make_arkit_test_head.py

Writes frontend/public/models/test/arkit-test-head.glb
"""

import math
import os

import bpy
from mathutils import Vector

ARKIT = [
    "browInnerUp", "browDownLeft", "browDownRight", "browOuterUpLeft", "browOuterUpRight",
    "eyeLookUpLeft", "eyeLookUpRight", "eyeLookDownLeft", "eyeLookDownRight",
    "eyeLookInLeft", "eyeLookInRight", "eyeLookOutLeft", "eyeLookOutRight",
    "eyeBlinkLeft", "eyeBlinkRight", "eyeSquintLeft", "eyeSquintRight", "eyeWideLeft", "eyeWideRight",
    "cheekPuff", "cheekSquintLeft", "cheekSquintRight", "noseSneerLeft", "noseSneerRight",
    "jawOpen", "jawForward", "jawLeft", "jawRight",
    "mouthFunnel", "mouthPucker", "mouthLeft", "mouthRight",
    "mouthRollUpper", "mouthRollLower", "mouthShrugUpper", "mouthShrugLower", "mouthClose",
    "mouthSmileLeft", "mouthSmileRight", "mouthFrownLeft", "mouthFrownRight",
    "mouthDimpleLeft", "mouthDimpleRight", "mouthUpperUpLeft", "mouthUpperUpRight",
    "mouthLowerDownLeft", "mouthLowerDownRight", "mouthPressLeft", "mouthPressRight",
    "mouthStretchLeft", "mouthStretchRight",
    "tongueOut",
]

HEAD_RADIUS = 0.11
HEAD_Y = 1.55

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "models", "test", "arkit-test-head.glb")


def region(name):
    """(center in head-local space, radius, displacement) for a blendshape name."""
    side = 1.0 if name.endswith("Left") else -1.0 if name.endswith("Right") else 0.0
    r = HEAD_RADIUS
    front = r * 0.95
    # Authored facing +Y; main() mirrors Y so the face ends up at Blender -Y,
    # which the glTF exporter turns into +Z (toward the stage camera). Left is +X.
    if name.startswith("brow"):
        up = -1.0 if "Down" in name else 1.0
        return Vector((side * r * 0.35, front, r * 0.45)), r * 0.35, Vector((0, 0, up * r * 0.12))
    if name.startswith("eye"):
        c = Vector((side * r * 0.38, front, r * 0.18))
        if "Blink" in name or "Squint" in name:
            return c, r * 0.22, Vector((0, -r * 0.05, -r * 0.08))
        if "Wide" in name:
            return c, r * 0.22, Vector((0, 0, r * 0.08))
        d = {"Up": (0, 0, 1), "Down": (0, 0, -1), "In": (-side, 0, 0), "Out": (side, 0, 0)}
        key = next(k for k in d if f"Look{k}" in name)
        return c, r * 0.18, Vector(d[key]) * r * 0.06
    if name.startswith("cheek"):
        return Vector((side * r * 0.6 or r * 0.6, front * 0.8, -r * 0.1)), r * 0.35, Vector((side or 1, r * 0.4, 0)).normalized() * r * 0.1
    if name.startswith("nose"):
        return Vector((side * r * 0.15, front, 0)), r * 0.2, Vector((0, 0, r * 0.08))
    if name.startswith("jaw"):
        c = Vector((0, front * 0.7, -r * 0.6))
        move = {"jawOpen": (0, 0, -1), "jawForward": (0, 1, 0), "jawLeft": (1, 0, 0), "jawRight": (-1, 0, 0)}[name]
        return c, r * 0.6, Vector(move) * r * 0.25
    if name == "tongueOut":
        return Vector((0, front, -r * 0.4)), r * 0.2, Vector((0, r * 0.3, 0))
    # mouth*
    c = Vector((side * r * 0.3, front, -r * 0.35))
    move = Vector((side * r * 0.12, 0, r * 0.06)) if side else Vector((0, r * 0.12, 0))
    if "Frown" in name or "LowerDown" in name or "Lower" in name:
        move = Vector((side * r * 0.05, 0, -r * 0.1))
    if "Close" in name or "Press" in name:
        move = Vector((0, -r * 0.05, 0))
    return c, r * 0.3, move


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)

    skin = bpy.data.materials.new("Skin")
    skin.use_nodes = True
    bsdf = skin.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.82, 0.62, 0.52, 1)
    bsdf.inputs["Roughness"].default_value = 0.55

    shirt = bpy.data.materials.new("Shirt")
    shirt.use_nodes = True
    shirt.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.15, 0.25, 0.45, 1)

    bpy.ops.mesh.primitive_cylinder_add(radius=0.18, depth=0.75, location=(0, 0, HEAD_Y - 0.55))
    body = bpy.context.active_object
    body.name = "Body"
    body.data.materials.append(shirt)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=HEAD_RADIUS, segments=48, ring_count=32, location=(0, 0, HEAD_Y))
    head = bpy.context.active_object
    head.name = "Head"
    head.data.materials.append(skin)
    bpy.ops.object.shade_smooth()

    head.shape_key_add(name="Basis")
    for name in ARKIT:
        key = head.shape_key_add(name=name, from_mix=False)
        center, radius, move = region(name)
        center.y, move.y = -center.y, -move.y  # face toward Blender -Y (glTF +Z)
        for i, v in enumerate(head.data.vertices):
            dist = (v.co - center).length
            if dist < radius:
                falloff = 0.5 * (1 + math.cos(math.pi * dist / radius))
                key.data[i].co = v.co + move * falloff

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", export_morph=True, export_apply=False)
    print(f"Wrote {OUT} with {len(ARKIT)} ARKit shape keys")


main()
