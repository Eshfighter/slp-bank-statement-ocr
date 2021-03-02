import pika
import ssl
import json
import os
from threading import Thread
from queue import Queue

from app.message_queue import send
from app.routes import process_pdf
from app.utils import utils


class RabbitMQServerConfiguration:

    def __init__(self):
        """ Server initialization   """
        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        mq_config_path = os.path.join(base_dir, 'assets', 'mq_configurations', 'mq_config.yaml')
        mq_configuration = utils.load_config(mq_config_path)
        listen_configuration = mq_configuration['listen-configuration']

        self.queue = listen_configuration['queue']
        self.host = listen_configuration['host']
        self.port = listen_configuration['port']
        self.virtual_host = listen_configuration['virtual_host']
        self.username = listen_configuration['username']
        self.password = listen_configuration['password']
        self.routing_key = listen_configuration['routing_key']
        self.exchange = listen_configuration['exchange']

        if 'ssl-configuration' in mq_configuration and 'client_key_password' in mq_configuration['ssl-configuration']:
            self.context = ssl.create_default_context(
                cafile=os.path.join(base_dir, 'assets', 'mq_configurations', 'ca_certificate.pem')
            )
            self.context.check_hostname = False
            self.context.load_cert_chain(certfile=os.path.join(base_dir, 'assets', 'mq_configurations', 'client_certificate.pem'),
                                         keyfile=os.path.join(base_dir, 'assets', 'mq_configurations', 'client_key.pem'),
                                         password=mq_configuration['ssl-configuration']['client_key_password'])
        else:
            self.context = None

        print(self.queue)


class RabbitMQServer:

    def __init__(self, config):
        """
        :param config: Object of class RabbitMQServerConfiguration
        """
        self.config = config
        credentials = pika.PlainCredentials(self.config.username, self.config.password)

        if self.config.context is not None:
            # Enable ssl
            ssl_options = pika.SSLOptions(self.config.context, self.config.host)
            conn_params = pika.ConnectionParameters(
                host=self.config.host,
                port=self.config.port,
                virtual_host=self.config.virtual_host,
                credentials=credentials,
                ssl_options=ssl_options,
                heartbeat=600
            )
        else:
            conn_params = pika.ConnectionParameters(
                host=self.config.host,
                port=self.config.port,
                virtual_host=self.config.virtual_host,
                credentials=credentials,
                heartbeat=600
            )

        self._connection = pika.BlockingConnection(conn_params)
        self._channel = self._connection.channel()
        self._channel.queue_declare(queue=self.config.queue, durable=True)
        exchange_available = self._channel.exchange_declare(exchange=self.config.exchange, exchange_type='topic', durable=True)
        print('exchange created: ' + str(exchange_available))
        self._channel.queue_bind(queue=self.config.queue, exchange=self.config.exchange, routing_key=self.config.routing_key)
        self._channel.basic_qos(prefetch_count=1)

    def callback(self, ch, method, properties, body):
        print('Received payload')
        result = {}
        try:
            payload = body.decode("utf-8")
            payload = json.loads(payload)

            # Sanity check
            if 'bankName' not in payload:
                result = {'Error': 'bankName not in payload'}
                return

            if 'fileId' not in payload:
                result = {'Error': 'fileId not in payload'}
                return

            print('bankName: %s' % str(payload["bankName"]))
            print('fileId : %s' % str(payload["fileId"]))

            # Begin processing
            que = Queue()
            t = Thread(target=lambda q, arg1: q.put(process_pdf.start(arg1)), args=(que, payload))
            t.start()

            # Keep connection alive
            while t.is_alive():
                ch._connection.sleep(1.0)

            t.join()
            result = que.get()
        except Exception as e:
            result = {'Error': 'Unknown error: %s' % e}
        finally:
            # Publish results
            print(self.config.host)
            publish_server = send.RabbitMQConfiguration()
            rabbitmq = send.RabbitMQServer(publish_server)
            rabbitmq.publish(payload=json.dumps(result, ensure_ascii=False))
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def start(self):
        self._channel.basic_consume(
            queue=self.config.queue,
            on_message_callback=lambda ch, method, properties, body: RabbitMQServer.callback(self, ch, method, properties, body),
            auto_ack=False)
        self._channel.start_consuming()
        print("Server started. Waiting for messages...")
