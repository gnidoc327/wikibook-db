import logging

import aio_pika

from ch05.config.config import settings

logger = logging.getLogger(__name__)

# RabbitMQ는 메시지 발행(publish)만 하므로 connection pool이 불필요합니다.
# 단일 connection + channel로 충분하며, aio_pika가 내부적으로
# heartbeat 및 reconnect를 관리합니다.
_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractRobustChannel | None = None


async def startup() -> None:
    """서버 시작 시 RabbitMQ에 연결합니다."""
    global _connection, _channel
    _connection = await aio_pika.connect_robust(
        "amqp://{user}:{passwd}@{host}:{port}/".format(
            user=settings.rabbitmq.user,
            passwd=settings.rabbitmq.passwd,
            host=settings.rabbitmq.host,
            port=settings.rabbitmq.port,
        ),
    )
    _channel = await _connection.channel()
    logger.info("RabbitMQ 연결 완료")


async def shutdown() -> None:
    """서버 종료 시 RabbitMQ 연결을 닫습니다."""
    global _connection, _channel
    if _channel:
        await _channel.close()
    if _connection:
        await _connection.close()
    _channel = None
    _connection = None


async def publish(exchange_name: str, routing_key: str, message: str):
    """
    메시지를 발행합니다.
    """
    if not _channel:
        raise RuntimeError("RabbitMQ 연결이 되어있지 않습니다.")

    exchange = await _channel.declare_exchange(
        exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
    )
    await exchange.publish(
        aio_pika.Message(body=message.encode()),
        routing_key=routing_key,
    )
