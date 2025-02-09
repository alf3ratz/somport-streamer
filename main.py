import asyncio
import logging
from datetime import time

import cv2
import numpy as np
from aiohttp import web
from aiortc import RTCPeerConnection, VideoStreamTrack, RTCSessionDescription
from aiortc.contrib.media import MediaRelay
from av import VideoFrame

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Класс для генерации тестового видео
class MockCameraStreamTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.relay = MediaRelay()

    async def recv(self):
        # Генерация чёрного кадра с текстом
        width, height = 640, 480
        frame_data = np.zeros((height, width, 3), dtype=np.uint8)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame_data, f"Mock Camera - {timestamp}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        # Преобразование в VideoFrame
        frame = VideoFrame.from_ndarray(frame_data, format="bgr24")
        frame.pts = None  # Обнуляем временные метки
        frame.time_base = None
        return frame

# Обработка WebSocket-соединений
pcs = set()  # Множество для хранения активных соединений

async def offer(request):
    pc = RTCPeerConnection(
        configuration={"iceServers": [{"urls": "stun:stun.l.google.com:19302"}]}
    )
    pcs.add(pc)

    params = await request.json()
    print("Received SDP Offer:", params["sdp"])  # <-- Лог для отладки

    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    video_track = MockCameraStreamTrack()
    pc.addTrack(video_track)

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })

# Завершение работы приложения
async def on_shutdown(app):
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

# Запуск сервера
app = web.Application()
app.on_shutdown.append(on_shutdown)
app.router.add_post("/offer", offer)

if __name__ == "__main__":
    logging.info("Запуск сервера на http://localhost:8081")
    web.run_app(app, port=8081)