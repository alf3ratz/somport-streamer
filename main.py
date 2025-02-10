# import asyncio
# import logging
# from datetime import time
#
# import cv2
# import numpy as np
# from aiohttp import web
# from aiortc import RTCPeerConnection, VideoStreamTrack, RTCSessionDescription
# from aiortc.contrib.media import MediaRelay
# from av import VideoFrame
#
# # Настройка логирования
# logging.basicConfig(level=logging.INFO)
#
# # Класс для генерации тестового видео
# class MockCameraStreamTrack(VideoStreamTrack):
#     def __init__(self):
#         super().__init__()
#         self.relay = MediaRelay()
#
#     async def recv(self):
#         # Генерация чёрного кадра с текстом
#         width, height = 640, 480
#         frame_data = np.zeros((height, width, 3), dtype=np.uint8)
#         timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
#         cv2.putText(frame_data, f"Mock Camera - {timestamp}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
#
#         # Преобразование в VideoFrame
#         frame = VideoFrame.from_ndarray(frame_data, format="bgr24")
#         frame.pts = None  # Обнуляем временные метки
#         frame.time_base = None
#         return frame
#
# # Обработка WebSocket-соединений
# pcs = set()  # Множество для хранения активных соединений
#
# async def offer(request):
#     pc = RTCPeerConnection(
#         configuration={"iceServers": [{"urls": "stun:stun.l.google.com:19302"}]}
#     )
#     pcs.add(pc)
#
#     params = await request.json()
#     print("Received SDP Offer:", params["sdp"])  # <-- Лог для отладки
#
#     offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
#     video_track = MockCameraStreamTrack()
#     pc.addTrack(video_track)
#
#     await pc.setRemoteDescription(offer)
#     answer = await pc.createAnswer()
#     await pc.setLocalDescription(answer)
#
#     return web.json_response({
#         "sdp": pc.localDescription.sdp,
#         "type": pc.localDescription.type
#     })
#
# # Завершение работы приложения
# async def on_shutdown(app):
#     coros = [pc.close() for pc in pcs]
#     await asyncio.gather(*coros)
#     pcs.clear()
#
# # Запуск сервера
# app = web.Application()
# app.on_shutdown.append(on_shutdown)
# app.router.add_post("/offer", offer)
#
# if __name__ == "__main__":
#     logging.info("Запуск сервера на http://localhost:8081")
#     web.run_app(app, port=8081)

import os
import asyncio
from aiohttp import web
import numpy as np
import cv2
import time
from datetime import datetime

# Путь к временной директории для хранения сегментов HLS
HLS_DIR = "hls"
os.makedirs(HLS_DIR, exist_ok=True)

# Настройки HLS
SEGMENT_DURATION = 5  # Длительность каждого сегмента в секундах
SEGMENT_COUNT = 5     # Количество сохраняемых сегментов в плейлисте

# Генерация фиктивного видеопотока
async def generate_video_stream():
    width, height = 640, 480
    frame_rate = 20  # Количество кадров в секунду

    while True:
        # Создание чёрного кадра
        frame = np.zeros((height, width, 3), dtype=np.uint8)

        # Добавление текущего времени на кадр
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, f"Mock Camera - {timestamp}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        yield frame
        await asyncio.sleep(1 / frame_rate)

# Запись сегмента HLS
class HLSSegmenter:
    def __init__(self, directory, segment_duration, max_segments):
        self.directory = directory
        self.segment_duration = segment_duration
        self.max_segments = max_segments
        self.current_segment_index = 0
        self.frame_buffer = []
        self.start_time = None

    async def write_frame(self, frame):
        if self.start_time is None:
            self.start_time = time.time()

        self.frame_buffer.append(frame)

        # Если накоплено достаточно кадров для нового сегмента
        elapsed_time = time.time() - self.start_time
        if elapsed_time >= self.segment_duration:
            await self.save_segment()
            self.start_time = time.time()
            self.frame_buffer = []

    async def save_segment(self):
        segment_filename = os.path.join(self.directory, f"segment_{self.current_segment_index:03d}.ts")
        print(f"Saving segment: {segment_filename}")

        # Сохраняем кадры в видеосегмент
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(segment_filename, fourcc, 20, (640, 480))

        for frame in self.frame_buffer:
            writer.write(frame)

        writer.release()

        # Обновляем индекс сегмента
        self.current_segment_index += 1
        if self.current_segment_index >= self.max_segments:
            self.current_segment_index = 0

        # Удаляем старые сегменты
        self.cleanup_old_segments()

    def cleanup_old_segments(self):
        for i in range(self.current_segment_index, self.current_segment_index + self.max_segments):
            old_segment = os.path.join(self.directory, f"segment_{i % self.max_segments:03d}.ts")
            if os.path.exists(old_segment):
                os.remove(old_segment)

    def generate_playlist(self):
        playlist = "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:5\n#EXT-X-MEDIA-SEQUENCE:{}\n".format(
            self.current_segment_index
        )

        for i in range(self.current_segment_index, self.current_segment_index + self.max_segments):
            segment_index = i % self.max_segments
            segment_name = f"segment_{segment_index:03d}.ts"
            segment_path = os.path.join(self.directory, segment_name)

            if os.path.exists(segment_path):
                playlist += f"#EXTINF:{self.segment_duration},\n{segment_name}\n"

        playlist += "#EXT-X-ENDLIST\n"
        return playlist

# Обработка запросов к HLS-плейлисту и сегментам
async def handle_hls(request):
    path = request.match_info.get("path", "")
    file_path = os.path.join(HLS_DIR, path)

    if not os.path.exists(file_path):
        if path == "stream.m3u8":
            # Возвращаем динамически сгенерированный плейлист
            playlist = hls_segmenter.generate_playlist()
            return web.Response(text=playlist, content_type="application/vnd.apple.mpegurl")

        raise web.HTTPNotFound()

    return web.FileResponse(file_path)

# Основной цикл
async def main():
    global hls_segmenter
    hls_segmenter = HLSSegmenter(HLS_DIR, SEGMENT_DURATION, SEGMENT_COUNT)

    # Запуск HTTP-сервера
    app = web.Application()
    app.router.add_get("/{path:.+}", handle_hls)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8081)
    await site.start()

    print("HLS server started at http://localhost:8081/stream.m3u8")

    # Запуск генератора кадров
    video_generator = generate_video_stream()

    try:
        while True:
            frame = await video_generator.__anext__()
            await hls_segmenter.write_frame(frame)
            await asyncio.sleep(0)  # Отдаем управление событийному циклу
    except asyncio.CancelledError:
        print("Stopping server...")
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())