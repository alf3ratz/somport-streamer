import asyncio

import av
import cv2
import logging
import numpy as np
from aiohttp import web
from aiortc import RTCPeerConnection, VideoStreamTrack, RTCSessionDescription
from aiortc.contrib.media import MediaRelay
from aiortc.mediastreams import VideoFrame

# import subprocess,os
# subprocess.run('start microsoft.windows.camera:', shell=True)
# Настройка логирования
logging.basicConfig(level=logging.INFO)


# Класс для захвата видео с камеры
class CameraStreamTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.cap = cv2.VideoCapture(0)  # 0 — индекс встроенной камеры

    async def recv(self):
        if not self.cap.isOpened():
            raise Exception("Не удалось открыть камеру")

        ret, frame = self.cap.read()  # Считываем кадр
        if not ret:
            raise Exception("Не удалось получить кадр с камеры")

        # Преобразуем кадр из BGR (OpenCV) в RGB (WebRTC)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_av = VideoFrame.from_ndarray(frame_rgb, format="rgb24")
        frame_av.pts = None  # Обнуляем временные метки
        frame_av.time_base = None
        return frame_av


# Обработка WebSocket-соединений
async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    # Установка предложения
    await pc.setRemoteDescription(offer)

    # Добавление треков
    video_track = CameraStreamTrack()
    pc.addTrack(video_track)

    # Создание ответа
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # Отправка ответа клиенту
    return web.json_response(
        {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    )


# Основной цикл приложения
pcs = set()  # Множество для хранения активных соединений


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
