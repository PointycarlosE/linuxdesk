#!/usr/bin/env python3
"""
LinuxDesk - Teste de captura de frames
Verifica se o grim consegue capturar frames corretamente.
Execute antes de testar com o Android.
"""

import subprocess
import sys
import time
import io
import os

def check_dep(cmd, pkg):
    result = subprocess.run(["which", cmd], capture_output=True)
    if result.returncode != 0:
        print(f"  ✗ '{cmd}' não encontrado → instale: sudo pacman -S {pkg}")
        return False
    print(f"  ✓ {cmd}")
    return True

def test_capture():
    print("\n─── Teste de captura de frame ───")
    start = time.monotonic()

    result = subprocess.run(
        ["grim", "-t", "ppm", "-"],
        capture_output=True,
        timeout=5.0
    )

    elapsed = (time.monotonic() - start) * 1000

    if result.returncode != 0:
        print(f"  ✗ grim falhou: {result.stderr.decode()[:200]}")
        return False

    size_kb = len(result.stdout) / 1024
    print(f"  ✓ Frame capturado em {elapsed:.0f}ms ({size_kb:.0f} KB PPM)")
    return result.stdout

def test_jpeg(raw_ppm):
    print("\n─── Teste de conversão JPEG ───")
    try:
        from PIL import Image
        import io as _io

        start = time.monotonic()
        img = Image.open(_io.BytesIO(raw_ppm))
        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        jpeg = buf.getvalue()
        elapsed = (time.monotonic() - start) * 1000

        print(f"  ✓ Resolução: {img.width}x{img.height}")
        print(f"  ✓ JPEG gerado em {elapsed:.0f}ms ({len(jpeg)/1024:.0f} KB)")

        # Salva para inspeção visual
        out_path = "/tmp/linuxdesk_test.jpg"
        with open(out_path, "wb") as f:
            f.write(jpeg)
        print(f"  ✓ Salvo em {out_path} (abra para verificar)")

        return True
    except ImportError:
        print("  ✗ Pillow não instalado → pip install pillow")
        return False
    except Exception as e:
        print(f"  ✗ Erro: {e}")
        return False

def test_fps():
    print("\n─── Teste de FPS (5 frames) ───")
    times = []
    for i in range(5):
        start = time.monotonic()
        result = subprocess.run(["grim", "-t", "ppm", "-"], capture_output=True, timeout=3.0)
        elapsed = (time.monotonic() - start) * 1000
        if result.returncode == 0:
            times.append(elapsed)
            print(f"  Frame {i+1}: {elapsed:.0f}ms")

    if times:
        avg = sum(times) / len(times)
        max_fps = 1000 / avg
        print(f"\n  Média: {avg:.0f}ms por frame → FPS máximo estimado: {max_fps:.0f}")
        if max_fps >= 30:
            print("  ✓ Captura rápida o suficiente para 30 FPS")
        elif max_fps >= 15:
            print("  ⚠ Captura lenta, recomendo --fps 15 ou --scale 0.75")
        else:
            print("  ✗ Captura muito lenta, verifique seu sistema")

def test_adb():
    print("\n─── Teste ADB ───")
    result = subprocess.run(["which", "adb"], capture_output=True)
    if result.returncode != 0:
        print("  ✗ ADB não instalado → sudo pacman -S android-tools")
        return

    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    lines = [l for l in result.stdout.splitlines() if l and "List of devices" not in l]

    if not lines:
        print("  ⚠ Nenhum dispositivo conectado (normal se o cabo não está plugado)")
    else:
        for line in lines:
            if "device" in line:
                print(f"  ✓ Dispositivo: {line.split()[0]}")
            elif "unauthorized" in line:
                print(f"  ⚠ Não autorizado: aceite a permissão no Android!")
            elif "offline" in line:
                print(f"  ✗ Dispositivo offline: verifique o cabo")

def main():
    print("╔═══════════════════════════════════╗")
    print("║   LinuxDesk - Diagnóstico v0.1    ║")
    print("╚═══════════════════════════════════╝")

    print("\n─── Dependências ───")
    ok = True
    ok &= check_dep("grim", "grim")
    ok &= check_dep("python3", "python")

    # Verifica WAYLAND_DISPLAY
    wayland = os.environ.get("WAYLAND_DISPLAY", "")
    if wayland:
        print(f"  ✓ WAYLAND_DISPLAY={wayland}")
    else:
        print("  ✗ WAYLAND_DISPLAY não definido — rode dentro do Niri!")
        ok = False

    if not ok:
        print("\n✗ Corrija os problemas acima antes de continuar.")
        sys.exit(1)

    raw = test_capture()
    if raw:
        test_jpeg(raw)
        test_fps()

    test_adb()

    print("\n─── Resumo ───")
    print("  Se tudo estiver ✓, rode: ./start.sh")
    print("  Dúvidas? Consulte o README.md\n")

if __name__ == "__main__":
    main()
