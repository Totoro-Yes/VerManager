# MIT License
#
# Copyright (c) 2020 Gcom
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import unittest

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, \
    BinaryIO, Union, Any, Callable
from functools import reduce
from manager.basic.type import Ok, Error, State
from manager.basic.letter import NewLetter, Letter, \
    PostTaskLetter, BinaryLetter
from manager.master.build import BuildSet
from manager.basic.restricts import TASK_ID_MAX_LENGTH, VERSION_MAX_LENGTH, \
    REVISION_MAX_LENGTH

from datetime import datetime
from manager.master.build import Build, Merge

# Need by test
from manager.basic.info import Info

TaskState = int
TaskType = int


class TASK_FORMAT_ERROR(Exception):
    pass


class TASK_TRANSFORM_ERROR(Exception):
    pass


class TaskBase(ABC):

    # Task does not dispatch to any worker.
    STATE_PREPARE = 0

    # Task was dispatch to a worker.
    STATE_IN_PROC = 1

    # Task is done and the result of task has been received.
    STATE_FINISHED = 2

    # Task is failure.
    STATE_FAILURE = 3

    STATE_STR_MAPPING = {
        STATE_PREPARE: "PREPARE",
        STATE_IN_PROC: "IN_PROC",
        STATE_FINISHED: "FIN",
        STATE_FAILURE: "FAIL",
    }

    STATE_TOPOLOGY = {
        STATE_PREPARE: [STATE_PREPARE, STATE_IN_PROC, STATE_FAILURE],
        STATE_IN_PROC: [STATE_IN_PROC, STATE_PREPARE,
                        STATE_FINISHED, STATE_FAILURE],
        STATE_FINISHED: [STATE_PREPARE, STATE_FINISHED, STATE_FAILURE],
        STATE_FAILURE: [STATE_FAILURE]
    }  # type:  Dict[int, List[int]]

    @abstractmethod
    def id(self) -> str:
        """ identity of task """

    @abstractmethod
    def taskState(self) -> TaskState:
        """ State of Task """

    @abstractmethod
    def stateChange(self, state: TaskState) -> State:
        """ Change task's state """

    @abstractmethod
    def isValid(self) -> bool:
        """ To check that is info in this task is valid  """


class Task(TaskBase):

    Type = 0

    def __init__(self, id:  str, sn: str, vsn: str,
                 extra: Dict[str, str] = {}) -> None:

        self.taskId = id

        self.type = Task.Type
        self.sn = sn
        self.vsn = vsn
        self.extra = extra

        # Files that relate to this task
        self._files = None  # type:  Optional[BinaryIO]

        self.state = Task.STATE_PREPARE

        # This field will be set by EventListener while
        # the task is complete by worker and transfer
        # back totally.
        self.data = ""

        self.build = None  # type:  Optional[Union[Build, BuildSet]]

        # Indicate that the number of request to the task
        self.refs = 1

        self.lastAccess = datetime.utcnow()

        # A Variable that reference to the job that
        # the task belong to.
        self.job = None  # type: Any

    def getType(self) -> TaskType:
        return self.type

    def setType(self, type: TaskType) -> None:
        self.type = type

    def getExtra(self) -> Optional[Dict[str, str]]:
        return self.extra

    def getSN(self) -> str:
        return self.sn

    def getVSN(self) -> str:
        return self.vsn

    def id(self) -> str:
        return self.taskId

    def lastUpdate(self) -> None:
        self.lastAccess = datetime.utcnow()

    def last(self) -> datetime:
        return self.lastAccess

    def taskState(self) -> TaskState:
        return self.state

    def setBuild(self, b: Union[Build, BuildSet]) -> None:
        self.build = b

    def isBindWithBuild(self) -> bool:
        return self.build is not None

    def stateChange(self, state: int) -> State:
        ableStates = Task.STATE_TOPOLOGY[self.taskState()]

        if state in ableStates:
            self.state = state
            return Ok
        else:
            return Error

    def toPreState(self) -> State:
        self.state = Task.STATE_PREPARE
        return Ok

    def toProcState(self) -> State:
        return self.stateChange(Task.STATE_IN_PROC)

    def toFinState(self) -> State:
        return self.stateChange(Task.STATE_FINISHED)

    def toFailState(self) -> State:
        return self.stateChange(Task.STATE_FAILURE)

    def setData(self, data:  str) -> None:
        self.data = data

    def isPrepare(self) -> bool:
        return self.state == Task.STATE_PREPARE

    def isProc(self) -> bool:
        return self.state == Task.STATE_IN_PROC

    def isFailure(self) -> bool:
        return self.state == Task.STATE_FAILURE

    def isFinished(self) -> bool:
        return self.state == Task.STATE_FINISHED

    # fixme:  Python 3.5.3 raise an NameError exception:
    #        name 'BinaryIO' is not defined. Temporarily
    #        use Any to instead of BinaryIO
    def file(self) -> Optional[Any]:
        return self._files

    @classmethod
    def state_str_to_int(self, state: str) -> int:
        for i in range(4):
            if state == self.STATE_STR_MAPPING[i]:
                return i

        return -1

    def toLetter(self) -> Letter:
        pass

    @staticmethod
    def isValidState(s: int) -> bool:
        return s >= Task.STATE_PREPARE and s <= Task.STATE_FAILURE

    def isValid(self) -> bool:
        cond1 = len(self.taskId) <= TASK_ID_MAX_LENGTH
        cond2 = len(self.vsn) <= VERSION_MAX_LENGTH
        cond3 = len(self.sn) <= REVISION_MAX_LENGTH
        cond4 = " " not in (self.taskId+self.vsn+self.sn)

        return cond1 and cond2 and cond3 and cond4


