CURRENT = 'Current'
IN_PROGRESS = 'In Progress'
TODO = 'TODO'
FINISHED = 'Finished'
STATUSES = [CURRENT, IN_PROGRESS, TODO, FINISHED]
TASKS_TABLE = 'tasks'
HISTORY_TABLE = 'history'


class HuntError(Exception):
    exit_status = 1


class HuntCouldNotFindTaskError(HuntError):
    exit_status = 2


class HuntAlreadyWorkingOnTaskError(HuntError):
    exit_status = 3


class HuntNoCurrentTaskError(HuntError):
    exit_status = 4


class HuntFoundMultipleTasksError(HuntError):
    exit_status = 5


class HuntTaskValidationError(HuntError):
    exit_status = 6
