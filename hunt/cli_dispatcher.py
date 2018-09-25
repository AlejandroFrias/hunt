"""
Based on docker-compose.
"""
from inspect import getdoc

from docopt import docopt
from docopt import DocoptExit


class Dispatcher:
    def __init__(self, command, options):
        self.command = command
        self.options = options

    def parse(self, argv):
        command_doc = getdoc(self.command)
        command_options = _docopt(command_doc, argv, **self.options)
        sub_command = command_options['COMMAND']

        if sub_command is None:
            raise SystemExit(command_doc)

        command_attrs = filter(
            lambda a: not a.startswith('__'), dir(self.command))
        sub_command_name = None
        for attr in command_attrs:
            if attr.startswith(sub_command.replace('-', '_')):
                if sub_command_name:
                    raise AmbiguousCommand(sub_command, self)
                sub_command_name = attr

        if not sub_command_name:
            raise NoSuchCommand(sub_command, self)

        sub_command_handler = getattr(self.command, sub_command_name)
        sub_command_doc = getdoc(sub_command_handler)

        if sub_command_doc is None:
            raise NoSuchCommand(sub_command, self)

        sub_command_options = _docopt(
            sub_command_doc,
            command_options['ARGS'],
        )
        return sub_command_options, sub_command_handler, command_options


def _docopt(doc, *args, **kwargs):
    try:
        return docopt(doc, *args, **kwargs)
    except DocoptExit:
        raise SystemExit(doc)


class NoSuchCommand(Exception):
    def __init__(self, command, supercommand):
        super(NoSuchCommand, self).__init__("No such command: %s" % command)

        self.command = command
        self.supercommand = supercommand


class AmbiguousCommand(Exception):
    def __init__(self, command, supercommand):
        super(AmbiguousCommand, self).__init__(
            "Ambiguous command: %s" % command)

        self.command = command
        self.supercommand = supercommand
