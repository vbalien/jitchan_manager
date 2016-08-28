from flask import Flask

from flask_sqlalchemy import SQLAlchemy

from application.config.config import Config

# Configure
app = Flask(__name__)
app.config.from_object(Config)

# Extensions
db = SQLAlchemy(app)

# Blueprints
from application.ani import ani_blueprint
from application.main import main_blueprint
app.register_blueprint(main_blueprint, subdomain='test')
app.register_blueprint(ani_blueprint, subdomain='ani')
