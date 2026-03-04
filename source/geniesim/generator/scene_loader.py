#!/usr/bin/env python3
"""
场景加载器 — 在 Isaac Sim 中查看生成的 scene.usda 文件

用法 (在 Docker 容器内):
    python source/geniesim/generator/scene_loader.py --scene ./harmful-behavior_output/scene.usda
    python source/geniesim/generator/scene_loader.py --scene ./harmful-behavior_output/scene.usda --auto-play
"""

import os
import sys
import argparse
from pathlib import Path

# Add project path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root / "source"))

import geniesim.utils.system_utils as system_utils
from isaacsim import SimulationApp

system_utils.check_and_fix_env()

simulation_app = SimulationApp({"headless": False})

from isaacsim.core.api import World
from isaacsim.core.utils.stage import add_reference_to_stage, get_current_stage
from isaacsim.core.utils.prims import delete_prim, get_prim_at_path, get_prim_children
from pxr import UsdLux, Sdf


def load_scene(scene_path: str, world: World, auto_play: bool = False):
    """Load a scene.usda file into Isaac Sim."""
    stage = get_current_stage()

    # Clear existing /World content
    world_prim = get_prim_at_path("/World")
    if world_prim.IsValid():
        for child in get_prim_children(world_prim):
            delete_prim(child.GetPath())
        delete_prim(world_prim.GetPath())

    # Import scene
    add_reference_to_stage(usd_path=scene_path, prim_path="/World")

    # Add Dome Light
    dome_path = "/World/DomeLight"
    if not get_prim_at_path(dome_path).IsValid():
        dome = UsdLux.DomeLight.Define(stage, Sdf.Path(dome_path))
        dome.CreateIntensityAttr().Set(1000)
        dome.CreateColorTemperatureAttr().Set(6500.0)
        dome.CreateEnableColorTemperatureAttr().Set(True)

    if auto_play:
        world.play()


def main():
    parser = argparse.ArgumentParser(description="Load scene.usda in Isaac Sim")
    parser.add_argument("--scene", required=True, help="Path to scene.usda file")
    parser.add_argument("--auto-play", action="store_true", help="Auto start simulation")
    args = parser.parse_args()

    scene_path = os.path.abspath(args.scene)
    if not os.path.exists(scene_path):
        print(f"Error: {scene_path} not found")
        simulation_app.close()
        sys.exit(1)

    world = World(stage_units_in_meters=1, physics_dt=1/60, rendering_dt=1/60)
    print(f"Loading scene: {scene_path}")
    load_scene(scene_path, world, args.auto_play)
    print("Scene loaded. Close the window to exit.")

    while simulation_app.is_running():
        world.step(render=True)

    simulation_app.close()


if __name__ == "__main__":
    main()
