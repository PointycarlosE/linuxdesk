#!/usr/bin/env python3
"""
LinuxDesk - Daemon servidor
Captura frames do Wayland (Niri) e envia para o cliente Android via TCP sobre ADB.
"""

import asyncio
import subprocess
import struct
import time
import logging
import signal
import sys
import os
from dataclasses import dataclass
from typing import Optional

# Tenta importar dependências opcionais
try:
    from PIL import Image
    import io
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("linuxdesk")


# ─────────────────────────────────────────────
# Configuração
# ─────────────────────────────────────────────

@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 7878
    fps_target: int = 30          # FPS alvo
    jpeg_quality: int = 80        # Qualidade JPEG (0-100)
    capture_output: str = ""      # Nome do output Wayland (vazio = primeiro disponível)
    scale: float = 1.0            # Fator de escala da imagem (0.5 = metade)


config = Config()


# ─────────────────────────────────────────────
# Captura de frames via grim (Wayland/Niri)
# ─────────────────────────────────────────────

class FrameCapture:
    """
    Captura frames do compositor Wayland usando `grim`.
    grim usa wlr-screencopy protocol, compatível com Niri.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._check_grim()

    def _check_grim(self):
        result = subprocess.run(["which", "grim"], capture_output=True)
        if result.returncode != 0:
            log.error("'grim' não encontrado! Instale com: sudo pacman -S grim")
            sys.exit(1)
        log.info("grim encontrado ✓")

    def get_outputs(self) -> list[str]:
        """Lista os outputs Wayland disponíveis."""
        try:
            result = subprocess.run(
                ["grim", "-l"],  # lista outputs
                capture_output=True, text=True, timeout=5
            )
            outputs = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            return outputs
        except Exception:
            return []

    def capture_frame(self) -> Optional[bytes]:
        """
        Captura um frame e retorna como JPEG em bytes.
        Retorna None em caso de falha.
        """
        cmd = ["grim", "-t", "ppm", "-c"]  # PPM é mais rápido que PNG para processar

        if self.cfg.capture_output:
            cmd += ["-o", self.cfg.capture_output]

        cmd.append("-")  # saída para stdout

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=2.0
            )

            if result.returncode != 0:
                log.warning(f"grim falhou: {result.stderr.decode()[:100]}")
                return None

            raw = result.stdout
            if not raw:
                return None

            # Converte PPM → JPEG com PIL
            if HAS_PIL:
                img = Image.open(io.BytesIO(raw))

                # Aplica escala se necessário
                if self.cfg.scale != 1.0:
                    new_w = int(img.width * self.cfg.scale)
                    new_h = int(img.height * self.cfg.scale)
                    img = img.resize((new_w, new_h), Image.BILINEAR)

                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=self.cfg.jpeg_quality, optimize=False)
                return buf.getvalue()
            else:
                # Fallback: retorna PPM raw (menos eficiente)
                return raw

        except subprocess.TimeoutExpired:
            log.warning("Timeout ao capturar frame")
            return None
        except Exception as e:
            log.error(f"Erro na captura: {e}")
            return None


# ─────────────────────────────────────────────
# Protocolo de comunicação
# ─────────────────────────────────────────────
#
# Cada frame é enviado como:
#   [4 bytes: tamanho do frame em uint32 big-endian]
#   [N bytes: dados JPEG]
#
# Mensagens de controle do cliente → servidor:
#   "HELLO\n"  → handshake inicial
#   "PING\n"   → keepalive
#   "BYE\n"    → desconexão limpa
#
# ─────────────────────────────────────────────

HEADER_SIZE = 4  # bytes para o tamanho do frame


def pack_frame(jpeg_data: bytes) -> bytes:
    """Empacota frame com header de tamanho."""
    size = len(jpeg_data)
    header = struct.pack(">I", size)  # uint32 big-endian
    return header + jpeg_data


# ─────────────────────────────────────────────
# Servidor TCP assíncrono
# ─────────────────────────────────────────────

class LinuxDeskServer:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.capture = FrameCapture(cfg)
        self.clients: set[asyncio.StreamWriter] = set()
        self.running = True
        self.frame_count = 0
        self.last_fps_report = time.time()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        log.info(f"Cliente conectado: {addr}")
        self.clients.add(writer)

        try:
            # Aguarda handshake
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            msg = line.decode().strip()

            if msg != "HELLO":
                log.warning(f"Handshake inválido de {addr}: {msg!r}")
                return

            log.info(f"Handshake OK com {addr}")

            # Envia configuração inicial
            info = f"OK fps={self.cfg.fps_target} quality={self.cfg.jpeg_quality}\n"
            writer.write(info.encode())
            await writer.drain()

            # Loop de streaming
            frame_interval = 1.0 / self.cfg.fps_target

            while self.running:
                start = time.monotonic()

                # Verifica mensagens do cliente (não-bloqueante)
                try:
                    ctrl = await asyncio.wait_for(reader.readline(), timeout=0.001)
                    ctrl_msg = ctrl.decode().strip()
                    if ctrl_msg == "BYE":
                        log.info(f"Cliente {addr} desconectou (BYE)")
                        break
                except asyncio.TimeoutError:
                    pass  # Normal, sem mensagem pendente

                # Captura e envia frame
                frame = await asyncio.get_event_loop().run_in_executor(
                    None, self.capture.capture_frame
                )

                if frame:
                    try:
                        packet = pack_frame(frame)
                        writer.write(packet)
                        await writer.drain()
                        self.frame_count += 1
                        self._report_fps()
                    except (ConnectionResetError, BrokenPipeError):
                        log.info(f"Cliente {addr} desconectou abruptamente")
                        break

                # Controle de FPS
                elapsed = time.monotonic() - start
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.TimeoutError:
            log.warning(f"Timeout no handshake com {addr}")
        except Exception as e:
            log.error(f"Erro com cliente {addr}: {e}")
        finally:
            self.clients.discard(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            log.info(f"Cliente {addr} removido. Clientes ativos: {len(self.clients)}")

    def _report_fps(self):
        now = time.time()
        elapsed = now - self.last_fps_report
        if elapsed >= 5.0:
            fps = self.frame_count / elapsed
            log.info(f"FPS atual: {fps:.1f} | Clientes: {len(self.clients)}")
            self.frame_count = 0
            self.last_fps_report = now

    async def start(self):
        log.info("=" * 50)
        log.info("  LinuxDesk Server v0.1")
        log.info("=" * 50)
        log.info(f"Host:     {self.cfg.host}:{self.cfg.port}")
        log.info(f"FPS alvo: {self.cfg.fps_target}")
        log.info(f"Qualidade JPEG: {self.cfg.jpeg_quality}")
        log.info(f"PIL disponível: {HAS_PIL}")

        # Lista outputs disponíveis
        outputs = self.capture.get_outputs()
        if outputs:
            log.info(f"Outputs Wayland: {outputs}")
        else:
            log.info("Outputs Wayland: (usando padrão)")

        server = await asyncio.start_server(
            self.handle_client,
            self.cfg.host,
            self.cfg.port
        )

        log.info(f"\n✓ Servidor escutando em {self.cfg.host}:{self.cfg.port}")
        log.info("  Aguardando conexão do Android...\n")

        async with server:
            await server.serve_forever()

    def stop(self):
        self.running = False
        log.info("Encerrando servidor...")


# ─────────────────────────────────────────────
# Ponto de entrada
# ─────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="LinuxDesk - servidor de display remoto")
    parser.add_argument("--port", type=int, default=7878, help="Porta TCP (padrão: 7878)")
    parser.add_argument("--fps", type=int, default=30, help="FPS alvo (padrão: 30)")
    parser.add_argument("--quality", type=int, default=80, help="Qualidade JPEG 1-100 (padrão: 80)")
    parser.add_argument("--output", type=str, default="", help="Nome do output Wayland")
    parser.add_argument("--scale", type=float, default=1.0, help="Escala da imagem (padrão: 1.0)")
    args = parser.parse_args()

    cfg = Config(
        port=args.port,
        fps_target=args.fps,
        jpeg_quality=args.quality,
        capture_output=args.output,
        scale=args.scale,
    )

    server = LinuxDeskServer(cfg)

    async def run():
        loop = asyncio.get_running_loop()

        def handle_signal():
            server.stop()
            loop.stop()

        loop.add_signal_handler(signal.SIGINT, handle_signal)
        loop.add_signal_handler(signal.SIGTERM, handle_signal)

        await server.start()

    try:
        asyncio.run(run())
    except Exception as e:
        log.error(f"Erro fatal: {e}")


if __name__ == "__main__":
    main()
