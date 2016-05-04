from application import app
from application import db
from datetime import datetime
from os.path import isfile


class Animation(db.Model):
    __tablename__ = 'animation'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    synonyms = db.Column(db.String(100), default=None)
    query = db.Column(db.String(100), nullable=False)
    sync_index = db.Column(db.Integer)
    release_datetime = db.Column(db.DateTime)
    end_date = db.Column(db.Date, default=None)
    week = db.Column(db.Integer, nullable=False)
    update_time = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
    latest_ep_num = db.Column(db.Integer, default=0)

    episodes = db.relationship(
        'Episode',
        backref='animation',
        lazy='dynamic',
        foreign_keys='Episode.animation_id',
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return '<Animation %r>' % self.title


class Episode(db.Model):
    __tablename__ = 'episode'
    id = db.Column(db.Integer, primary_key=True)
    animation_id = db.Column(db.Integer, db.ForeignKey('animation.id'), nullable=False)
    torrent_id = db.Column(db.Integer)
    ep_num = db.Column(db.Integer, nullable=False)
    # sync_path = db.Column(db.String(300))
    # video_path = db.Column(db.String(300), nullable=False)
    filename = db.Column(db.String(200), default=None)
    video_ext = db.Column(db.String(10), default=None)
    upload_time = db.Column(db.DateTime, default=datetime.now())
    view_count = db.Column(db.Integer, default=0)

    def hasSync(self):
        if isfile(self.getSyncFullPath()):
            return True
        else:
            return False

    def getSyncFullPath(self):
        return '{path}/{title}/{filename}.vtt'.\
            format(
                path=app.config['ANI_SYNC_DIR'],
                title=self.animation.synonyms,
                filename=self.filename
            )

    def getVideoURL(self):
        return 'http://test.alien.moe:81/{title}/{filename}.{ext}'.\
            format(
                title=self.animation.synonyms,
                filename=self.filename,
                ext=self.video_ext
            )

    def __repr__(self):
        return '<Episode animation=%r, ep_num=%r>' % (self.animation, self.ep_num)
