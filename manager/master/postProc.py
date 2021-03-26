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

from manager.basic.mmanager import ModuleDaemon
from manager.basic.observer import Subject


class PostProc(ModuleDaemon, Subject):

    NAME = "PostProc"
    NOTIFY_TASK_DONE = "DONE"
    NOTIFY_TAKS_FAIL = "FAIL"

    def __init__(self) -> None:
        ModuleDaemon.__init__(self, self.NAME)

        # Subject Init
        Subject.__init__(self, self.NAME)
        self.addType(self.NOTIFY_TASK_DONE)
        self.addType(self.NOTIFY_TAKS_FAIL)

    async def begin(self) -> None:
        return

    async def cleanup(self) -> None:
        return

    async def run(self) -> None:
        return
