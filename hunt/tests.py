import os
import settings
import shutil
import sqlite3
import tempfile
from unittest import TestCase

from hunt import Hunt


class TestHunt(TestCase):
    def setUp(self):
        hunt_dir = tempfile.mkdtemp()
        self.env = {
            'HUNT_DIRECTORY': hunt_dir,
            'DEFAULT_DATABASE': os.path.join(hunt_dir, 'default_database.db')
        }
        settings.HUNT_DIRECTORY = self.env['HUNT_DIRECTORY']
        settings.DEFAULT_DATABASE = self.env['DEFAULT_DATABASE']
        sqlite3.connect(self.env['DEFAULT_DATABASE'])

    def tearDown(self):
        shutil.rmtree(self.env['HUNT_DIRECTORY'])

    def test_init(self):
        hunt = Hunt()
        self.assertEqual(hunt.database, self.env['DEFAULT_DATABASE'])

        hunt = Hunt('/database.db')
        self.assertEqual(hunt.database, '/database.db')
