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
import typing
import manager.master.configs as config
from manager.basic.info import Info
from manager.master.task import Task
from manager.master.job import Job
from manager.master.jobMaster import JobMaster, task_prefix_trim, \
    JobMasterMsgSrc
from manager.basic.endpoint import Endpoint
from manager.models import Jobs, JobHistory, TaskHistory
from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from manager.master.jobMaster import command_var_replace, \
    command_preprocessing, build_preprocessing
from manager.master.build import Build
from manager.basic.mmanager import MManager
from manager.master.TestCases.misc.stubs import StorageStub


class DispatcherFake(Endpoint):

    def __init__(self) -> None:
        Endpoint.__init__(self)
        self.tasks = []  # type: typing.List[Task]

    async def handle(self, msg: typing.Tuple[str, Task]) -> None:
        cmd, task = msg
        self.tasks.append(task)

    async def fin(self) -> None:
        """
        Set all tasks to fin state and notify
        JobMaster.
        """
        for t in self.tasks:
            # To ProcState then to Fin
            # cause directly from Prepare to
            # Fin state is not allow.
            t.toProcState()
            t.toFinState()

            await self.peer_notify((
                t.id(),
                Task.STATE_STR_MAPPING[Task.STATE_FINISHED]
            ))


class JobMasterTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        # Setup
        config.config = Info("manager/master/TestCases/misc/config.yaml")
        config.mmanager = MManager()

        # Add StorageStub
        config.mmanager.addModule(StorageStub())

        self.sut = JobMaster()

    async def test_JobMaster_Create(self) -> None:
        # Verify
        self.assertIsNotNone(self.sut)

    async def test_JobMaster_BindJob(self) -> None:
        """
        Bind a job with a Job command that defined
        in configuration file, after binded job
        will contain a set of tasks that able to
        dispatched via dispatcher.
        """
        # Setup
        job = Job("JobMasterTest1", "GL8900", {"sn": "123456", "vsn": "123456"})

        # Exercise
        await self.sut.bind(job)

        # Verify
        idents = [t.id().split("_")[1] for t in job.tasks()]
        self.assertTrue(len(job.tasks()) == 5)
        self.assertTrue("GL5610" in idents)
        self.assertTrue("GL5610-v3" in idents)
        self.assertTrue("GL5610-v2" in idents)
        self.assertTrue("GL8900" in idents)
        self.assertTrue("JobMasterTest1" in idents)

        # Teardown
        job = await sync_to_async(Jobs.objects.filter)(jobid="JobMasterTest1")
        await sync_to_async(job.delete)()  # type: ignore

    async def test_JobMaster_DoJob(self) -> None:
        """
        Assign a job to JobMaster, JobMaster should bind
        the Job with a command then dispatch tasks to
        worker via dispatcher.
        """

        tasks = [
            "GL5610",
            "GL5610-v2",
            "GL5610-v3",
            "GL8900",
            "JobMasterTest",
        ]

        # Setup
        job = Job("JobMasterTest", "GL8900", {"sn": "123456", "vsn": "123456"})
        fake = DispatcherFake()
        self.sut.set_peer(fake)

        # Exercise
        await self.sut.do_job(job)

        # Verify Tasks
        self.assertTrue(len(job.tasks()) == 5)
        for t in tasks:
            self.assertTrue(t in [t.id().split("_")[1] for t in fake.tasks])

        # Exercise Fin state of a job
        job.job_result = "Path"
        await fake.fin()

        # Verify
        job_db = await database_sync_to_async(
            JobHistory.objects.get
        )(unique_id=job.unique_id)

        tasks_db = await database_sync_to_async(
            TaskHistory.objects.filter
        )(jobhistory_id=job_db.unique_id)

        tasks_objs = await database_sync_to_async(list)(tasks_db)
        for t in tasks:
            self.assertTrue(t in [obj.task_name for obj in tasks_objs])

        # Teardown
        job_ = await sync_to_async(Jobs.objects.filter)(jobid="JobMasterTest")
        await sync_to_async(job_.delete)()  # type: ignore

        jobhistory = await database_sync_to_async(
            JobHistory.objects.filter
        )(unique_id=job.unique_id)
        await database_sync_to_async(
            jobhistory.delete
        )()

        taskhistory = await database_sync_to_async(
            TaskHistory.objects.filter
        )(jobhistory_id=job_db.unique_id)
        await database_sync_to_async(
            taskhistory.delete
        )()

    async def test_JobMaster_GenMsg(self) -> None:
        """
        Try query message from JobMaster.
        """
        source = JobMasterMsgSrc("SRC")
        source.jobs = {"1": Job("J", "CMD", {})}

        # Exercise
        msg = await source.gen_msg(["processing"])

        # Verify
        self.assertIsNotNone(msg)
        self.assertTrue("batch", msg.content['subtype'])

    async def test_JobMaster_GenHistoryMsg(self) -> None:
        """
        Query history message from JobMaster.
        """
        source = JobMasterMsgSrc("SRC")
        source.jobs = {"1": Job("J", "CMD", {})}

        # Exercise
        msg = await source.gen_msg(["history"])


class JobMasterMiscTestCases(unittest.IsolatedAsyncioTestCase):

    async def test_JobMasterMisc_TaskPrefixTrim_ValidString(self) -> None:
        ident = "Ver_TASKID"
        self.assertEqual("TASKID", task_prefix_trim(ident))

    async def test_JobMasterMisc_TaskprefixTrim_InvalidString(self, ) -> None:
        self.assertEqual(None, task_prefix_trim(""))
        self.assertEqual(None, task_prefix_trim("1_"))
        self.assertEqual(None, task_prefix_trim("_"))

    async def test_JobMasterMisc_VarReplace(self) -> None:
        # Setup
        cmd = [
            "echo <version>",
            "echo <datetime>"
        ]

        cmd_trans = command_var_replace(
            cmd, [("<version>", "vsn"), ("<datetime>", "2020-01-01")])

        self.assertEqual("echo vsn", cmd_trans[0])
        self.assertEqual("echo 2020-01-01", cmd_trans[1])

    async def test_JobMasterMisc_CmdPreprocessing(self) -> None:
        # Setup
        cmd = [
            "echo <version>",
            "echo <datetime>",
            "echo .\\path\\to\\result"
        ]

        cmd_trans = command_preprocessing(
            cmd, [("<version>", "vsn"), ("<datetime>", "2020-01-01")])

        self.assertEqual("echo vsn", cmd_trans[0])
        self.assertEqual("echo 2020-01-01", cmd_trans[1])
        self.assertEqual("echo ./path/to/result", cmd_trans[2])

    async def test_JobMasterMisc_BuildPrepreocessing(self) -> None:
        # Setup
        b = Build("B", {
            'cmd': [
                "echo <version>",
                "echo <datetime>"
            ],
            'output': [
                ".\\path\\to\\result"
            ]
        })

        # Exercise
        build_preprocessing(b, [("<version>", "vsn"), ("<datetime>", "2020-01-01")])

        # Verify
        cmds = b.getCmd()
        self.assertEqual("echo vsn", cmds[0])
        self.assertEqual("echo 2020-01-01", cmds[1])
        output = b.getOutput()
        self.assertEqual("./path/to/result", output)
