from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from authlib.integrations.flask_client import OAuth
from flask_mail import Mail

mail = Mail()
db = SQLAlchemy()
migrate = Migrate()
oauth = OAuth()