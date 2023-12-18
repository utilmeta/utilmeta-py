from config.service import service

service.mount('service.api.RootAPI', route='/api')
app = service.application()

if __name__ == '__main__':
    service.run()