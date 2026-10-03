from waitress import serve
from ppj_system.wsgi import application

if __name__ == '__main__':
    print("Server PPJ berjalan di http://192.168.1.9:8000")
    serve(application, host='192.168.1.9', port=8000, threads=6)