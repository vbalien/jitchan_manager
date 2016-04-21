from application.config.config import Config
from application.main import main_blueprint
from application.ani import ani_blueprint
from flask import Flask
from flask_sqlalchemy import SQLAlchemy


# Configure
app = Flask(__name__)
app.config.from_object(Config)

# Extensions
db = SQLAlchemy(app)

# Blueprints
app.register_blueprint(main_blueprint)
app.register_blueprint(ani_blueprint)
