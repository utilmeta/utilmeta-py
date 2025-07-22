from django_demo.asgi import application, PORT


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(application, host='127.0.0.1', port=PORT)
