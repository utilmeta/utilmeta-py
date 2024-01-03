from config.service import service

app = service.application()

if __name__ == '__main__':
    service.run()