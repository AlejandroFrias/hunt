import settings
import sqlite3
import time
from datetime import datetime
from contextlib import contextmanager
from functools import total_ordering

from clint.textui import colored

from hunt.constants import CURRENT
from hunt.constants import FINISHED
from hunt.constants import HISTORY_TABLE
from hunt.constants import HuntAlreadyWorkingOnTaskError
from hunt.constants import HuntCouldNotFindTaskError
from hunt.constants import HuntFoundMultipleTasksError
from hunt.constants import HuntNoCurrentTaskError
from hunt.constants import IN_PROGRESS
from hunt.constants import STATUSES
from hunt.constants import TASKS_TABLE
from hunt.constants import TODO
from hunt.utils import calc_progress
from hunt.utils import display_time


def now():
    return int(time.mktime(datetime.now().timetuple()))


class Hunt:
    def __init__(self, database=None):
        if database:
            self.database = database
        else:
            self.database = settings.DATABASE

    def get_task(self, task_identifier, statuses=None):
        if isinstance(task_identifier, int) or task_identifier.isdigit():
            where_clause = 'id=?'
            order_by = 'last_modified DESC'
            params = [task_identifier]
        elif task_identifier:
            where_clause = 'name LIKE ?'
            order_by = 'last_modified DESC'
            params = [task_identifier + '%']
        else:
            raise AssertionError("No task identifier given.")

        if statuses:
            where_clause += (
                ' AND status IN (' + ','.join(len(statuses) * '?') + ')')
            params.extend(statuses)

        tasks = self.select_from_task(
            where_clause=where_clause,
            order_by=order_by,
            params=params)

        if len(tasks) == 0:
            raise HuntCouldNotFindTaskError(
                "Could not find task for identifier: " +
                colored.yellow(task_identifier))
        elif len(tasks) > 1:
            raise HuntFoundMultipleTasksError(
                "Found multiple tasks for identifier: " +
                colored.yellow(task_identifier))

        return tasks[0]

    def display_task(self, taskid):
        task = self.get_task(str(taskid))
        task_history = self.get_history(taskid)

        lines = []
        lines.append('NAME: %s' % task.name)
        lines.append('ESTIMATE: %s' % task.estimate)
        lines.append('STATUS: %s' % task.status)
        lines.append('DESCRIPTION: %s' % task.description)
        lines.append('')
        lines.append('HISTORY')
        for history_record in task_history:
            record_type = 'Start' if history_record.is_start else 'Stop'
            lines.append(record_type +
                         '\t' +
                         history_record.get_time_display())
        return "\n".join(lines)

    def create_task(self, name, estimate=None, description=None):
        task = Task((None, name, estimate, description, TODO, now()))
        self.insert_task(task)
        return self.get_task(task.name, statuses=[TODO])

    def get_tasks(self, statuses=None, starts_with=None, contains=None):
        where_clause_param_tuples = []
        if starts_with:
            where_clause_param_tuples.append(
                ('name LIKE ?', (starts_with + '%',)))
        if contains:
            where_clause_param_tuples.append(
                ('name LIKE ?', ('%' + contains + '%',)))
        if statuses:
            where_clause_param_tuples.append(
                ('status IN (' + ','.join(len(statuses) * '?') + ')',
                 statuses))
        if where_clause_param_tuples:
            where_clauses, where_params = zip(*where_clause_param_tuples)
            where_clause = ' AND '.join(where_clauses)
            params = [param for params in where_params for param in params]
        else:
            where_clause = None
            params = None

        tasks = self.select_from_task(
            where_clause=where_clause,
            params=params)
        return sorted(tasks)

    def get_history(self, taskids):
        if isinstance(taskids, int):
            taskids = [taskids]
        assert(all(map(lambda taskid: isinstance(taskid, int), taskids)))

        where_clause = 'taskid IN (' + ','.join(len(taskids) * '?') + ')'
        history = self.select_from_history(
            where_clause=where_clause,
            params=taskids)
        return sorted(history)

    def get_progress(self, taskid):
        history = self.get_history(taskid)
        return calc_progress(history)

    def get_current_task(self, required=True):
        current_tasks = self.select_from_task(
            where_clause='status IN (?)', params=(CURRENT,))
        if len(current_tasks) == 0:
            if required:
                raise HuntNoCurrentTaskError("No current tasks.")
            else:
                return None
        elif len(current_tasks) > 1:
            raise AssertionError("More than one current task? How!?")

        return current_tasks[0]

    def workon_task(self, task_identifier):
        task = self.get_task(task_identifier)
        current_task = self.get_current_task(required=False)
        if current_task:
            if current_task.id == task.id:
                raise HuntAlreadyWorkingOnTaskError("Already working on " + colored.yellow(task.name))
            self.insert_history(History((None, current_task.id, False, now())))
            self.update_task(current_task.id, "status", IN_PROGRESS)
        self.insert_history(History((None, task.id, True, now())))
        self.update_task(task.id, "status", CURRENT)

    def stop_current_task(self):
        current_task = self.get_current_task()
        self.insert_history(History((None, current_task.id, False, now())))
        self.update_task(current_task.id, 'status', IN_PROGRESS)
        return self.get_task(current_task.id)

    def finish_task(self, taskid):
        self.update_task(taskid, "status", FINISHED)

    def estimate_task(self, taskid, estimate):
        self.update_task(taskid, "estimate", estimate)

    def remove_task(self, taskid):
        delete_task_sql = 'DELETE from {table} WHERE id=?'.format(
            table=TASKS_TABLE)
        delete_history_sql = 'DELETE from {table} WHERE taskid=?'.format(
            table=HISTORY_TABLE)
        self.execute(delete_task_sql, (taskid,))
        self.execute(delete_history_sql, (taskid,))

    def update_task(self, taskid, field, value):
        sql = ('UPDATE {table} SET {field}=?, last_modified=? '
               'WHERE id=?').format(
            table=TASKS_TABLE, field=field)
        self.execute(sql, (value, now(), taskid))

    def select_from_task(self, where_clause=None, order_by=None, params=None):
        return self.select_from_table(
            TASKS_TABLE, where_clause, order_by, params)

    def select_from_history(
            self, where_clause=None, order_by=None, params=None):
        return self.select_from_table(
            HISTORY_TABLE, where_clause, order_by, params)

    def select_from_table(
            self, table, where_clause=None, order_by=None, params=None):
        assert(table in (TASKS_TABLE, HISTORY_TABLE))
        sql = 'SELECT * FROM {table}'.format(table=table)
        if where_clause:
            sql += ' WHERE ' + where_clause
        if order_by:
            sql += ' ORDER BY ' + order_by
        if table == TASKS_TABLE:
            record_type = Task
        elif table == HISTORY_TABLE:
            record_type = History
        else:
            raise AssertionError(table + "is not one of the tables")
        return list(map(record_type, self.execute(sql, params)))

    def insert_task(self, task):
        sql = (
            'INSERT INTO {table} '
            '(name,estimate,description,status,last_modified) '
            'VALUES (?,?,?,?,?)').format(table=TASKS_TABLE)
        self.execute(sql, (task.name, task.estimate, task.description,
                           task.status, task.last_modified))

    def insert_history(self, history):
        sql = ('INSERT INTO {table} (taskid,is_start,time) VALUES '
               '(?,?,?)').format(table=HISTORY_TABLE)
        self.execute(sql, (history.taskid, history.is_start, history.time))

    def execute(self, sql, sql_params=None):
        if sql_params is None:
            sql_params = []
        with self.connect() as conn:
            rows = conn.execute(sql, sql_params).fetchall()
        return rows

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.database)
        yield conn
        conn.commit()
        conn.close()


