import asyncio
import os
from datetime import datetime

import websockets
import cv2
import numpy as np

SERVER_URL = "ws://localhost:8080/video-stream"


async def send_video_old():
    # cap = cv2.VideoCapture(0)  # Используем основную камеру
    width, height = 640, 480
    # Устанавливаем параметры камеры
    # cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    # ret, frame = cap.read()
    # if not ret:
    #     break  # Ошибка чтения кадра
    #
    # # Кодируем кадр в JPEG (без base64)
    # _, buffer = cv2.imencode('.jpg', frame)
    #
    # # Отправляем бинарные данные напрямую
    # await websocket.send(buffer.tobytes())
    #
    # # Задержка для FPS (30 кадров в секунду)
    # await asyncio.sleep(1 / 30)

    # cap.release()


async def generate_frame():
    """Генерирует кадр с текущим временем на черном фоне"""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    current_time = datetime.now().strftime("%H:%M:%S.%f")[:-3] + "_stream_2"  # С миллисекундами

    # Настройки текста
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1
    thickness = 2
    color = (255, 255, 255)  # Белый цвет

    # Расчет позиции текста
    (text_width, text_height), _ = cv2.getTextSize(
        current_time, font, font_scale, thickness)
    position = ((640 - text_width) // 2, (480 + text_height) // 2)

    cv2.putText(frame, current_time, position, font, font_scale, color, thickness)
    _, buffer = cv2.imencode('.jpg', frame)
    return buffer.tobytes()


async def send_video(stream_id: str):
    while True:
        try:
            async with websockets.connect(
                    f"{SERVER_URL}/{stream_id}",
                    max_size=10_000_000,
                    ping_interval=5,
                    ping_timeout=10
            ) as websocket:
                print(f"Connected to {SERVER_URL}/{stream_id}")
                while True:
                    frame = await generate_frame()
                    await websocket.send(frame)
                    await asyncio.sleep(1 / 30)  # 30 FPS

        except websockets.exceptions.ConnectionClosedError:
            print("Connection lost. Retry...")
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        stream_id = os.environ.get('stream_id')
        asyncio.run(send_video(stream_id))
    except KeyboardInterrupt:
        print("Client stopped")
