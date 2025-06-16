from flask import Blueprint

finance_bp = Blueprint('finance', __name__, url_prefix='/api/finance')

from . import routes
