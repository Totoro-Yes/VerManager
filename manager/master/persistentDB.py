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


FileRefInfo = namedtuple('FileRefInfo', ['ref', 'lock'])


class PersistentDB(Module):

    def __init__(self, location: str) -> None:
        self._location = location
        if not os.path.exists(self._location):
            os.mkdir(self._location)

        self._files = {}  # type: T.Dict[str, str]
        self._refs = {}   # type: T.Dict[str, FileRefInfo]

        # Lock to protect _refs
        self._ref_lock = asyncio.Lock()

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

    def open(self, key: str) -> None:
        if key not in self._files:
            raise PERSISTENT_DB_FILE_NOT_EXISTS(key)

        path = self._files[key]

        ref = open(path, "r")
        lock = asyncio.Lock()
        self._refs[key] = FileRefInfo(ref, lock)

    def remove(self, key: str) -> None:
        if key not in self._files:
            return

        # Remove file
        os.remove(self._files[key])

        # Remove meta info from db
        meta = PersistentDBMeta(pk=key)
        meta.delete()

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
        # cause if the length is too big
        # will may allow read within async context
        # to prevent eventloop dead.
        async with refinfo.lock:
            return await cb(refinfo.ref, *args)

    @staticmethod
    async def read_cb(ref, length: int, pos: int) -> T.Union[str, bytes]:
        ref.seek(pos)
        return ref.read(length)

    @staticmethod
    async def write_cb(ref, data: T.Union[str, bytes], pos: int) -> None:
        ref.seek(pos)
        ref.write(data)
        return None

    async def read(self, key: str, length: int, pos: int) -> T.Union[str, bytes]:
        return await self._atomic_op(key, self.read_cb, length, pos)

    async def write(self, key: str, data: T.Union[str, bytes], pos: int) -> None:
        return await self._atomic_op(key, self.write_cb, data, pos)
