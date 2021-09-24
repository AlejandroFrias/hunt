import shutil
import sys
import os
import tempfile
from collections import defaultdict
from subprocess import call
from contextlib import redirect_stdout
from io import StringIO

import sqlite3
from rich import box
from rich.console import Console
from rich.table import Table

from hunt import settings
from .cli_dispatcher import Dispatcher
from .constants import CURRENT
from .constants import FINISHED
from .constants import HuntError
from .constants import HuntCouldNotFindTaskError
from .constants import IN_PROGRESS
from .constants import STATUSES
from .constants import TODO
from .hunt import History
from .hunt import Hunt
from .utils import calc_progress
from .utils import display_progress
from .utils import needs_init
from .utils import parse_task

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
        init                Initialize database
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

    def init(self, options, console):
        """Initialize hunt database


        Usage:
            init
        """
        # check if db and hunt dir exist already exists
        if not needs_init():
            prompt = f"Are you sure you want to re-initialize and lose all tracking info? [yN]"
            user_sure = input(prompt).lower() == "y"
            if not user_sure:
                console.print("Aborting re-initialization")
                return
            shutil.rmtree(settings.HUNT_DIR)
        os.mkdir(settings.HUNT_DIR)
        conn = sqlite3.connect(settings.DATABASE)
        conn.execute("CREATE TABLE tasks(id INTEGER PRIMARY KEY, name TEXT, estimate INTEGER, description TEXT, status TEXT, last_modified INTEGER)")
        conn.execute("CREATE TABLE history(id INTEGER PRIMARY KEY, taskid INTEGER, is_start BOOLEAN, time INTEGER)")
        conn.commit()
        conn.close()

    # flake8: noqa
    def ls(self, options, console):
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
        if options.get("--all"):
            statuses.update(STATUSES)
        if options.get("--open"):
            statuses.update([CURRENT, IN_PROGRESS, TODO])
        if options.get("--started"):
            statuses.update([CURRENT, IN_PROGRESS])
        if options.get("--current"):
            statuses.add(CURRENT)
        if options.get("--in-progress"):
            statuses.add(IN_PROGRESS)
        if options.get("--todo"):
            statuses.add(TODO)
        if options.get("--finished"):
            statuses.add(FINISHED)
        if not statuses:
            statuses.update([CURRENT, IN_PROGRESS, TODO])

        # Get the filtered and sorted list of tasks to display
        hunt = Hunt()
        tasks = hunt.get_tasks(
            statuses, starts_with=options.get("--starts-with"), contains=options.get("--contains")
        )

        # Calculate progress from history
        history_records = hunt.get_history([task.id for task in tasks])
        taskid2history = defaultdict(list)
        for record in history_records:
            taskid2history[record.taskid].append(record)
        taskid2progress = defaultdict(int)
        for taskid, task_history in taskid2history.items():
            taskid2progress[taskid] = calc_progress(task_history)

        # Pretty diplay in a table with colors
        table = Table(
            "ID",
            "NAME",
            "ESTIMATE",
            "PROGRESS",
            "STATUS",
            box=box.MINIMAL_HEAVY_HEAD,
        )
        for rowid, task in enumerate(tasks):
            seconds = taskid2progress[task.id]
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            row = (
                str(task.id),
                task.name,
                task.estimate_display,
                display_progress(taskid2progress[task.id]),
                task.status,
            )
            style = None
            if task.status == CURRENT:
                style = "green"
            elif task.status == IN_PROGRESS:
                style = "yellow"
            table.add_row(*row, style=style)
        console.print(table)

    def show(self, options, console):
        """
        Display task.

        Usage:
            show [<task-identifier>]
        """
        hunt = Hunt()
        if options["<task-identifier>"]:
            task = hunt.get_task(options["<task-identifier>"])
        else:
            task = hunt.get_current_task()
        console.print(hunt.display_task(task.id))

    def create(self, options, console):
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
            options["<task-name>"],
            estimate=options["--estimate"],
            description=options["--description"],
        )
        self.ls({"--starts-with": task.name}, console=console)

    def workon(self, options, console):
        """
        Start/continue working on an unfinished task.

        Usage:
            workon [<task-identifier>] [options]

        Options:
            -c, --create                        Attempt to create task first
            -e, --estimate=<estimate>           [Only for create] Add estimate (in hours)
            -d, --description=<description>     [Only for create] Add a description
        """
        hunt = Hunt()
        try:
            task = hunt.get_task(
                options["<task-identifier>"] or "$CURRENT", statuses=[CURRENT, IN_PROGRESS, TODO]
            )
        except HuntCouldNotFindTaskError:
            if options["--create"]:
                task = hunt.create_task(
                    options["<task-identifier>"],
                    estimate=options["--estimate"],
                    description=options["--description"],
                )
            else:
                raise

        if options["--create"] and task.name != options["<task-identifier>"]:
            task = hunt.create_task(
                options["<task-identifier>"],
                estimate=options["--estimate"],
                description=options["--description"],
            )

        hunt.workon_task(task.id)
        self.ls({"--open": True}, console=console)

    def restart(self, options, console):
        """
        Restart a finished task (progress will continue from before).

        Usage:
            restart <task-identifier>
        """
        hunt = Hunt()
        task = hunt.get_task(options["<task-identifier>"], statuses=[FINISHED])
        if task:
            hunt.workon_task(task.id)
        self.ls({"--open": True}, console=console)

    def stop(self, options, console):
        """
        Stop working on current task.

        Usage:
            stop
        """
        hunt = Hunt()
        hunt.stop_current_task()
        self.ls({"--open": True}, console=console)

    def finish(self, options, console):
        """
        Finish a task (defaults to finish current task).

        Usage:
            finish [<task-identifier>]
        """
        hunt = Hunt()
        task = None
        if options["<task-identifier>"]:
            task = hunt.get_task(options["<task-identifier>"])
        else:
            task = hunt.stop_current_task()

        hunt.finish_task(task.id)
        console.print("Finished [yellow]{task.name}[/yellow]!")

    def estimate(self, options, console):
        """
        Estimate how long a task will take.

        Usage:
            estimate <estimate> [options]

        Options:
            -t, --task-identifier=STRING     Specifiy task
        """
        hunt = Hunt()
        estimate = int(options["<estimate>"])
        task_identifier = options["--task-identifier"]
        if task_identifier:
            task = hunt.get_task(task_identifier)
        else:
            task = hunt.get_current_task()

        taskid = task.id
        task_name = task.name
        hunt.estimate_task(taskid, estimate)
        task = hunt.get_task(task.id)
        console.print(
            f"[green]{task_name}[/green] estimated to take [yellow]{task.estimate_display}[/yellow]"
        )

    def edit(self, options, console):
        """
        Edit a task. Use with caution.

        Usage:
            edit [<task-identifier>]
        """
        hunt = Hunt()
        if options["<task-identifier>"]:
            task = hunt.get_task(options["<task-identifier>"])
        else:
            task = hunt.get_current_task()

        if not task:
            console.print(
                "Could not find task '" + (options["<task-identifier>"] or "Current") + "'"
            )
            return

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tmp") as tf:
            tf.write(hunt.display_task(task.id))
            tf.flush()
            call([settings.EDITOR, tf.name])

            with open(tf.name, mode="r") as tf:
                tf.seek(0)
                edit = tf.read()

        task_dict = parse_task(edit)
        hunt.remove_task(task.id)
        new_task = hunt.create_task(
            task_dict["name"], task_dict["estimate"], task_dict["description"]
        )
        hunt.update_task(new_task.id, "status", task_dict["status"])
        for is_start, history_time in task_dict["history"]:
            hunt.insert_history(History((None, new_task.id, is_start, history_time)))

        self.ls({"--starts-with": new_task.name, "--all": True}, console=console)

    def rm(self, options, console):
        """
        Remove/delete a task.

        Usage:
            rm <task-identifier> [options]

        Options:
            -f, --force         No confirmation prompt
        """
        hunt = Hunt()
        task = hunt.get_task(options["<task-identifier>"])

        if options["--force"]:
            user_unsure = False
        else:
            prompt = f"Are you sure you want to remove [red]{task.name}[/red]!? [yN]"
            user_unsure = input(prompt).lower() == "n"

        if user_unsure:
            console.print(f"Didn't remove [yellow]{task.name}[/yellow].")
        else:
            hunt.remove_task(task.id)
            console.print(f"Removed [red]{task.name}[/red]!")


def main():
    dispatcher = Dispatcher(Command(), {"options_first": True, "version": "0.0.0"})

    options, handler, command_options = dispatcher.parse(sys.argv[1:])

    if command_options["--silent"]:
        console = Console(file=StringIO())
    else:
        console = Console()

    try:
        handler(options, console=console)
    except KeyboardInterrupt:
        sys.exit(1)
    except HuntError as hunt_error:
        if not command_options["--silent"]:
            console.print(str(hunt_error))
        sys.exit(hunt_error.exit_status)
