import asyncio
import os
from datetime import datetime

import websockets
import cv2
import numpy as np
import boto3
from botocore.exceptions import NoCredentialsError

SERVER_URL = "ws://localhost:8080/video-stream"
S3_BUCKET_NAME = "my-local-bucket"
S3_FOLDER = "video_frames/"  # Папка в S3 для хранения кадров

s3_client = boto3.client(
    's3',
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    endpoint_url=os.environ.get('S3_ENDPOINT_URL')  # Для MinIO или LocalStack
)


def upload_to_s3(frame_data, frame_id):
    try:
        s3_key = f"{S3_FOLDER}{frame_id}.jpg"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=frame_data,
            ContentType='image/jpeg'
        )
        print(f"Uploaded frame {frame_id} to S3")
    except NoCredentialsError:
        print("AWS credentials not found!")
    except Exception as e:
        print(f"Error uploading to S3: {e}")


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


# async def send_video(stream_id: str):
#     while True:
#         try:
#             async with websockets.connect(
#                     f"{SERVER_URL}/{stream_id}",
#                     max_size=10_000_000,
#                     ping_interval=5,
#                     ping_timeout=10
#             ) as websocket:
#                 print(f"Connected to {SERVER_URL}/{stream_id}")
#                 while True:
#                     frame = await generate_frame()
#                     await websocket.send(frame)
#                     await asyncio.sleep(1 / 30)  # 30 FPS
#
#         except websockets.exceptions.ConnectionClosedError:
#             print("Connection lost. Retry...")
#             await asyncio.sleep(1)
#         except Exception as e:
#             print(f"Error: {e}")
#             await asyncio.sleep(5)

async def send_video(stream_id: str):
    frame_id = 0
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

                    # Загрузка кадра в S3
                    upload_to_s3(frame, frame_id)
                    frame_id += 1

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
        if not stream_id:
            raise ValueError("Environment variable 'stream_id' is required!")

        if not os.environ.get('AWS_ACCESS_KEY_ID') or not os.environ.get('AWS_SECRET_ACCESS_KEY'):
            raise ValueError("AWS credentials are missing!")

        asyncio.run(send_video(stream_id))
    except KeyboardInterrupt:
        print("Client stopped")
