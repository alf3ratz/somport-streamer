import asyncio
import os
from datetime import datetime

import websockets
import cv2
import numpy as np
import boto3
import uvicorn
from botocore.exceptions import NoCredentialsError
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

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


@app.websocket("/ws/{stream_id}")
async def websocket_endpoint(websocket: WebSocket, stream_id: str):
    await websocket.accept()
    frame_id = 0
    try:
        while True:
            frame = await generate_frame()
            await websocket.send_bytes(frame)

            # Загрузка кадра в S3
            upload_to_s3(frame, frame_id)
            frame_id += 1

            await asyncio.sleep(1 / 30)  # 30 FPS
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    import uvicorn

    try:
        if not os.environ.get('stream_id'):
            raise ValueError("Environment variable 'stream_id' is required!")

        if not os.environ.get('AWS_ACCESS_KEY_ID') or not os.environ.get('AWS_SECRET_ACCESS_KEY'):
            raise ValueError("AWS credentials are missing!")

        uvicorn.run(app, host="0.0.0.0", port=8081)
    except KeyboardInterrupt:
        print("Server stopped")
