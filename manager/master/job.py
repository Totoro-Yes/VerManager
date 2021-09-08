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

from types import MappingProxyType
from typing import Dict, List, Optional, Any
from manager.master.task import Task


class Job:

    STATE_PENDING = 0
    STATE_IN_PROCESSING = 1
    STATE_DONE = 2

    def __init__(self, jobid: str, cmd_id: str, info: Dict[str, str]) -> None:
        self.jobid = jobid

        # A unique id is set by JobMaster while this job is
        # dispatched, so set to 0 by default is not a matter.
        self.unique_id = 0

        self.cmd_id = cmd_id
        self._tasks = {}  # type: Dict[str, Task]
        self._job_info = info
        self.job_result = None  # type: Optional[str]
        self.state = Job.STATE_PENDING
        self.result = None  # type: Any
        # This Dict used by
        self.tasks_record = {}  # type: Dict[str, str]
        self._extra = {}  # type: Dict[str, str]

    def is_valid(self) -> bool:
        return len(self.jobid) > 0 and \
            len(self.cmd_id) > 0 and \
            0 not in [len(t) for t in self._tasks]

    def set_unique_id(self, uid: int) -> None:
        self.unique_id = uid

    def addTask(self, ident: str, task: Task) -> None:
        if ident not in self._tasks:
            self._tasks[ident] = task

    def getTask(self, taskid: str) -> Task:
        return self._tasks[taskid]

    def numOfTasks(self) -> int:
        return len(self._tasks)

    def removeTask(self, ident: str) -> None:
        if ident in self._tasks:
            del self._tasks[ident]

    def tasks(self) -> List[Task]:
        return list(self._tasks.values())

    def get_info(self, key: str) -> Optional[str]:
        if key not in self._job_info:
            return None
        return self._job_info[key]

    def infos(self) -> MappingProxyType:
        return MappingProxyType(self._job_info)

    def is_fin(self) -> bool:
        for task in self._tasks.values():
            if not task.isFinished():
                return False

        return True

    def getExtra(self, key:str) -> Optional[str]:
        return self._extra.get(key, None)

    def __str__(self) -> str:
        """
        Format:
        <JobId>,<CmdId>::=<TaskID_1>:<TaskID_2>:...:<TaskID_n>
        """
        tasks_str = ""
        if len(self._tasks) > 0:
            tasks_str = ":".join([
                t.id()+","+Task.STATE_STR_MAPPING[t.taskState()]
                for t in self._tasks.values()
            ])
        elif len(self.tasks_record) > 0:
            tasks_str = ":".join([
                ident+","+self.tasks_record[ident]
                for ident in self.tasks_record
            ])

        return self.jobid + "," + self.cmd_id + "::=" + tasks_str

    @staticmethod
    def fromStr(str_present: str) -> Optional['Job']:
        try:
            head, body = str_present.split("::=")
            jobid, cmdid = head.split(",")

            record = {}  # type: Dict[str, str]
            tasks = body.split(":")
            for t in tasks:
                tid, state = t.split(",")
                record[tid] = state

            job = Job(jobid, cmdid, {})
            job.tasks_record = record
        except Exception:
            return None

        return job


class VerResult:

    def __init__(self, uid: str, jobid: str, url: str) -> None:
        self.uid = uid
        self.jobid = jobid
        self.url = url
