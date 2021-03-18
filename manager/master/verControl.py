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

# verRegister.py
#
# This module define a object that deal with Revisions

import asyncio
import django.db.utils
import re
import gitlab
import json
import manager.master.configs as cfg

from concurrent.futures import ProcessPoolExecutor
from asgiref.sync import sync_to_async
from django.http import HttpRequest
from manager.basic.info import Info
from typing import Any, Optional, Dict, cast
from manager.basic.type import Error
from manager.basic.mmanager import ModuleDaemon
from manager.models import Revisions, make_sure_mysql_usable


revSyncner = None
M_NAME = "RevSyncner"


class RevSync(ModuleDaemon):

    def __init__(self) -> None:
        global M_NAME

        ModuleDaemon.__init__(self, M_NAME)

        self._stop = False

        # This queue will fill by new revision that merged into
        # repository after RevSync started and RevSync will
        # put such revision into model so the revision database
        # will remain updated
        self.revQueue = asyncio.Queue(10)  # type: asyncio.Queue

    async def begin(self) -> None:
        await self.revDBInit()

    async def cleanup(self) -> None:
        return None

    def needStop(self) -> bool:
        return self._stop

    @staticmethod
    def _connectToGitlab() -> Optional[gitlab.Gitlab]:
        assert(cfg.config is not None)

        cfgs = cfg.config
        url = cfgs.getConfig('GitlabUrl')
        token = cfgs.getConfig('PrivateToken')

        if url == "" or token == "":
            return Error

        ref = gitlab.Gitlab(url, token)
        ref.auth()

        return ref

    @staticmethod
    def _retrive_revisions() -> Optional[Any]:
        assert(cfg.config is not None)

        ref = RevSync._connectToGitlab()
        projId = cfg.config.getConfig("Project_ID")

        if ref is None:
            return None

        return ref.projects.get(projId).commits.list(all=True)

    async def revTransfer(rev, tz):
        revision = Revisions(
            sn=rev.id, author=rev.author_name,
            comment=rev.message, dateTime=rev.committed_date)

        await sync_to_async(revision.save)()

        return revision

    # format of offset if "+08:00"
    @staticmethod
    def timeFormat(timeStr: str, offset: str) -> str:
        return timeStr
        pattern = "([0-9]*-[0-9]*-[0-9]*T[0-9]*:[0-9]*:[0-9]*)"

        m = re.search(pattern, timeStr)
        if m is None:
            return ""

        formatDate = m.group()
        formatDate = formatDate.replace("T", " ")
        return formatDate + offset

    async def revDBInit(self) -> bool:
        print("RevDB Init...")
        loop = asyncio.get_running_loop()
        e = ProcessPoolExecutor()
        revisions = await loop.run_in_executor(e, self._retrive_revisions)

        if revisions is None:
            raise VERSION_DB_INIT_FAILED()

        # Remove old datas of revisions cause these data may out of date
        # repository may be rebased so that the structure of it is very
        # different with datas in database so just remove these data and
        # load from server again
        import traceback
        import sys

        try:
            await sync_to_async(Revisions.objects.all().delete)()

            # Fill revisions just retrived into model
            config = cast(Info, cfg.config)
            tz = config.getConfig('TimeZone')

            for rev in revisions:
                await RevSync.revTransfer(rev, tz)
            print("Done")
            sys.stdout.flush()

        except django.db.utils.ProgrammingError:
            traceback.print_exc()
            return False
        except Exception:
            traceback.print_exc()
            pass

        print("RevDB Init success.")
        return True

    def revNewPush(self, rev: HttpRequest) -> bool:
        self.revQueue.put_nowait(rev)
        return True

    def gitlabWebHooksChecking(self, request: HttpRequest) -> Optional[Dict]:
        headers = request.headers  # type: ignore

        if 'X-Gitlab-Event' not in headers:
            print("X-Gitlab-Event not found")
            return None

        try:
            contentType = headers['Content-Type']
            event = headers['X-Gitlab-Event']

            if contentType == 'application/json' \
               and event == 'Merge Request Hook':

                body = json.loads(request.body)  # type: ignore
                state = body['object_attributes']['state']

                if state == 'merged':
                    return body
        except Exception:
            return None

        return None

    async def _requestHandle(self, request: HttpRequest) -> bool:
        # Premise of these code work correct is a merge request
        # contain only a commit if it can't be satisfied
        # should read gitlab when merge event arrived and
        # compare with database then append theses new into
        # database
        body = body = self.gitlabWebHooksChecking(request)

        if body is None:
            return False

        last_commit = body['object_attributes']['last_commit']
        sn_ = last_commit['id']
        author_ = last_commit['author']['name']
        comment_ = last_commit['message']
        date_time_ = last_commit['timestamp']

        make_sure_mysql_usable()

        rev = Revisions(sn=sn_, author=author_, comment=comment_,
                        dateTime=date_time_)

        await sync_to_async(rev.save, thread_sensitive=True)()

        return True

    # Process such a database related operation on background
    # is for the purpose of quick response to where request come
    # from. Responsbility will gain more benefit if such operation
    # to be complicated.
    async def run(self) -> None:

        while True:

            if self._stop is True:
                return None

            try:
                request = await self.revQueue.get()
                await self._requestHandle(request)
            except Exception as e:
                print(e)


class VERSION_DB_INIT_FAILED(Exception):

    def __str__(self) -> str:
        return "Version Database failed to init"
