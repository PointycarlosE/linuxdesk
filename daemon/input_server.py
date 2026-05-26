#!/usr/bin/env python3
"""
LinuxDesk - Input Server
Recebe eventos de toque e caneta do Android e cria dispositivos uinput virtuais.
"""

import asyncio
import json
import logging
import sys
import uinput

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("linuxdesk.input")

# Resolução do tablet (Tab S6 Lite = 2000x1200)
TABLET_W = 2000
TABLET_H = 1200

# Resolução do monitor virtual
SCREEN_W = 1920
SCREEN_H = 1080

# Pressão máxima da S Pen
PEN_MAX_PRESSURE = 4096


def create_touchpad():
    """Cria um touchpad virtual multitouch."""
    events = (
        uinput.BTN_TOUCH,
        uinput.BTN_LEFT,
        uinput.BTN_RIGHT,
        uinput.ABS_X + (0, SCREEN_W, 0, 0),
        uinput.ABS_Y + (0, SCREEN_H, 0, 0),
        uinput.ABS_MT_SLOT + (0, 9, 0, 0),
        uinput.ABS_MT_TRACKING_ID + (0, 65535, 0, 0),
        uinput.ABS_MT_POSITION_X + (0, SCREEN_W, 0, 0),
        uinput.ABS_MT_POSITION_Y + (0, SCREEN_H, 0, 0),
        uinput.REL_X,
        uinput.REL_Y,
        uinput.REL_WHEEL,
        uinput.REL_HWHEEL,
    )
    return uinput.Device(events, name="LinuxDesk Touchpad", bustype=uinput.BUS_VIRTUAL)


def create_pen_tablet():
    """Cria um tablet digitalizador virtual para a S Pen."""
    events = (
        uinput.BTN_TOUCH,
        uinput.BTN_STYLUS,
        uinput.BTN_STYLUS2,
        uinput.ABS_X + (0, SCREEN_W, 0, 0),
        uinput.ABS_Y + (0, SCREEN_H, 0, 0),
        uinput.ABS_PRESSURE + (0, PEN_MAX_PRESSURE, 0, 0),
        uinput.ABS_TILT_X + (-90, 90, 0, 0),
        uinput.ABS_TILT_Y + (-90, 90, 0, 0),
        uinput.ABS_DISTANCE + (0, 255, 0, 0),
    )
    return uinput.Device(events, name="LinuxDesk S Pen", bustype=uinput.BUS_VIRTUAL)


