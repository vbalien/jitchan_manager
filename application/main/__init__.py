from flask import Blueprint
from flask import render_template

main_blueprint = Blueprint(
    'main', __name__, url_prefix='/', template_folder='templates')


@main_blueprint.route('/')
def index():
    return render_template('main/index.html')
