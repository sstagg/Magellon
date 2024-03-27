import pika


class RabbitMQClient:
    def __init__(self, host='localhost', port=5672, username='guest', password='guest'):
        self.connection = None
        self.channel = None
        self.host = host
        self.port = port
        self.credentials = pika.PlainCredentials(username, password)

    def connect(self):
        try:
            parameters = pika.ConnectionParameters(self.host, self.port, '/', self.credentials)
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            print(f"Connected to RabbitMQ server at {self.host}:{self.port}")
        except pika.exceptions.AMQPConnectionError as e:
            print(f"Error connecting to RabbitMQ: {e}")

    def close_connection(self):
        if self.connection and self.connection.is_open:
            self.connection.close()
            print("Connection to RabbitMQ closed.")

    def declare_queue(self, queue_name):
        self.channel.queue_declare(queue=queue_name)
        print(f"Queue '{queue_name}' declared.")

    def publish_message(self, exchange, routing_key, message):
        self.channel.basic_publish(exchange=exchange, routing_key=routing_key, body=message)
        print(f"Message sent: '{message}'")

    def consume_messages(self, queue_name, callback):
        self.channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
        print(f"Consuming messages from queue '{queue_name}'. Press CTRL+C to exit.")
        self.channel.start_consuming()


def message_callback(ch, method, properties, body):
    print(f"Received message: {body}")
