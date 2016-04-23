from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import send_file
from flask import session
from flask import url_for

from application.ani.utils import is_loggedin
from application.ani.utils import only_loggedin
from application.ani.utils import valid_login

from application import db

from application.ani.model import Animation
from application.ani.model import Episode

ani_blueprint = Blueprint(
    'ani', __name__, url_prefix='/ani', template_folder='templates')


@ani_blueprint.route('/')
def index():
    anilist = db.session.query(Animation).all()
    return render_template('ani/index.html', loggedin=is_loggedin(), anilist=anilist)


@ani_blueprint.route('/<int:animation_id>')
def episodes(animation_id):
    ani = db.session.query(Animation).filter(Animation.id == animation_id).first()
    return render_template('ani/episodes.html', loggedin=is_loggedin(), ani=ani)


@ani_blueprint.route('/<int:animation_id>/<int:ep_num>')
def episode_view(animation_id, ep_num):
    episode = db.session.query(Episode).filter(
        db.and_(Episode.animation_id == animation_id, Episode.ep_num == ep_num)
    ).first()
    return render_template('ani/episode_view.html', loggedin=is_loggedin(), ani=episode.animation, ep=episode)


@ani_blueprint.route('/<int:animation_id>/<int:ep_num>/video')
def episode_video(animation_id, ep_num):
    episode = db.session.query(Episode).filter(
        db.and_(Episode.animation_id == animation_id, Episode.ep_num == ep_num)
    ).first()
    return send_file(
        episode.video_path,
        mimetype='video/*'
    )


@ani_blueprint.route('/<int:animation_id>/<int:ep_num>/sync')
def episode_sync(animation_id, ep_num):
    episode = db.session.query(Episode).filter(
        db.and_(Episode.animation_id == animation_id, Episode.ep_num == ep_num)
    ).first()
    return send_file(
        episode.sync_path,
        mimetype='text/vtt'
    )


@ani_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    error = ''
    redirect_url = request.args.get('redirect_url', url_for('ani.index'))
    if 'ani_username' in session:  # loggedin
        return redirect(redirect_url)
    if request.method == 'POST':
        if valid_login(request.form['username'],
                       request.form['password']):
            session['ani_username'] = request.form['username']
            return redirect(redirect_url)
        else:
            error = '로그인 실패'
    return render_template('ani/login.html', error=error)


@ani_blueprint.route('/logout', methods=['GET'])
def logout():
    session.pop('ani_username', None)
    return redirect(url_for('ani.index'))


@ani_blueprint.route('/register', methods=['GET', 'POST'])
def register():
    only_loggedin()
    if request.method == 'POST':
        ani = Animation(
            title=request.form['title'],
            query=request.form['query'],
            sync_index=request.form['sync_index'],
        )
        db.session.add(ani)
        db.session.commit()
        return redirect(url_for('ani.index'))
    return render_template('ani/register.html')


@ani_blueprint.errorhandler(403)
def page_403(e):
    return redirect(url_for('ani.login', redirect_url=request.path))
