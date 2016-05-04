import sys

sys.path.append('/home/vbalien/private/jitchan_manager')

activate_this = '/home/vbalien/private/jitchan_manager/.env/bin/activate_this.py'
exec(open(activate_this).read(), dict(__file__=activate_this))

from application import app as application
