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

import asyncio
from datetime import datetime
import subprocess
from manager.basic.util import packShellCommands, execute_shell, \
    stop_ps_recursive_async
from typing import List, Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor


class CommandExecutor:

    def __init__(self, cmds: List[str] = None) -> None:
        self._cmds = cmds  # type: Optional[List[str]]
        self._max_stucked_time = 3600
        self._running = False
        self._ret = 0
        self._ref = None  # type: Optional[subprocess.Popen]
        self._pid = 0
        self.isStucked = False
        self._last_active = datetime.utcnow()
        self._isMonitorInProgress = False
        self._output_proc = None  # type: Optional[Callable]
        self._output_proc_args = None  # type: Any

    def _reset(self) -> None:
        self._running = False

    def pid(self) -> int:
        return self._pid

    async def stop(self) -> None:
        if self._ref is not None:
            # subproces.terminate() unable
            # to stop children of the directly
            # process
            await stop_ps_recursive_async(self._ref.pid)
            self._reset()

    async def run(self) -> int:

        if self._cmds is None:
            return -1

        self._running = True
        self._last_active = datetime.utcnow()

        command_str = packShellCommands(self._cmds)
        ref = execute_shell(
            command_str,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        if ref is None:
            self._ret = -1
            self._reset()
            return -1

        self._ref = ref
        self._pid = ref.pid

        self._makeMonitor()

        while True:
            # Check whether the command done
            ret = ref.poll()

            if ret is not None:
                # Wait monitor done
                while self._isMonitorInProgress:
                    await asyncio.sleep(1)

                self._ret = ret
                break

            # Check whether the command is stucked
            diff = (datetime.utcnow() - self._last_active).seconds
            if diff > self._max_stucked_time:
                self._ret = -1
                await self.stop()
                break

            await asyncio.sleep(1)

        self._ref = None
        self._running = False

        if ret is None:
            return -1

        self._reset()
        return ret

    def _makeMonitor(self) -> None:
        """
        Create a monitor to make sure a command is not
        idle state forever.
        """
        asyncio.get_running_loop()\
            .create_task(self._monitor())

    async def _monitor(self) -> None:
        self._isMonitorInProgress = True

        if self._ref is None:
            return None

        handle = self._ref.stdout
        # handle must not None
        assert(handle is not None)

        loop = asyncio.get_running_loop()
        e = ThreadPoolExecutor()

        while True:
            # Read a KiB datas from output.
            datas = b""
            r_count = 0

            while r_count < 1024:
                # Stdout is already setup by run(), ignore
                # warning.
                line = await loop.run_in_executor(e, handle.readline)

                if line == b"":
                    break

                self._last_active = datetime.utcnow()
                r_count += len(line)
                datas += line

            # No output and command is done.
            if datas == b"":
                self._isMonitorInProgress = False
                return

            # Process output datas if needed.
            if self._output_proc is not None:
                await self._output_proc(datas, *self._output_proc_args)

        e.shutdown()

    def return_code(self) -> int:
        return self._ret

    def isRunning(self) -> bool:
        return self._running

    def getStuckedLimit(self) -> int:
        return self._max_stucked_time

    def setStuckedLimit(self, limit: int) -> None:
        self._max_stucked_time = limit

    def setCommand(self, cmds: List[str]) -> None:
        self._cmds = cmds

    def set_output_proc(self, proc: Callable, *args) -> None:
        self._output_proc = proc
        self._output_proc_args = args