@total_ordering
class Task(object):
    def __init__(self, record):
        self.id = record[0]
        self.name = record[1]
        self.estimate = record[2]
        self.description = record[3]
        self.status = record[4]
        self.last_modified = record[5]

    @property
    def last_modified_display(self):
        return display_time(self.last_modified)

    @property
    def estimate_display(self):
        estimate_display_str = ""
        if self.estimate:
            estimate_display_str = "%d hr" % self.estimate
            if self.estimate > 1:
                estimate_display_str += "s"
        return estimate_display_str

    def __str__(self):
        return "{name} ({status}): {desc}".format(
            name=self.name, status=self.status, desc=self.description)

    def __repr__(self):
        return str(self)

    def __lt__(self, other):
        return ((STATUSES.index(self.status), -self.last_modified) <
                (STATUSES.index(other.status), -other.last_modified))

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id


@total_ordering
class History(object):
    def __init__(self, record):
        self.id = record[0]
        self.taskid = record[1]
        self.is_start = record[2]
        self.time = record[3]

    def get_time_display(self):
        return display_time(self.time)

    def __str__(self):
        return "{id} {verb} at {time}".format(
            id=self.id,
            verb=("Started" if self.is_start else "Stopped"),
            time=self.get_time_display())

    def __repr__(self):
        return str(self)

    def __lt__(self, other):
        return ((self.taskid, self.time, not self.is_start) <
                (other.taskid, other.time, not other.is_start))

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id
