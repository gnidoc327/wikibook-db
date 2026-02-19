"""
RabbitMQ consumer 스크립트.

메시지를 수신하여 FastAPI 서버의 /internal/messages endpoint로 전달합니다.

실행:
    uv run python -m ch05.consumer

FastAPI 서버가 먼저 실행되어 있어야 합니다:
    uv run fastapi dev ch05/main.py
"""

import asyncio
import logging
import sys

import aio_pika
import httpx

from ch05.config.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


async def on_message(message: aio_pika.IncomingMessage) -> None:
    """
    메시지를 수신하여 FastAPI endpoint로 전달합니다.

    - 2xx: ACK (처리 성공)
    - 4xx: ACK (잘못된 메시지, 재처리 불필요)
    - 5xx 또는 네트워크 오류: NACK + requeue (재처리)
    """
    async with message.process(requeue=True):
        payload = {
            "routing_key": message.routing_key,
            "body": message.body.decode(),
        }
        logger.info("메시지 수신: routing_key=%s", message.routing_key)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.consumer.fastapi_url}/internal/messages",
                json=payload,
                timeout=30.0,
            )

        if response.status_code >= 500:
            logger.error(
                "FastAPI 서버 오류 (status=%s), 메시지를 재처리합니다.",
                response.status_code,
            )
            raise RuntimeError(f"FastAPI server error: {response.status_code}")

        if response.status_code >= 400:
            logger.error(
                "메시지 처리 실패 (status=%s): %s",
                response.status_code,
                payload,
            )
        else:
            logger.info("메시지 처리 완료: routing_key=%s", message.routing_key)


async def main() -> None:
    amqp_url = "amqp://{user}:{passwd}@{host}:{port}/".format(
        user=settings.rabbitmq.user,
        passwd=settings.rabbitmq.passwd,
        host=settings.rabbitmq.host,
        port=settings.rabbitmq.port,
    )

    connection = await aio_pika.connect_robust(amqp_url)
    logger.info("RabbitMQ 연결 완료")

    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)

        exchange = await channel.declare_exchange(
            settings.consumer.exchange_name,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        queue = await channel.declare_queue(
            settings.consumer.queue_name,
            durable=True,
        )
        await queue.bind(exchange, routing_key=settings.consumer.routing_key)

        await queue.consume(on_message)
        logger.info(
            "Consumer 시작: exchange=%s queue=%s routing_key=%s",
            settings.consumer.exchange_name,
            settings.consumer.queue_name,
            settings.consumer.routing_key,
        )

        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            logger.info("Consumer 종료")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Consumer 종료 (KeyboardInterrupt)")
        sys.exit(0)
