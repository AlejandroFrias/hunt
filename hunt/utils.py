from parsimonious import Grammar
from parsimonious import NodeVisitor
from time import gmtime
from time import strftime
from time import strptime
import calendar
import time

from clint.textui import colored

from hunt.constants import CURRENT
from hunt.constants import FINISHED
from hunt.constants import HuntTaskValidationError
from hunt.constants import IN_PROGRESS
from hunt.constants import TODO

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

grammar = Grammar(r"""
    task = name newline+
           estimate newline+
           status newline+
           description newline+
           history newline*
    name = "NAME:" whitespace? phrase whitespace?
    estimate = "ESTIMATE:" whitespace? int whitespace?
    description = "DESCRIPTION:" whitespace? phrase whitespace?
    status = "STATUS:" whitespace? status_type whitespace?
    status_type = "Current" / "TODO" / "In Progress" / "Finished"
    history = whitespace? "HISTORY" whitespace? newline+
              history_records?
    whitespace = ~"[ \t]+"
    newline = "\n" / "\n\r"
    phrase = word (whitespace word)*
    word = ~"[0-9a-zA-Z.!?&-_]+"
    int = ~"[1-9]\d*" / "None"
    history_records = history_record (next_history_record)*
    history_record = history_record_type whitespace time whitespace?
    next_history_record = newline+ history_record
    history_record_type = "Start" / "Stop"
    time = year "-" month "-" day " " hours ":" minutes ":" seconds
    year = ~"20\d{2}"
    month = ~"0[1-9]" / ~"1[0-2]"
    day = ~"0[1-9]" / ~"1\d" / ~"2\d" / ~"3[0-1]"
    hours = ~"0\d" / ~"1\d" / ~"2[0-3]"
    minutes = ~"[0-5]\d"
    seconds = minutes
    """)


class TaskVisitor(NodeVisitor):
    grammar = grammar

    def visit_task(self, task, children):
        (name, _nl1,
         estimate, _nl2,
         status, _nl3,
         description, _nl4,
         history, _nl5) = children
        return {
            "name": name,
            "estimate": estimate,
            "description": description,
            "history": history[0] if history else history,
            "status": status,
        }

    def visit_name(self, name, children):
        (_name, _ws1, phrase, _ws2) = children
        return phrase

    def visit_estimate(self, estimate, children):
        (_est, _ws1, phrase, _ws2) = children
        return int(phrase) if phrase.isdigit() else None

    def visit_description(self, description, children):
        (_desc, _ws1, phrase, _ws2) = children
        return None if phrase == "None" else phrase

    def visit_status(self, status, children):
        (_status, _ws1, status_type, _ws2) = children
        return status_type

    def visit_status_type(self, node, _children):
        return node.text

    def visit_history(self, history, children):
        (_ws1, _hist, _ws2, _nl, history_records) = children
        return history_records

    def visit_history_records(self, history_records, children):
        (history_record, rest) = children
        records = [history_record]
        records.extend(rest)
        return records

    def visit_history_record(self, history_record, children):
        (history_record_type, _ws1, history_time, _ws2) = children
        return (history_record_type, history_time)

    def visit_next_history_record(self, node, children):
        (_nl, history_record) = children
        return history_record

    def visit_history_record_type(self, history_record_type, _children):
        return history_record_type.text == "Start"

    def visit_time(self, time, _children):
        return calendar.timegm(strptime(time.text, TIME_FORMAT))

    def visit_phrase(self, phrase, children):
        return phrase.text

    def visit_int(self, node, children):
        return node.text

    def generic_visit(self, node, children):
        return children


def parse_task(task_display):
    task_dict = TaskVisitor().parse(task_display)
    validate_task_dict(task_dict)
    return task_dict


def hunt_assert(expr, message):
    if not expr:
        error_message = colored.red("Task Validation Error: ") + message
        raise HuntTaskValidationError(error_message)


def validate_task_dict(task_dict):
    if task_dict['status'] == TODO:
        hunt_assert(
            len(task_dict['history']) == 0,
            "Can't have a history if the status is TODO")
    else:
        hunt_assert(
            len(task_dict['history']) > 0,
            "Must have a history if status is %s" % task_dict['status'])

    if task_dict['status'] == CURRENT:
        last_history_record = task_dict['history'][-1]
        hunt_assert(
            last_history_record[0] is True,
            "Last history record must be a Start if the status is Current")
    elif task_dict['status'] in [IN_PROGRESS, FINISHED]:
        last_history_record = task_dict['history'][-1]
        hunt_assert(
            last_history_record[0] is False,
            "Last history record must be a Stop if the status is %s" %
            task_dict['status'])

    if task_dict['history']:
        expect_start = True
        last_history_time = 0
        for is_start, history_time in task_dict['history']:
            hunt_assert(
                last_history_time < history_time,
                "History must be in ascending order by time")
            hunt_assert(
                is_start == expect_start,
                "History must alternate between Start and Stop")
            expect_start = not expect_start
            last_history_time = history_time


def display_time(seconds):
    return strftime(TIME_FORMAT, gmtime(seconds))


def calc_progress(task_history):
    progress = 0
    start_time = None
    for history_record in task_history:
        if bool(history_record.is_start):
            start_time = history_record.time
        else:
            progress += history_record.time - start_time
            start_time = None
    if task_history and start_time:
        progress += int(time.time()) - start_time
    return progress


def display_progress(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return "{0:02d}:{1:02d}:{2:02d}".format(hours, minutes, seconds)
