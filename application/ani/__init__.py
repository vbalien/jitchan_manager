from flask import Blueprint
from flask import render_template

ani_blueprint = Blueprint(
    'ani', __name__, url_prefix='/ani', template_folder='templates')


@ani_blueprint.route('/')
def aniindex():
    return render_template('ani/index.html')
