from flask import abort
from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import send_file
from flask import session
from flask import url_for
from flask import make_response

from application.ani.utils import is_loggedin
from application.ani.utils import only_loggedin
from application.ani.utils import valid_login

from application import db

from application.ani.model import Animation
from application.ani.model import Episode

from script.ani_downloader import guess_encoding
from script.ani_downloader import smi2vtt

import os
from os.path import isfile

ani_blueprint = Blueprint(
    'ani', __name__,
    static_folder='static',
    template_folder='templates')


@ani_blueprint.context_processor
def inject_user():
    return dict(loggedin=is_loggedin())


@ani_blueprint.route('/')
def index():
    anilist = db.session.query(Animation).order_by(Animation.week).all()
    return render_template('ani/index.html', anilist=anilist)


@ani_blueprint.route('/podcast.xml')
def all_podcast():
    episodes = db.session.query(Episode).order_by(Episode.upload_time.desc()).all()
    response = make_response(render_template('ani/podcast/all.xml', episodes=episodes))
    response.headers['Content-Type'] = 'application/xml'
    return response


@ani_blueprint.route('/<int:animation_id>')
def episodes(animation_id):
    ani = db.session.query(Animation).filter(Animation.id == animation_id).first()
    return render_template('ani/episodes.html', ani=ani)


@ani_blueprint.route('/<int:animation_id>/podcast.xml')
def episodes_podcast(animation_id):
    ani = db.session.query(Animation).filter(Animation.id == animation_id).first()
    response = make_response(render_template('ani/podcast/episodes.xml', ani=ani))
    response.headers['Content-Type'] = 'application/xml'
    return response


@ani_blueprint.route('/<int:animation_id>/<int:ep_num>')
def episode_view(animation_id, ep_num):
    episode = db.session.query(Episode).filter(
        db.and_(Episode.animation_id == animation_id, Episode.ep_num == ep_num)
    ).first()
    return render_template('ani/episode_view.html', ani=episode.animation, ep=episode)


@ani_blueprint.route('/<int:animation_id>/<int:ep_num>/sync')
def episode_sync(animation_id, ep_num):
    episode = db.session.query(Episode).filter(
        db.and_(Episode.animation_id == animation_id, Episode.ep_num == ep_num)
    ).first()
    return send_file(
        episode.getSyncFullPath(),
        mimetype='text/vtt'
    )


@ani_blueprint.route('/<int:animation_id>/<int:ep_num>/add_sync', methods=['POST'])
def add_sync(animation_id, ep_num):
    only_loggedin()
    episode = db.session.query(Episode).filter(
        db.and_(Episode.animation_id == animation_id, Episode.ep_num == ep_num)
    ).first()
    smi_file = request.files['smi_file']
    smi_data = smi_file.stream.read()
    charset = guess_encoding(smi_data)
    if charset is None:
        return None
    smi_data = smi_data.decode(charset)
    vtt_data = smi2vtt(smi_data)

    # Sync
    # sync_dir = app.config['ANI_SYNC_DIR'] + '/' + episode.animation.query
    # syncname = "{0}/{1}.vtt".format(sync_dir, episode.ep_num)
    # sync_path = "/{0}/{1}.vtt".format(episode.animation.query, episode.ep_num)
    if isfile(episode.getSyncFullPath()):
        os.remove(episode.getSyncFullPath())
    with open(episode.getSyncFullPath(), 'wb') as fp:
        fp.write(vtt_data.encode('utf-8'))
    # episode.sync_path = sync_path
    # db.session.commit()
    return redirect(url_for('ani.episode_view', animation_id=animation_id, ep_num=ep_num))


@ani_blueprint.route('/<int:animation_id>/delete', methods=['GET', 'POST'])
def animation_delete(animation_id):
    only_loggedin()
    ani = db.session.query(Animation).filter(Animation.id == animation_id).first()
    if ani is None:
        abort(404)
    db.session.delete(ani)
    db.session.commit()
    return redirect(url_for('ani.index'))


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
    only_loggedin()
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
            week=request.form['week'],
        )
        db.session.add(ani)
        db.session.commit()
        return redirect(url_for('ani.index'))
    return render_template('ani/register.html')


@ani_blueprint.errorhandler(403)
def page_403(e):
    return redirect(url_for('ani.login', redirect_url=request.path))
