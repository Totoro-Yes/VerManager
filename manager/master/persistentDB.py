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
import asyncio
import typing as T

from collections import namedtuple
from manager.models import PersistentDBMeta
from manager.basic.mmanager import Module
from manager.master.exceptions import PERSISTENT_DB_FILE_NOT_EXISTS
from channels.db import database_sync_to_async


FileRefInfo = namedtuple('FileRefInfo', ['ref', 'lock'])


CURRENT_POS = -1
TAIL = -2


class PersistentDB(Module):

    M_NAME = "Meta"

    def __init__(self, location: str) -> None:

        Module.__init__(self, self.M_NAME)

        self._location = location
        if not os.path.exists(self._location):
            os.mkdir(self._location)

        self._files = {}  # type: T.Dict[str, str]
        self._refs = {}   # type: T.Dict[str, FileRefInfo]

        # Lock to protect _refs
        self._ref_lock = asyncio.Lock()

        self._loop = asyncio.get_running_loop()

    async def begin(self) -> None:
        return

    async def cleanup(self) -> None:
        return

    def create(self, key: str) -> None:

        path = self._location + "/" + key

        # Try to create file
        if key in self._files:
            return
        else:
            os.mknod(path)

        self._files[key] = path

        # Record into database
        meta = PersistentDBMeta(key=key, path=path)
        meta.save()

    def is_exists(self, key: str) -> bool:
        return key in self._files

    def open(self, key: str) -> None:
        if key not in self._files:
            raise PERSISTENT_DB_FILE_NOT_EXISTS(key)

        if self.is_open(key):
            return

        path = self._files[key]

        ref = open(path, "r+b")
        lock = asyncio.Lock()
        self._refs[key] = FileRefInfo(ref, lock)

    def is_open(self, key: str) -> bool:
        return key in self._refs

    async def close(self, key: str) -> None:
        async with self._ref_lock:
            if key not in self._refs:
                raise PERSISTENT_DB_FILE_NOT_EXISTS(key)

            refinfo = self._refs[key]

            async with refinfo.lock:
                refinfo.ref.close()

            del self._refs[key]

    async def remove(self, key: str) -> None:
        if key not in self._files:
            return

        # Remove file
        os.remove(self._files[key])

        # Remove meta info from db
        meta = PersistentDBMeta(pk=key)
        await database_sync_to_async(meta.delete)()

    async def _atomic_op(self, key: str, cb: T.Callable, *args) -> T.Any:
        refinfo = None  # type: T.Optional[FileRefInfo]

        if key not in self._files:
            raise PERSISTENT_DB_FILE_NOT_EXISTS(key)

        # Check whether the file is opened.
        async with self._ref_lock:
            if key in self._refs:
                refinfo = self._refs[key]
            else:
                # Open the file
                self.open(key)
                # Must not failed
                assert(key in self._refs)
                refinfo = self._refs[key]

        # Lock down the critical region,
        # read maybe within async context
        # cause if the length is too big
        # to prevent eventloop dead.
        async with refinfo.lock:
            return await cb(refinfo.ref, *args)

    @staticmethod
    def _seek_proc(ref, pos: int) -> None:
        if pos == TAIL:
            ref.seek(0, 2)
        elif pos != CURRENT_POS:
            ref.seek(pos)

    async def read_cb(self, ref, length: int, pos: int) -> T.Union[str, bytes]:
        self._seek_proc(ref, pos)
        return ref.read(length)

    async def write_cb(self, ref, data: T.Union[str, bytes], pos: int) -> None:
        self._seek_proc(ref, pos)

        ref.write(data)

        # Flush immediately after write
        # cause another code may require these data
        # after call of this write().
        ref.flush()

        return None

    async def read(self, key: str, length: int,
                   pos: int = CURRENT_POS) -> T.Union[str, bytes]:
        return await self._atomic_op(key, self.read_cb, length, pos)

    async def write(self, key: str, data: T.Union[str, bytes],
                    pos: int = CURRENT_POS) -> None:
        return await self._atomic_op(key, self.write_cb, data, pos)

    def write_sync(self, key: str, data: T.Union[str, bytes],
                   pos: int = CURRENT_POS) -> None:
        self._loop.create_task(self.write(key, data, pos))
