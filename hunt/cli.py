import settings
import sys
import tempfile
from collections import defaultdict
from subprocess import call
from contextlib import redirect_stdout
from io import StringIO

from clint.textui import colored
from clint.textui import puts
from clint.textui import puts_err
from clint.textui.prompt import yn
from tabulate import tabulate

from hunt.cli_dispatcher import Dispatcher
from hunt.constants import CURRENT
from hunt.constants import FINISHED
from hunt.constants import HuntError
from hunt.constants import HuntCouldNotFindTaskError
from hunt.constants import IN_PROGRESS
from hunt.constants import STATUSES
from hunt.constants import TODO
from hunt.hunt import History
from hunt.hunt import Hunt
from hunt.utils import calc_progress
from hunt.utils import display_progress
from hunt.utils import parse_task


class Command:
    """
    An interactive todo list.

    Usage:
        hunt [options] [COMMAND] [ARGS...]

    Options:
        -v, --version       Print version and exit
        -h, --help          Print usage and exit
        -s, --silent        Silently run without output (useful for scripts)

    Commands:
        ls                  List tasks
        show                Display task
        create              Create task
        workon              Start/continue working on a task
        stop                Stop working on current task
        finish              Finish a task
        estimate            Estimate how long task will take
        restart             Restart a finished task
        edit                Edit a task
        rm                  Remove task
    """

    # flake8: noqa
    def ls(self, options, stream):
        """
        List tasks.

        Usage:
            ls [options]

        Options:
            -a, --all                   List all tasks (short for -citf)
            -o, --open                  List all open tasks (short for -cit)
            -s, --started               List all started tasks (short for -ci)
            -c, --current               List all Current tasks
            -i, --in-progress           List all In Progress tasks
            -t, --todo                  List all TODO tasks
            -f, --finished              List all Finished tasks
            -S, --starts-with=STRING    Only tasks that start with STRING
            -C, --contains=STRING       Only tasks that contain STRING
        """
        statuses = set()
        if options.get('--all'):
            statuses.update(STATUSES)
        if options.get('--open'):
            statuses.update([CURRENT, IN_PROGRESS, TODO])
        if options.get('--started'):
            statuses.update([CURRENT, IN_PROGRESS])
        if options.get('--current'):
            statuses.add(CURRENT)
        if options.get('--todo'):
            statuses.add(TODO)
        if options.get('--finished'):
            statuses.add(FINISHED)
        if not statuses:
            statuses.update([CURRENT, IN_PROGRESS, TODO])

        # Get the filtered and sorted list of tasks to display
        hunt = Hunt()
        tasks = hunt.get_tasks(
            statuses,
            starts_with=options.get('--starts-with'),
            contains=options.get('--contains'))

        # Calculate progress from history
        history_records = hunt.get_history([task.id for task in tasks])
        taskid2history = defaultdict(list)
        for record in history_records:
            taskid2history[record.taskid].append(record)
        taskid2progress = defaultdict(int)
        for taskid, task_history in taskid2history.items():
            taskid2progress[taskid] = calc_progress(task_history)

        # Pretty diplay in a table with colors
        display_rows = []
        current_rows = []
        in_progress_rows = []
        for rowid, task in enumerate(tasks):
            seconds = taskid2progress[task.id]
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            display_rows.append(
                (task.id, task.name, task.estimate_display,
                 display_progress(taskid2progress[task.id]),
                 task.status, task.last_modified_display))
            if task.status == CURRENT:
                current_rows.append(rowid)
            if task.status == IN_PROGRESS:
                in_progress_rows.append(rowid)

        table_rows = tabulate(
            display_rows,
            headers=['ID', 'NAME', 'ESTIMATE', 'PROGRESS',
                     'STATUS', 'LAST MODIFIED']).split('\n')

        for rowid in current_rows:
            table_rows[rowid + 2] = colored.green(table_rows[rowid + 2])

        for rowid in in_progress_rows:
            table_rows[rowid + 2] = colored.yellow(table_rows[rowid + 2])

        for row in table_rows:
            puts(row, stream=stream)

    def show(self, options, stream):
        """
        Display task.

        Usage:
            show [<task-identifier>]
        """
        hunt = Hunt()
        if options['<task-identifier>']:
            task = hunt.get_task(options['<task-identifier>'])
        else:
            task = hunt.get_current_task()
        puts(hunt.display_task(task.id), stream=stream)

    def create(self, options, stream):
        """
        Create a new task.

        Usage:
            create <task-name> [options]

        Options:
            -e, --estimate=<estimate>           Add estimate (in hours)
            -d, --description=<description>     Add a description
        """
        hunt = Hunt()
        task = hunt.create_task(
            options['<task-name>'],
            estimate=options['--estimate'],
            description=options['--description'])
        self.ls({'--starts-with': task.name}, stream=stream)

    def workon(self, options, stream):
        """
        Start/continue working on an unfinished task.

        Usage:
            workon <task-identifier> [options]

        Options:
            -c, --create                        Attempt to create task first
            -e, --estimate=<estimate>           [Only for create] Add estimate (in hours)
            -d, --description=<description>     [Only for create] Add a description
        """
        hunt = Hunt()
        try:
            task = hunt.get_task(
                options['<task-identifier>'],
                statuses=[CURRENT, IN_PROGRESS, TODO])
        except HuntCouldNotFindTaskError:
            if options['--create']:
                task = hunt.create_task(
                    options['<task-identifier>'],
                    estimate=options['--estimate'],
                    description=options['--description'])
            else:
                raise

        if options['--create'] and task.name != options['<task-identifier>']:
            task = hunt.create_task(
                options['<task-identifier>'],
                estimate=options['--estimate'],
                description=options['--description'])

        hunt.workon_task(task.id)
        self.ls({'--open': True}, stream=stream)

    def restart(self, options, stream):
        """
        Restart a finished task (progress will continue from before).

        Usage:
            restart <task-identifier>
        """
        hunt = Hunt()
        task = hunt.get_task(
            options['<task-identifier>'],
            statuses=[FINISHED])
        if task:
            hunt.workon_task(task.id)
        self.ls({'--open': True}, stream=stream)

    def stop(self, options, stream):
        """
        Stop working on current task.

        Usage:
            stop
        """
        hunt = Hunt()
        hunt.stop_current_task()
        self.ls({'--open': True}, stream=stream)

    def finish(self, options, stream):
        """
        Finish a task (defaults to finish current task).

        Usage:
            finish [<task-identifier>]
        """
        hunt = Hunt()
        task = None
        if options['<task-identifier>']:
            task = hunt.get_task(options['<task-identifier>'])
        else:
            task = hunt.stop_current_task()

        hunt.finish_task(task.id)
        puts("Finished " + colored.yellow(task.name) + "!", stream=stream)

    def estimate(self, options, stream):
        """
        Estimate how long a task will take.

        Usage:
            estimate <estimate> [options]

        Options:
            -t, --task-identifier=STRING     Specifiy task
        """
        hunt = Hunt()
        estimate = int(options['<estimate>'])
        task_identifier = options['--task-identifier']
        if task_identifier:
            task = hunt.get_task(task_identifier)
        else:
            task = hunt.get_current_task()

        taskid = task.id
        task_name = task.name
        hunt.estimate_task(taskid, estimate)
        task = hunt.get_task(task.id)
        puts("{task} estimated to take {estimate}".format(
                task=colored.green(task_name),
                estimat=colored.yellow(task.estimate_display)
            ), stream=stream)

    def edit(self, options, stream):
        """
        Edit a task. Use with caution.

        Usage:
            edit [<task-identifier>]
        """
        hunt = Hunt()
        if options['<task-identifier>']:
            task = hunt.get_task(options['<task-identifier>'])
        else:
            task = hunt.get_current_task()

        if not task:
            puts("Could not find task '" + (options['<task-identifier>'] or "Current") + "'",
                 stream=stream)
            return

        with tempfile.NamedTemporaryFile(mode='w', suffix=".tmp") as tf:
            tf.write(hunt.display_task(task.id))
            tf.flush()
            call([settings.EDITOR, tf.name])

            with open(tf.name, mode='r') as tf:
                tf.seek(0)
                edit = tf.read()

        task_dict = parse_task(edit)
        hunt.remove_task(task.id)
        new_task = hunt.create_task(
            task_dict['name'], task_dict['estimate'], task_dict['description'])
        hunt.update_task(new_task.id, "status", task_dict['status'])
        for is_start, history_time in task_dict['history']:
            hunt.insert_history(
                History((None, new_task.id, is_start, history_time)))

        self.ls({'--starts-with': new_task.name, "--all": True}, stream=stream)

    def rm(self, options, stream):
        """
        Remove/delete a task.

        Usage:
            rm <task-identifier> [options]

        Options:
            -f, --force         No confirmation prompt
        """
        hunt = Hunt()
        task = hunt.get_task(options['<task-identifier>'])

        if options['--force']:
            user_unsure = False
        else:
            prompt = ("Are you sure you want to remove " +
                      colored.red(task.name) + "!?")
            user_unsure = yn(prompt, default='n')

        if user_unsure:
            puts("Didn't remove " + colored.yellow(task.name) + ".", stream=stream)
        else:
            hunt.remove_task(task.id)
            puts("Removed " + colored.red(task.name) + "!", stream=stream)


def main():
    dispatcher = Dispatcher(Command(), {'options_first': True, 'version': '0.0.0'})

    options, handler, command_options = dispatcher.parse(sys.argv[1:])

    try:
        if command_options['--silent']:
            handler(options, stream=StringIO)
        else:
            handler(options, stream=sys.stdout.write)
    except KeyboardInterrupt:
        sys.exit(1)
    except HuntError as hunt_error:
        if not command_options['--silent']:
            puts_err(str(hunt_error))
        sys.exit(hunt_error.exit_status)
