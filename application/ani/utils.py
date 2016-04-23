from flask import abort
from flask import current_app
from flask import session


def valid_login(username, password):
    if username == current_app.config['ANI_ADMIN_USERNAME'] and password == current_app.config['ANI_ADMIN_PASSWORD']:
        return True
    return False


def only_loggedin():
    if 'ani_username' not in session:
        abort(403)


def is_loggedin():
    loggedin = False
    if 'ani_username' in session:
        loggedin = True
    return loggedin
