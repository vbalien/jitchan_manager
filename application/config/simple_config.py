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