class SingleTask(Task):

    Type = 2

    def __init__(self, id: str, sn: str, revision: str,
                 build: Build,
                 needPost: str = 'false',
                 extra: Dict = {}) -> None:

        Task.__init__(self, id, sn, revision, extra)

        self.type = SingleTask.Type
        self._build = build
        self._needPost = needPost

    def isValid(self) -> bool:
        cond1 = len(self.taskId) <= BinaryLetter.TASK_ID_FIELD_LEN
        cond2 = len(self.vsn) <= VERSION_MAX_LENGTH
        cond3 = len(self.sn) <= REVISION_MAX_LENGTH
        cond4 = " " not in (self.taskId+self.vsn+self.sn)

        return cond1 and cond2 and cond3 and cond4

    def toLetter(self) -> NewLetter:
        build = self._build
        extra = {"resultPath": build.getOutput(), "cmds": build.getCmd()}

        for key in self.extra:
            if key not in extra:
                extra[key] = self.extra[key]
            else:
                raise Exception()

        return NewLetter(self.id(), self.sn, self.vsn, str(datetime.utcnow()),
                         parent="",
                         extra=extra,
                         needPost=self._needPost)

    def isBindWithBuild(self) -> bool:
        return self._build is not None


class PostTask(Task):

    Type = 3

    def __init__(self, ident: str, version: str,
                 frags: List[str], merge: Merge) -> None:

        Task.__init__(self, ident, "", version)

        self.type = PostTask.Type
        self._frags = frags
        self._merge = merge

    @staticmethod
    def genIdent(ident: str) -> str:
        return ident+"__Post"

    def isValid(self) -> bool:
        cond1 = len(self.taskId) <= BinaryLetter.TASK_ID_FIELD_LEN
        cond2 = len(self.vsn) <= VERSION_MAX_LENGTH
        cond3 = len(self.sn) <= REVISION_MAX_LENGTH
        cond4 = " " not in (self.taskId+self.vsn+self.sn)

        return cond1 and cond2 and cond3 and cond4

    def toLetter(self) -> PostTaskLetter:
        return PostTaskLetter(
            self.id(), self.vsn, self._merge.getCmds(),
            self._merge.getOutput(), frags=self._frags)


# Every task in TaskGroup must be unique in the TaskGroup
class TaskGroup:
    def __init__(self) -> None:
        # {Type: Tasks}
        self._tasks = {}  # type:  Dict[TaskType, Dict[str, Task]]
        self._numOfTasks = 0

    def newTask(self, task:  Task) -> None:
        type = task.getType()
        tid = task.id()

        if self._isExists(tid):
            return None

        if type not in self._tasks:
            self._tasks[type] = {}

        tasks = self._tasks[type]

        tasks[task.id()] = task

        if not isinstance(task, PostTask):
            self._numOfTasks += 1

    def remove(self, id:  str) -> State:
        return self._remove(id)

    def _remove(self, id: str) -> State:
        for tasks in self._tasks.values():

            if id not in tasks:
                continue

            task = tasks[id]
            del tasks[id]

            if not isinstance(task, PostTask):
                self._numOfTasks -= 1

            return Ok

        return Error

    def _mark(self, id:  str, st:  TaskState) -> State:
        task = self.search(id)
        if task is None:
            return Error
        task.stateChange(st)

        return Ok

    def toList(self) -> List[Task]:
        return self._toList_non_lock()

    def _toList_non_lock(self) -> List[Task]:
        task_dicts = list(self._tasks.values())
        task_lists = list(map(lambda d:  list(d.values()), task_dicts))

        return reduce(lambda acc, cur:  acc + cur, task_lists, [])

    def toList_(self) -> List[str]:
        letter = self.toList()
        l_id = map(lambda t:  t.id(), letter)

        return list(l_id)

    def isExists(self, ident: str) -> bool:
        return self._isExists(ident)

    def _isExists(self, ident: str) -> bool:
        task_dicts = list(self._tasks.values())

        for tasks in task_dicts:
            if id not in tasks:
                continue

            return True

        return False

    def removeTasks(self, predicate: Callable[[Task], bool]) -> None:
        for t in self._toList_non_lock():
            ret = predicate(t)

            if ret is True:
                self._remove(t.id())

    def markPre(self, id:  str) -> State:
        return self._mark(id, Task.STATE_PREPARE)

    def markInProc(self, id: str) -> State:
        return self._mark(id, Task.STATE_IN_PROC)

    def markFin(self, id:  str) -> State:
        return self._mark(id, Task.STATE_FINISHED)

    def markFail(self, id:  str) -> State:
        return self._mark(id, Task.STATE_FAILURE)

    def search(self, id:  str) -> Union[Task, None]:
        tasks_dicts = list(self._tasks.values())

        for tasks in tasks_dicts:
            if id not in tasks:
                continue

            return tasks[id]

        return None

    def numOfTasks(self) -> int:
        return self._numOfTasks


# TestCases
class TaskTestCases(unittest.TestCase):

    def setUp(self) -> None:
        info = Info("./config_test.yaml")
        buildSet = info.getConfig('BuildSet')
        self.bs = BuildSet(buildSet)
