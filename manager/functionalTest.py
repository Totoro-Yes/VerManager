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

import os
import shutil
import unittest
import asyncio
from datetime import datetime
from typing import cast, Optional, Callable
from manager.master.job import Job
from manager.master.jobMaster import JobMaster
from manager.master.master import ServerInst
from manager.worker.worker import Worker
from multiprocessing import Process
import manager.master.configs as cfg


async def masterCreate(host: str,
                       port: int, config: str) -> ServerInst:
    # Create Master
    master = ServerInst(host, port, config)
    master.start()

    cfg.skip_doc_gen = True

    # Wait Master startup
    await asyncio.sleep(1)

    return master


def WorkerStartup(startup: Optional[Callable],
                  config: str) -> None:
    if startup is not None:
        startup()
    Worker(config).start()


async def WorkerCreate(config: str,
                       startup: Optional[Callable] = None) -> Process:
    # Worker Spawn
    p = Process(
        target=WorkerStartup,
        args=(startup, config)
    )
    p.start()

    # Wait Worker startup
    await asyncio.sleep(1)

    return p


class FunctionalTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        # Create Master
        self.master = await masterCreate(
            "127.0.0.1", 30001, "./manager/misc/master_test_configs/config.yaml")

        # Create Workers
        self.worker = await WorkerCreate("./manager/misc/worker_test_configs/config.yaml")
        self.worker1 = await WorkerCreate("./manager/misc/worker_test_configs/config1.yaml")
        self.worker2 = await WorkerCreate("./manager/misc/worker_test_configs/config2.yaml")

    async def asyncTearDown(self) -> None:
        for d in ["Build", "Build1", "Build2", "Post", "data", "log"]:
            shutil.rmtree(d)

    async def test_Functional_DoJob(self) -> None:
        # Exercise
        job = Job("Job", "GL8900", {"sn": "123456", "vsn": "Job"})
        job_master = cast(JobMaster, self.master.getModule("JobMaster"))
        if job_master is None:
            self.fail("Fail to get JobMaster")

        await job_master.do_job(job)

        before = datetime.utcnow()

        while True:
            if os.path.exists("data/"+str(job.unique_id)):
                break
            if (datetime.utcnow() - before).seconds > 60:
                self.fail("Timeout")
            else:
                await asyncio.sleep(1)


###############################################################################
#                             WorkerLost TestCases                            #
###############################################################################
async def disconnectFromMaster() -> None:
    """
    Disconnect from Master after 10 seconds
    """
    import manager.worker.configs as cfg

    connector = cfg.connector
    print("Try Disconnect")
    print(connector)
    assert(connector is not None)

    await asyncio.sleep(10)
    print("Disconnect")
    connector.close("Master")

    await asyncio.sleep(5)
    # After 5 seconds we are able to reconnect to

def startup_lost() -> None:
    import manager.worker.configs as cfg
    cfg.debug = True
    cfg.debugRoutine = disconnectFromMaster


class WorkerLostTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        # Create Master
        self.master = await masterCreate(
            "127.0.0.1", 30001, "./manager/misc/master_test_configs/config.yaml",
        )
        # Create Merger
        self.merger = await WorkerCreate("./manager/misc/worker_test_configs/config.yaml")

    async def test_WorkerLostAndReconnect(self) -> None:
        # Setup
        # Create an Worker that will disconnect then reconnect
        # after master remove it.
        await WorkerCreate(
            "./manager/misc/worker_test_configs/config1.yaml",
            startup_lost
        )

        # Exercise
        job = Job("Job", "GL8900", {"sn": "123456", "vsn": "Job"})
        job_master = cast(JobMaster, self.master.getModule("JobMaster"))
        if job_master is None:
            self.fail("Fail to get JobMaster")

        await job_master.do_job(job)
