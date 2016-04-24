from application import db
from datetime import datetime


class Animation(db.Model):
    __tablename__ = 'animation'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    query = db.Column(db.String(100), nullable=False)
    sync_index = db.Column(db.Integer)
    release_datetime = db.Column(db.DateTime)
    week = db.Column(db.Integer, nullable=False)
    update_time = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
    latest_ep_num = db.Column(db.Integer, default=0)

    episodes = db.relationship(
        'Episode',
        backref='animation',
        lazy='dynamic',
        foreign_keys='Episode.animation_id'
    )

    def __repr__(self):
        return '<Animation %r>' % self.title


class Episode(db.Model):
    __tablename__ = 'episode'
    id = db.Column(db.Integer, primary_key=True)
    animation_id = db.Column(db.Integer, db.ForeignKey('animation.id'), nullable=False)
    torrent_id = db.Column(db.Integer)
    ep_num = db.Column(db.Integer, nullable=False)
    sync_path = db.Column(db.String(100))
    video_path = db.Column(db.String(100), nullable=False)
    upload_time = db.Column(db.DateTime, default=datetime.now())
    view_count = db.Column(db.Integer, default=0)
