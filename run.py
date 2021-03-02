from app.message_queue import receive

# listen exchange is SDP
# publish exchange is OCR
if __name__ == "__main__":
    server_config = receive.RabbitMQServerConfiguration()
    server = receive.RabbitMQServer(config=server_config)
    server.start()
