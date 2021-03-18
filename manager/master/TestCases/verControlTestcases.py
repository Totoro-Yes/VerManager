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
import asyncio

from concurrent.futures import ProcessPoolExecutor
from asgiref.sync import sync_to_async
from manager.master.verControl import RevSync
from manager.models import Revisions


class HttpRequest_:

    def __init__(self):
        self.headers = ""
        self.body = ""


class VerControlTestCases(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.revSyncer = RevSync()

    async def test_new_rev(self) -> None:
        # Setup
        request = HttpRequest_()
        request.headers = {'Content-Type': 'application/json',
                           'X-Gitlab-Event': 'Merge Request Hook'}

        request.body = '{ "object_attributes": {\
                            "state": "merged",\
                            "last_commit": {\
                                "id": "12345678",\
                                "message": "message",\
                                "timestamp": "2019-05-09T01:39:08Z",\
                                "author": {\
                                "name": "root"\
                                }\
                            }\
                            }\
                            }'

        # Exercise
        self.revSyncer.start()
        self.revSyncer.revNewPush(request)
        await asyncio.sleep(1)

        # Verify
        rev = await sync_to_async(
            Revisions.objects.get, thread_sensitive=True)(pk='12345678')

        self.assertEqual("12345678", rev.sn)
        self.assertEqual("message", rev.comment)
        self.assertEqual("root", rev.author)
        self.assertEqual("2019-05-09 01:39:08+00:00", str(rev.dateTime))

        # Teardown
        await sync_to_async(rev.delete)()