class InputServer:
    def __init__(self, host="127.0.0.1", port=7879):
        self.host = host
        self.port = port
        self.touchpad = None
        self.pen = None
        self._last_slots = {}

    def setup_devices(self):
        log.info("Criando dispositivos virtuais...")
        self.touchpad = create_touchpad()
        self.pen = create_pen_tablet()
        log.info("Touchpad virtual criado ✓")
        log.info("S Pen virtual criada ✓")

    def scale_x(self, x, source_w):
        return int(x * SCREEN_W / source_w)

    def scale_y(self, y, source_h):
        return int(y * SCREEN_H / source_h)

    def handle_touch(self, event):
        """Processa eventos de toque (dedos)."""
        action = event.get("action")
        x = self.scale_x(event.get("x", 0), event.get("w", TABLET_W))
        y = self.scale_y(event.get("y", 0), event.get("h", TABLET_H))
        slot = event.get("slot", 0)
        pointer_count = event.get("pointers", 1)

        if action == "down":
            self.touchpad.emit(uinput.ABS_MT_SLOT, slot)
            self.touchpad.emit(uinput.ABS_MT_TRACKING_ID, slot)
            self.touchpad.emit(uinput.ABS_MT_POSITION_X, x)
            self.touchpad.emit(uinput.ABS_MT_POSITION_Y, y)
            self.touchpad.emit(uinput.ABS_X, x)
            self.touchpad.emit(uinput.ABS_Y, y)
            if slot == 0:
                self.touchpad.emit(uinput.BTN_TOUCH, 1)
                self.touchpad.emit(uinput.BTN_LEFT, 1)

        elif action == "move":
            self.touchpad.emit(uinput.ABS_MT_SLOT, slot)
            self.touchpad.emit(uinput.ABS_MT_POSITION_X, x)
            self.touchpad.emit(uinput.ABS_MT_POSITION_Y, y)
            if slot == 0:
                self.touchpad.emit(uinput.ABS_X, x)
                self.touchpad.emit(uinput.ABS_Y, y)

        elif action == "up":
            self.touchpad.emit(uinput.ABS_MT_SLOT, slot)
            self.touchpad.emit(uinput.ABS_MT_TRACKING_ID, -1)
            if slot == 0:
                self.touchpad.emit(uinput.BTN_TOUCH, 0)
                self.touchpad.emit(uinput.BTN_LEFT, 0)

        elif action == "scroll":
            dx = event.get("dx", 0)
            dy = event.get("dy", 0)
            if dy != 0:
                self.touchpad.emit(uinput.REL_WHEEL, -1 if dy > 0 else 1)
            if dx != 0:
                self.touchpad.emit(uinput.REL_HWHEEL, -1 if dx > 0 else 1)

    def handle_pen(self, event):
        """Processa eventos da S Pen."""
        action = event.get("action")
        x = self.scale_x(event.get("x", 0), event.get("w", TABLET_W))
        y = self.scale_y(event.get("y", 0), event.get("h", TABLET_H))
        pressure = int(event.get("pressure", 0) * PEN_MAX_PRESSURE)
        tilt_x = event.get("tilt_x", 0)
        tilt_y = event.get("tilt_y", 0)
        distance = event.get("distance", 0)
        button1 = event.get("button1", False)
        button2 = event.get("button2", False)

        self.pen.emit(uinput.ABS_X, x)
        self.pen.emit(uinput.ABS_Y, y)
        self.pen.emit(uinput.ABS_TILT_X, int(tilt_x))
        self.pen.emit(uinput.ABS_TILT_Y, int(tilt_y))

        if action == "hover":
            self.pen.emit(uinput.ABS_DISTANCE, min(255, int(distance * 255)))
            self.pen.emit(uinput.BTN_TOUCH, 0)
            self.pen.emit(uinput.ABS_PRESSURE, 0)

        elif action == "down":
            self.pen.emit(uinput.ABS_DISTANCE, 0)
            self.pen.emit(uinput.ABS_PRESSURE, pressure)
            self.pen.emit(uinput.BTN_TOUCH, 1)
            self.pen.emit(uinput.BTN_STYLUS, 1 if button1 else 0)
            self.pen.emit(uinput.BTN_STYLUS2, 1 if button2 else 0)

        elif action == "move":
            self.pen.emit(uinput.ABS_DISTANCE, 0)
            self.pen.emit(uinput.ABS_PRESSURE, pressure)
            self.pen.emit(uinput.BTN_STYLUS, 1 if button1 else 0)
            self.pen.emit(uinput.BTN_STYLUS2, 1 if button2 else 0)

        elif action == "up":
            self.pen.emit(uinput.ABS_PRESSURE, 0)
            self.pen.emit(uinput.BTN_TOUCH, 0)
            self.pen.emit(uinput.BTN_STYLUS, 0)
            self.pen.emit(uinput.BTN_STYLUS2, 0)

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info("peername")
        log.info(f"Cliente input conectado: {addr}")
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                try:
                    event = json.loads(line.decode().strip())
                    etype = event.get("type")
                    if etype == "touch":
                        self.handle_touch(event)
                    elif etype == "pen":
                        self.handle_pen(event)
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            log.error(f"Erro: {e}")
        finally:
            writer.close()
            log.info(f"Cliente input desconectado: {addr}")

    async def start(self):
        self.setup_devices()
        server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        log.info(f"Input server escutando em {self.host}:{self.port}")
        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(InputServer().start())
