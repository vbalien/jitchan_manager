#!/usr/bin/env python3
from flask.ext.script import Command
from flask.ext.script import Manager

from flask.ext.migrate import Migrate
from flask.ext.migrate import MigrateCommand

from application import app
from application import db

from script.ani_downloader import AniDownloader

migrate = Migrate(app, db)
manager = Manager(app)


class DebugCommand(Command):
    def run(self):
        app.run(host='0.0.0.0', port=8000, debug=True)


class RunCommand(Command):
    def run(self):
        app.run(host='0.0.0.0', port=8000, debug=False)


class AniDownCommand(Command):
    def run(self):
        ad = AniDownloader(app, db)
        ad.download()


if __name__ == "__main__":
    manager.add_command('debug', DebugCommand)
    manager.add_command('run', RunCommand)
    manager.add_command('db', MigrateCommand)
    manager.add_command('anidown', AniDownCommand)
    manager.run()
