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

import json
import abc
from typing import Dict, Any, List, Tuple, Generator
from manager.master.job import VerResult
from manager.master.job import Job
from manager.master.task import Task


class Message(abc.ABC):

    FORMAT_TEMPLATE = '{"type": "%s", "content": %s}'

    def __init__(self, type: str, content: Dict[str, Any]) -> None:
        self.type = type
        self.content = content

    def __str__(self) -> str:
        content = json.dumps(self.content)
        return Message.FORMAT_TEMPLATE % (self.type, content)

    def __iter__(self) -> Generator:
        yield "type", self.type
        yield "content", self.content

    @staticmethod
    def fromString(msg_str: str) -> 'Message':
        """
        Rebuild Message from string.
        """
        json_str = json.loads(msg_str)
        return Message(json_str["type"], json_str["content"])


class JobBatchMessage(Message):

    def __init__(self, msgs: List[Message]) -> None:
        # fixme: type should be job.msg.
        Message.__init__(self, "job.msg.batch", {
            "subtype": "batch",
            "message": [
                dict(msg) for msg in msgs
                # Ensure a batch not to
                # embed into another batch.
                if type(msg).__name__ != "JobBatchMessage"
            ]
        })


class JobInfoMessage(Message):

    def __init__(self, unique_id: str, jobid: str,
                 tasks: List[List[str]]) -> None:

        Message.__init__(self, "job.msg", {
            "subtype": "info",
            "message": {
                "unique_id": unique_id,
                "jobid": jobid,
                "tasks": tasks
            }
        })

    def unique_id(self) -> str:
        return self.content["message"]["unique_id"]

    def jobid(self) -> str:
        return self.content["jobid"]["unique_id"]

    def tasks(self) -> List[Tuple[str, str]]:
        return self.content["tasks"]


class JobStateChangeMessage(Message):

    def __init__(self, unique_id: str, jobid: str,
                 taskid: str, state: str) -> None:

        Message.__init__(self, "job.msg", {
            "subtype": "change",
            "message": {
                "unique_id": unique_id,
                "jobid": jobid,
                "taskid": taskid,
                "state": state
            }
        })


class JobAllResultsMessage(Message):

    def __init__(self, results: List[VerResult]) -> None:
        Message.__init__(self, "job.msg.file.exists", {
            "subtype": "exists",
            "message": {
                str(r.uid): {
                    "unique_id": str(r.uid),
                    "ver_id": r.jobid,
                    "url": r.url
                }
                for r in results
            }
        })


class TaskOutputMessage(Message):

    def __init__(self, unique_id: str, taskid: str,
                 pos: int, length: int, message: str,
                 last: int) -> None:

        Message.__init__(self, "job.msg.task.output", {
            "subtype": "output",
            "message": {
                "uid": unique_id,
                "task": taskid,
                "pos": pos,
                "len": length,
                "msg": message,
                "last": last
            }
        })


class JobNewResultMessage(Message):

    def __init__(self, result: VerResult) -> None:
        Message.__init__(self, "job.msg.file.new", {
            "subtype": "new",
            "message": {
                "unique_id": result.uid,
                "ver_id": result.jobid,
                "url": result.url
            }
        })


class JobHistoryMessage(Message):

    def __init__(self, jobs: List[Job]) -> None:
        Message.__init__(self, "job.msg.history", {
            "subtype": "history",
            "message": {
                str(job.unique_id): {
                    "unique_id": str(job.unique_id),
                    "jobid": job.jobid,
                    "tasks": {
                        t.id(): {
                            "taskid": t.id(),
                            "state": Task.STATE_STR_MAPPING[t.taskState()]
                        }
                        for t in job.tasks()
                    }
                }
                for job in jobs
            }
        })


class JobFinMessage(Message):

    def __init__(self, unique_id: str) -> None:
        Message.__init__(self, "job.msg", {
            "subtype": "fin",
            "message": {"jobs": [unique_id]}
        })


class JobFailMessage(Message):

    def __init__(self, unique_id: str) -> None:
        Message.__init__(self, "job.msg", {
            "subtype": "fail",
            "message": {"jobs": [unique_id]}
        })


class ClientEvent(Message):

    def __init__(self, text_data: str) -> None:

        try:
            data = json.loads(text_data)

            Message.__init__(self, data['type'], {
                "subtype": data["content"]["subtype"],
                "message": data["content"]["message"]
            })

        except Exception:
            raise
