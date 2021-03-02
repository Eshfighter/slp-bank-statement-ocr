import pika
import ssl
import os
from app.utils import utils


class RabbitMQConfiguration:

    def __init__(self):
        """ Configure Rabbit Mq Server  """
        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        mq_config_path = os.path.join(base_dir, 'assets', 'mq_configurations', 'mq_config.yaml')
        mq_configuration = utils.load_config(mq_config_path)
        publish_configuration = mq_configuration['publish-configuration']

        self.queue = publish_configuration['queue']
        self.host = publish_configuration['host']
        self.port = publish_configuration['port']
        self.virtual_host = publish_configuration['virtual_host']
        self.username = publish_configuration['username']
        self.password = publish_configuration['password']
        self.routing_key = publish_configuration['routing_key']
        self.exchange = publish_configuration['exchange']

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

    __slots__ = ["config", "_channel", "_connection"]

    def __init__(self, config):
        """
        :param config: Object of class RabbitMQConfiguration
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
        self._channel.queue_bind(queue=self.config.queue, exchange=self.config.exchange, routing_key=self.config.routing_key)

    def publish(self, payload=None):
        """
        :param payload: JSON payload
        :return: None
        """
        if not payload:
            # TODO: Proper error implementation
            payload = {}

        self._channel.basic_publish(exchange=self.config.exchange, routing_key=self.config.routing_key, body=payload)
        print("Published Message")
        self._connection.close()
