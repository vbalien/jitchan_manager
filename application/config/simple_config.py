class Config(object):
    # base config
    SECRET_KEY = 'development'

    # Database
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///tmp/test.db'

    # Transmission
    TRANSMISSION_HOST = 'localhost'
    TRANSMISSION_PORT = 9091
    TRANSMISSION_USER = None
    TRANSMISSION_PASSWORD = None

    # Ani
    ANI_ADMIN_USERNAME = 'admin'
    ANI_ADMIN_PASSWORD = 'admin'
    ANI_DOWNLOAD_DIR = '/tmp'
    ANI_SYNC_DIR = '/tmp'
