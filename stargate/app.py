from .core_api import API
import os
from .extentions import configure_extensions
from .entity_manager.models import db
from .api import api_blueprint
from flask import Flask

def create_app(config):
    app = Flask(__name__)
    app.config.from_object(config)
    # configure_extensions(app)
    # app.register_blueprint(api_blueprint)
    return app