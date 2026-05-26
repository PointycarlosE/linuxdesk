#!/usr/bin/env python3
"""
LinuxDesk - Cursor Warp Daemon
Lê eventos do mouse via evdev e faz warp nas bordas entre monitores.
"""

import subprocess
import time
import json
import os
import sys
import threading
import evdev
from evdev import InputDevice, ecodes

YDOTOOL_SOCKET = os.environ.get("YDOTOOL_SOCKET", "/run/user/1000/.ydotool_socket")
EDGE_THRESHOLD = 2   # pixels da borda para acionar warp
WARP_COOLDOWN = 0.5  # segundos entre warps

def get_outputs():
    """Lê os outputs do Niri via IPC."""
    try:
        result = subprocess.run(
            ["niri", "msg", "-j", "outputs"],
            capture_output=True, text=True, timeout=5
        )
        data = json.loads(result.stdout)
        monitors = []
        for name, out in data.items():
            if out.get("logical"):
                log = out["logical"]
                monitors.append({
                    "name": name,
                    "x": log["x"],
                    "y": log["y"],
                    "width": log["width"],
                    "height": log["height"],
                })
        return monitors
    except Exception as e:
        print(f"Erro ao ler outputs: {e}")
        return []

def move_cursor(x, y):
    """Move o cursor para posição absoluta."""
    env = os.environ.copy()
    env["YDOTOOL_SOCKET"] = YDOTOOL_SOCKET
    subprocess.run(
        ["ydotool", "mousemove", "--absolute", "--x", str(x), "--y", str(y)],
        env=env, capture_output=True
    )

def find_mouse_device():
    """Encontra o dispositivo de mouse."""
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for dev in devices:
        caps = dev.capabilities()
        if ecodes.EV_REL in caps and ecodes.REL_X in caps[ecodes.EV_REL]:
            print(f"Mouse encontrado: {dev.name} ({dev.path})")
            return dev
    return None

def get_focused_output():
    """Retorna o nome do output focado."""
    try:
        result = subprocess.run(
            ["niri", "msg", "-j", "focused-output"],
            capture_output=True, text=True, timeout=1
        )
        data = json.loads(result.stdout)
        return data.get("name", "")
    except Exception:
        return ""

def find_neighbor(monitors, current_name, direction):
    """Encontra o monitor vizinho na direção dada."""
    current = next((m for m in monitors if m["name"] == current_name), None)
    if not current:
        return None

    for m in monitors:
        if m["name"] == current_name:
            continue
        if direction == "right":
            if m["x"] == current["x"] + current["width"]:
                return m
        elif direction == "left":
            if m["x"] + m["width"] == current["x"]:
                return m
        elif direction == "down":
            if m["y"] == current["y"] + current["height"]:
                return m
        elif direction == "up":
            if m["y"] + m["height"] == current["y"]:
                return m
    return None

def main():
    print("LinuxDesk Cursor Warp iniciando...")

    monitors = get_outputs()
    if len(monitors) < 2:
        print("Menos de 2 monitores ativos, saindo.")
        sys.exit(0)

    print(f"Monitores: {[(m['name'], m['x'], m['y'], m['width'], m['height']) for m in monitors]}")

    mouse = find_mouse_device()
    if not mouse:
        print("Nenhum mouse encontrado!")
        sys.exit(1)

    # Posição atual acumulada
    cur_x = 0
    cur_y = 0
    last_warp = 0

    # Descobrir posição inicial aproximada
    focused = get_focused_output()
    current_mon = next((m for m in monitors if m["name"] == focused), monitors[0])
    cur_x = current_mon["x"] + current_mon["width"] // 2
    cur_y = current_mon["y"] + current_mon["height"] // 2

    print(f"Posição inicial: {cur_x}, {cur_y} (monitor: {current_mon['name']})")
    print("Monitorando bordas...")

    for event in mouse.read_loop():
        if event.type == ecodes.EV_REL:
            if event.code == ecodes.REL_X:
                cur_x += event.value
            elif event.code == ecodes.REL_Y:
                cur_y += event.value

            # Descobrir em qual monitor estamos
            current_mon = None
            for m in monitors:
                if (m["x"] <= cur_x < m["x"] + m["width"] and
                        m["y"] <= cur_y < m["y"] + m["height"]):
                    current_mon = m
                    break

            if not current_mon:
                # Cursor fora de qualquer monitor — clamp
                cur_x = max(0, min(cur_x, sum(m["width"] for m in monitors) - 1))
                cur_y = max(0, min(cur_y, monitors[0]["height"] - 1))
                continue

            now = time.monotonic()
            if now - last_warp < WARP_COOLDOWN:
                continue

            # Verificar bordas
            warp_target = None
            warp_x = cur_x
            warp_y = cur_y

            # Borda direita
            if cur_x >= current_mon["x"] + current_mon["width"] - EDGE_THRESHOLD:
                neighbor = find_neighbor(monitors, current_mon["name"], "right")
                if neighbor:
                    warp_x = neighbor["x"] + EDGE_THRESHOLD + 5
                    warp_y = max(neighbor["y"], min(cur_y, neighbor["y"] + neighbor["height"] - 1))
                    warp_target = neighbor

            # Borda esquerda
            elif cur_x <= current_mon["x"] + EDGE_THRESHOLD:
                neighbor = find_neighbor(monitors, current_mon["name"], "left")
                if neighbor:
                    warp_x = neighbor["x"] + neighbor["width"] - EDGE_THRESHOLD - 5
                    warp_y = max(neighbor["y"], min(cur_y, neighbor["y"] + neighbor["height"] - 1))
                    warp_target = neighbor

            # Borda inferior
            elif cur_y >= current_mon["y"] + current_mon["height"] - EDGE_THRESHOLD:
                neighbor = find_neighbor(monitors, current_mon["name"], "down")
                if neighbor:
                    warp_x = max(neighbor["x"], min(cur_x, neighbor["x"] + neighbor["width"] - 1))
                    warp_y = neighbor["y"] + EDGE_THRESHOLD + 5
                    warp_target = neighbor

            # Borda superior
            elif cur_y <= current_mon["y"] + EDGE_THRESHOLD:
                neighbor = find_neighbor(monitors, current_mon["name"], "up")
                if neighbor:
                    warp_x = max(neighbor["x"], min(cur_x, neighbor["x"] + neighbor["width"] - 1))
                    warp_y = neighbor["y"] + neighbor["height"] - EDGE_THRESHOLD - 5
                    warp_target = neighbor

            if warp_target:
                print(f"Warp: {current_mon['name']} → {warp_target['name']} ({warp_x}, {warp_y})")
                move_cursor(warp_x, warp_y)
                cur_x = warp_x
                cur_y = warp_y
                last_warp = now

if __name__ == "__main__":
    main()
