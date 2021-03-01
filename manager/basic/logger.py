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

# logger.py

import unittest
import shutil

import os
import asyncio

from datetime import datetime
from typing import Dict, TextIO, Tuple, Optional

from manager.basic.mmanager import ModuleDaemon
from manager.basic.type import State, Ok, Error

from manager.basic.observer import Observer

M_NAME = "Logger"

LOG_ID = str
LOG_MSG = str


class LOGGER_NOT_EXISTS(Exception):
    pass


class Logger(ModuleDaemon, Observer):

    def __init__(self, path: str) -> None:
        global M_NAME
        ModuleDaemon.__init__(self, M_NAME)
        Observer.__init__(self)

        self.logPath = path
        self.logQueue = asyncio.Queue(128)  # type: asyncio.Queue

        self.logTunnels = {}  # type: Dict[str, TextIO]

        self._stop = False

        if not os.path.exists(path):
            os.mkdir(path)

    async def begin(self) -> None:
        return None

    async def cleanup(self) -> None:
        return None

    async def run(self) -> None:

        assert(self.logQueue is not None)

        while True:
            if self._stop:
                return None
            try:
                msgUnit = await asyncio.wait_for(
                    self.logQueue.get(), timeout=1)
            except asyncio.exceptions.TimeoutError:
                continue

            self._output(msgUnit)

    async def stopDelay(self, timeout: Optional[int] = None) -> None:
        if timeout is not None:
            await asyncio.sleep(timeout)
        self.stop()

    def needStop(self) -> bool:
        return self._stop

    async def log_put(self, lid: LOG_ID, msg: LOG_MSG) -> None:
        if self.logQueue is None:
            raise LOGGER_NOT_EXISTS()

        await self.logQueue.put((lid, msg))

    def log_register(self, logId: LOG_ID) -> State:
        if logId in self.logTunnels:
            return Error

        logFilePath = self.logPath + "/" + logId
        file = open(logFilePath, "w")

        self.logTunnels[logId] = file

        return Ok

    def log_close(self, logId: LOG_ID) -> None:
        if logId not in self.logTunnels:
            return None

        fd = self.logTunnels[logId]
        del self.logTunnels[logId]

        fd.close()

    def _output(self, unit: Tuple[LOG_ID, LOG_MSG]) -> None:
        logId = unit[0]
        logMessage = unit[1]

        if logId not in self.logTunnels:
            return None

        logFile = self.logTunnels[logId]

        logMessage = self._format(logMessage)
        logFile.write(logMessage)
        logFile.flush()

    @staticmethod
    async def putLog(log: 'Logger', lid: LOG_ID, msg: LOG_MSG) -> None:
        if log is None:
            return None

        await log.log_put(lid, msg)

    @staticmethod
    def _format(message: LOG_MSG) -> str:
        time = datetime.now()
        formated_message = str(time) + " : " + message + '\n'

        return formated_message

    async def listenTo(self, data: Tuple[str, str]) -> None:
        print(data)
        tunnelname, msg = data

        if tunnelname not in self.logTunnels:
            self.log_register(tunnelname)

        await self.log_put(tunnelname, msg)


# TestCases
class LoggerTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.logger = Logger("./logger")

    async def asyncTearDown(self) -> None:
        shutil.rmtree("./logger")

    async def test_Logger_logRegister(self) -> None:
        self.logger.log_register("ID")
        self.assertTrue("ID" in self.logger.logTunnels)

    async def test_Logger_logRegister_duplicate(self) -> None:
        self.logger.log_register("ID")
        self.logger.log_register("ID")
        self.assertTrue("ID" in self.logger.logTunnels)

    async def test_Logger_logPut(self) -> None:
        # Setup
        self.logger.log_register("ID")

        # Exercise
        await self.logger.begin()
        await self.logger.log_put("ID", "123456789")
        self.logger.start()
        await asyncio.sleep(1)

        # Verify
        f = open("./logger/ID")
        val = f.read(100)
        val = val.split(":")[-1].strip()
        self.assertEqual("123456789", val)

    async def test_logger_close(self) -> None:
        # Setup
        self.logger.log_register("ID")
        self.assertTrue("ID" in self.logger.logTunnels)

        # Exercise
        self.logger.log_close("ID")

        # Verify
        self.assertTrue("ID" not in self.logger.logTunnels)
