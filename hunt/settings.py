from os import environ
from os import path


HUNT_DIR = path.expanduser(environ.get('HUNT_DIRECTORY', '~/.hunt'))
DATABASE = path.join(
    HUNT_DIR, environ.get('DATABASE_NAME', 'database.db'))
EDITOR = environ.get('EDITOR', 'vim')
