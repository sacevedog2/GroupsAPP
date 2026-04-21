import pika
import json
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class EventPublisher:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.exchange = "groupsapp.events"

    def connect(self):
        try:
            parameters = pika.URLParameters(settings.RABBITMQ_URL)
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            self.channel.exchange_declare(exchange=self.exchange, exchange_type='topic', durable=True)
            logger.info("Connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")

    def publish(self, routing_key: str, payload: dict):
        if not self.channel or self.channel.is_closed:
            self.connect()

        if self.channel:
            try:
                self.channel.basic_publish(
                    exchange=self.exchange,
                    routing_key=routing_key,
                    body=json.dumps(payload),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # make message persistent
                        content_type='application/json'
                    )
                )
                logger.info(f"Published event {routing_key}")
            except Exception as e:
                logger.error(f"Failed to publish event: {e}")

    def close(self):
        if self.connection and not self.connection.is_closed:
            self.connection.close()

publisher = EventPublisher()
