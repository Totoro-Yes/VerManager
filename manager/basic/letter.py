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

# letter.py
#
# How to communicate with worker ?

import json
import asyncio
import socket
import time

import traceback
from typing import Optional, Dict, \
    Any, List, Union, Tuple, Callable, cast


def newTaskLetterValidity(letter: 'Letter') -> bool:
    isHValid = letter.getHeader('ident') != "" and letter.getHeader('tid') != ""
    isCValid = letter.getContent('sn') != "" and \
               letter.getContent('vsn') != ""

    return isHValid and isCValid


def responseLetterValidity(letter: 'Letter') -> bool:
    isHValid = letter.getHeader('ident') != "" and letter.getHeader('tid') != ""
    isCValid = letter.getContent('state') != ""

    return isHValid and isCValid


def propertyLetterValidity(letter: 'Letter') -> bool:
    isHValid = letter.getHeader('ident') != ""
    isCValid = letter.getContent('MAX') != "" and letter.getContent('PROC') != ""

    return isHValid and isCValid


def binaryLetterValidity(letter: 'Letter') -> bool:
    isHValid = letter.getHeader('tid') != ""
    isCValid = letter.getContent('bytes') != ""

    return isHValid and isCValid


def logLetterValidity(letter: 'Letter') -> bool:
    isHValid = letter.getHeader('logId') != ""
    isCValid = letter.getContent('logMsg') != ""

    return isHValid and isCValid


def logRegisterLetterValidity(letter:  'Letter') -> bool:
    isHValid = letter.getHeader('logId') != ""

    return isHValid


class Letter:

    # Format of NewTask letter
    # Type    :  'new'
    # header  :  '{"tid": "...", "parent": "...", "needPost": "true/false", "menu": "..."}'
    # content :  '{"sn": "...", "vsn": "...", "datetime": "...", "extra": {...}}"
    NewTask = 'new'

    # Format of Menu letter
    # Type    :  "menu"
    # header  :  "{"mid": "..."}"
    # content :  "{"cmds": "[...]", "depends": "[...]", "output": "..."}"
    NewMenu = 'menu'

    # Format of Post letter
    # Type    :  "Post"
    # header  :  '{"version":"...", "output":"..."}'
    # content :  '{"Menus":{"M1":{"mid":"...", "cmds":[...], "depends":[...], "output":"..."},
    #              "Fragments":["F1", "F2"], "cmds":[...]}'
    Post = 'Post'

    # Format of Command letter
    # Type    :  "command"
    # header  :  "{"type": "...", "target": "...", "extra": "..."}"
    # content :  "{"content": "..."}"
    #
    # Type:
    # (1) Stop -- stop worker process
    # (2) Cancel -- Cancel target task
    # (3) Config -- Informations that guid worker how to configure itself
    Command = 'command'

    # Format of Command response letter
    # Type    :  "cmdResponse"
    # Header  :  "{"ident": "WorkerName", "type": "cmdType", "state": "...", "target": "..."}"
    # Content :  "{}"
    CmdResponse = "cmdResponse"

    # Format of TaskCancel letter
    # Type    :  'cancel'
    # header  :  '{"tid": "...", "parent": "..."}'
    # content :  '{}'
    TaskCancel = 'cancel'

    # Format of Response letter
    # Type    :  'response'
    # header  :  '{"ident": "...", "tid": "...", "parent": "..."}
    # content :  '{"state": "..."}
    Response = 'response'

    RESPONSE_STATE_PREPARE = "0"
    RESPONSE_STATE_IN_PROC = "1"
    RESPONSE_STATE_FINISHED = "2"
    RESPONSE_STATE_FAILURE = "3"

    # Format of PrpertyNotify letter
    # Type    :  'notify'
    # header  :  '{"ident": "..."}'
    # content :  '{"MAX": "...", "PROC": "..."}'
    PropertyNotify = 'notify'

    # Format of binary letter in a stream
    # | Type (2Bytes) 00001 : :  Int | Length (4Bytes) : :  Int | fileName (32 Bytes)
    # | TaskId (64Bytes) : :  String | Parent (64 Bytes) : :  String
    # | Menu (30 Bytes) : :  String | Content |
    # Format of BinaryFile letter
    # Type    :  'binary'
    # header  :  '{"tid": "...", "parent": "..."}'
    # content :  "{"bytes": b"..."}"
    BinaryFile = 'binary'

    # Format of log letter
    # Type :  'log'
    # header :  '{"ident": "...", "logId": "..."}'
    # content:  '{"logMsg": "..."}'
    Log = 'log'

    # Format of LogRegister letter
    # Type    :  'LogRegister'
    # header  :  '{"ident": "...", "logId"}'
    # content :  "{}"
    LogRegister = 'logRegister'

    """
    Format of ReqLetter
    Type : 'Req'
    Header : {"type":...}
    Content : {"content":"..."}
    """
    Req = "Req"

    """
    Fortmath of HeartbeatLetter
    Type    : 'Hb'
    Header  : {"type":..., "ident":..., "seq":...}}
    Content : {}
    """
    Heartbeat = "Hb"

    """
    Format of TaskLogLetter
    Type    : "TL"
    Header  : {ident":...}
    content : {"message":...}
    """
    TaskLog = "TL"

    Notify = "Notify"

    BINARY_HEADER_LEN = 260
    BINARY_MIN_HEADER_LEN = 6
    LETTER_TYPE_LEN = 2

    MAX_LEN = 512

    format = '{"type": "%s", "header": %s, "content": %s}'

    def __init__(self, type_:  str,
                 header:  Dict[str, str],
                 content:  Dict[str, Any]) -> None:

        self.type_ = type_

        # header field is a dictionary
        self.header = header

        # content field is a dictionary
        self.content = content

        #if not self.validity():
        #    print(self.type_ + str(self.header) + str(self.content))

    # Generate a json string
    def toString(self) -> str:
        # length of content after length
        headerStr = json.dumps(self.header)
        contentStr = json.dumps(self.content)
        return Letter.format % (self.type_, headerStr, contentStr)

    def __repr__(self) -> str:
        # length of content after length
        headerStr = json.dumps(self.header)
        contentStr = json.dumps(self.content)
        return Letter.format % (self.type_, headerStr, contentStr)

    def toJson(self) -> Dict:
        jsonStr = self.toString()
        return json.loads(jsonStr)

    def toBytesWithLength(self) -> bytes:
        str = self.toString()
        bStr = str.encode()

        return len(bStr).to_bytes(2, "big") + bStr

    @staticmethod
    def json2Letter(s:  str) -> 'Letter':
        dict_ = None

        begin = s.find('{')
        dict_ = json.loads(s[begin: ])

        return Letter(dict_['type'], dict_['header'], dict_['content'])

    def typeOfLetter(self) -> str:
        return self.type_

    def getHeader(self, key:  str) -> str:
        if key in self.header:
            return self.header[key]
        else:
            return ""

    def addToHeader(self, key:  str, value:  str) -> None:
        self.header[key] = value

    def setHeader(self, key: str, value: str) -> None:
        self.header[key] = value

    def setContent(self, key: str, value: Union[str, bytes]) -> None:
        self.content[key] = value

    def addToContent(self, key:  str, value:  str) -> None:
        self.content[key] = value

    def getContent(self, key:  str) -> Any:
        if key in self.content:
            return self.content[key]
        else:
            return ""

    # If a letter is received completely return 0 otherwise
    # return the remaining bytes
    @staticmethod
    def letterBytesRemain(s:  bytes) -> int:
        if len(s) < 2:
            return 2 - len(s)
        else:
            if int.from_bytes(s[:2], "big") == 1:
                if len(s) < Letter.BINARY_HEADER_LEN:
                    return Letter.BINARY_HEADER_LEN - len(s)

                length = int.from_bytes(s[2:6], "big")
                return length - (len(s) - Letter.BINARY_HEADER_LEN)
            else:
                length = int.from_bytes(s[:2], "big")
                return length - (len(s) - 2)

    @staticmethod
    def parse(s: bytes) -> Optional['Letter']:
        # To check that is BinaryFile type or another
        if int.from_bytes(s[: 2], "big") == 1:
            return BinaryLetter.parse(s)
        else:
            return Letter._parse(s)

    @staticmethod
    def _parse(s: bytes) -> Optional['Letter']:
        try:
            letter = s[2:].decode()
        except Exception:
            traceback.print_exc()
            raise Exception

        try:
            dict_ = json.loads(letter)
            type_ = dict_['type']
        except Exception:
            return None

        return parseMethods[type_].parse(s)

    def validity(self) -> bool:
        type = self.typeOfLetter()
        return validityMethods[type](self)

    # PropertyNotify letter interface
    def propNotify_MAX(self) -> int:
        return int(self.content['MAX'])

    def propNotify_PROC(self) -> int:
        return int(self.content['PROC'])

    def propNotify_IDENT(self) -> str:
        return self.header['ident']


def bytesDivide(s: bytes) -> Tuple:
    letter = s[2: ].decode()
    dict_ = json.loads(letter)

    type_ = dict_['type']
    header = dict_['header']
    content = dict_['content']

    return (type_, header, content)


class NewLetter(Letter):

    def __init__(self, tid: str, sn: str,
                 vsn: str, datetime: str,
                 extra: Dict,
                 parent: str = "",
                 needPost: str = "") -> None:
        Letter.__init__(
            self,
            Letter.NewTask,
            {"tid": tid, "parent": parent, "needPost": needPost},
            {"sn": sn, "vsn": vsn, "datetime": datetime, "extra": extra}
        )

    @staticmethod
    def parse(s: bytes) -> Optional['NewLetter']:

        (type_, header, content) = bytesDivide(s)

        if type_ != Letter.NewTask:
            return None

        return NewLetter(
            tid=header['tid'],
            sn=content['sn'],
            vsn=content['vsn'],
            datetime=content['datetime'],
            parent=header['parent'],
            extra=content['extra'],
            needPost=header['needPost'])

    def getTid(self) -> str:
        return self.getHeader('tid')

    def getParent(self) -> str:
        return self.getHeader('parent')

    def needPost(self) -> str:
        return self.getHeader('needPost')

    def setPost(self, post: str) -> None:
        self.setHeader("needPost", post)

    def getSN(self) -> str:
        return self.getContent('sn')

    def getVSN(self) -> str:
        return self.getContent('vsn')

    def getDatetime(self) -> str:
        return self.getContent('datetime')

    def getExtra(self) -> Dict[str, Any]:
        return self.getContent('extra')


class CancelLetter(Letter):

    TYPE_SINGLE = "Single"
    TYPE_POST = "Post"

    def __init__(self, taskId: str, type: str) -> None:
        Letter.__init__(self, Letter.TaskCancel,
                        {"taskId": taskId, "type": type}, {})

    @staticmethod
    def parse(s: bytes) -> Optional['CancelLetter']:
        (type_, header, content) = bytesDivide(s)

        if type_ != Letter.TaskCancel:
            return None

        return CancelLetter(header['taskId'], header['type'])

    def getIdent(self) -> str:
        return self.getHeader('taskId')

    def getType(self) -> str:
        return self.getHeader('type')

    def setType(self, type: str) -> None:
        self.setHeader('type', type)


CmdType = int
CmdSubType = int


class CommandLetter(Letter):

    def __init__(self, type:  str, content:  Dict[str, str], target:  str = "",
                 extra: str = "") -> None:
        Letter.__init__(self, Letter.Command,
                        {"type":  type, "target":  target, "extra":  extra},
                        content)

    @staticmethod
    def parse(s:  bytes) -> Optional['CommandLetter']:
        (type_, header, content) = bytesDivide(s)

        if type_ != Letter.Command:
            return None

        return CommandLetter(header['type'], content, header['target'],
                             header['extra'])

    def getType(self) -> str:
        return self.getHeader('type')

    def getTarget(self) -> str:
        return self.getHeader('target')

    def getExtra(self) -> Any:
        return self.getHeader('extra')

    def content_(self, key: str) -> str:
        return self.getContent(key)


class CmdResponseLetter(Letter):

    STATE_SUCCESS = "s"
    STATE_FAILED = "f"

    def __init__(self, wIdent:  str, type:  str,
                 state:  str, extra:  Dict[str, str],
                 reason:  str = "", target:  str = "") -> None:
        Letter.__init__(self, Letter.CmdResponse,
                        {"ident":  wIdent, "type":  type,
                         "state": state, "target":  target},
                        {"reason":  reason, "extra":  extra})

    @staticmethod
    def parse(s:  bytes) -> Optional['CmdResponseLetter']:
        (type_, header, content) = bytesDivide(s)

        if type_ != Letter.CmdResponse:
            return None

        return CmdResponseLetter(header['ident'], header['type'], header['state'],
                                 content['extra'],
                                 target=header['target'],
                                 reason=content['reason'])

    def getIdent(self) -> str:
        return self.getHeader('ident')

    def getType(self) -> str:
        return self.getHeader('type')

    def getState(self) -> str:
        return self.getHeader('state')

    def getReason(self) -> str:
        return self.getContent('reason')

    def getTarget(self) -> str:
        return self.getHeader('target')

    def getExtra(self, key:  str) -> Any:
        try:
            return self.getContent('extra')[key]
        except IndexError:
            return None


class PostTaskLetter(Letter):

    def __init__(self, ident: str, ver: str,
                 cmds: List[str], output: str,
                 frags: List) -> None:

        Letter.__init__(self, Letter.Post,
                        {"ident": ident, "version": ver, "output": output},
                        {"cmds": cmds, "Fragments": frags})

    @staticmethod
    def parse(s: bytes) -> Optional['PostTaskLetter']:
        (type_, header, content) = bytesDivide(s)

        if type_ != Letter.Post:
            return None

        return PostTaskLetter(header['ident'], header['version'],
                              content['cmds'], header['output'],
                              frags=content['Fragments'])

    def getIdent(self) -> str:
        return self.getHeader("ident")

    def getVersion(self) -> str:
        return self.getHeader("version")

    def getCmds(self) -> List[str]:
        return self.getContent('cmds')

    def getOutput(self) -> str:
        return self.getHeader('output')

    def addFrag(self, fragId: str) -> None:
        frags = self.getContent('Fragments')

        if fragId in frags:
            return None

        frags.append(fragId)

    def frags(self) -> List[str]:
        return self.getContent("Fragments")


class ResponseLetter(Letter):

    def __init__(self, ident:  str, tid:  str, state:  str,
                 parent: str = "") -> None:
        Letter.__init__(
            self,
            Letter.Response,
            {"ident":  ident, "tid":  tid, "parent":  parent},
            {"state":  state}
        )

    @staticmethod
    def parse(s:  bytes) -> Optional['ResponseLetter']:
        (type_, header, content) = bytesDivide(s)

        if type_ != Letter.Response:
            return None

        return ResponseLetter(
            ident=header['ident'],
            tid=header['tid'],
            state=content['state'],
            parent=header['parent']
        )

    def getIdent(self) -> str:
        return self.getHeader('ident')

    def getTid(self) -> str:
        return self.getHeader('tid')

    def getParent(self) -> str:
        return self.getHeader('parent')

    def getState(self) -> str:
        return self.getContent('state')

    def setState(self, state: str) -> None:
        self.setContent('state', state)


class NotifyLetter(Letter):

    def __init__(self, ident: str, type: str, content: Dict) -> None:
        Letter.__init__(self, Letter.Notify,
                        {"ident": ident, "type": type}, content)

    def notifyFrom(self) -> str:
        return self.getHeader('ident')

    def notifyType(self) -> str:
        return self.getHeader('type')

    def notifyContent(self) -> Dict:
        return self.content

    @staticmethod
    def parse(bs: bytes) -> Optional['NotifyLetter']:
        (type_, header, content) = bytesDivide(bs)

        if type_ != Letter.Notify:
            return None

        return NotifyLetter(header['ident'], header['type'], content)


class PropLetter(Letter):

    def __init__(self, ident: str, max: str, proc: str, role: str) -> None:
        Letter.__init__(
            self,
            Letter.PropertyNotify,
            {"ident":  ident},
            {"MAX":  max, "PROC":  proc, "role": role}
        )

    @staticmethod
    def parse(s:  bytes) -> Optional['PropLetter']:
        (type_, header, content) = bytesDivide(s)

        if type_ != Letter.PropertyNotify:
            return None

        return PropLetter(
            ident=header['ident'],
            max=content['MAX'],
            proc=content['PROC'],
            role=content['role']
        )

    def getIdent(self) -> str:
        return self.getHeader('ident')

    def getMax(self) -> str:
        return self.getContent('MAX')

    def getProc(self) -> str:
        return self.getContent('PROC')

    def getRole(self) -> int:
        return self.getContent('role')


class BinaryLetter(Letter):

    TYPE_DATA = 1
    TYPE_BROKEN = 2

    TYPE_FIELD_LEN = 2
    LENGTH_FIELD_LEN = 4
    FILE_NAME_FIELD_LEN = 32
    TASK_ID_FIELD_LEN = 128
    PARENT_FIELD_LEN = 64
    MENU_FIELD_LEN = 30

    class FIELD_LENGTH_EXCEPTION(Exception):
        pass

    def __init__(self, tid:  str, bStr:  bytes, menu:  str = "",
                 fileName:  str = "", parent:  str = "",
                 last:  str = "false") -> None:

        BinaryLetter.field_length_check(
            BinaryLetter.FILE_NAME_FIELD_LEN,
            fileName
        )
        BinaryLetter.field_length_check(
            BinaryLetter.TASK_ID_FIELD_LEN,
            tid
        )
        BinaryLetter.field_length_check(
            BinaryLetter.PARENT_FIELD_LEN,
            parent
        )
        BinaryLetter.field_length_check(
            BinaryLetter.MENU_FIELD_LEN,
            menu
        )

        Letter.__init__(
            self,
            Letter.BinaryFile,
            {"tid":  tid, "fileName":  fileName,
             "parent":  parent, "menu":  menu},
            {"bytes":  bStr}
        )

    @staticmethod
    def field_length_check(l, field):
        if len(field) > l:
            raise BinaryLetter.FIELD_LENGTH_EXCEPTION

    @staticmethod
    def parse(s:  bytes) -> Optional['BinaryLetter']:
        fileName = s[6:38].decode().replace(" ", "")
        tid = s[38:166].decode().replace(" ", "")
        parent = s[166:230].decode().replace(" ", "")
        menu = s[230:260].decode().replace(" ", "")
        content = s[260:]

        return BinaryLetter(tid, content, menu, fileName, parent = parent)

    def toBytesWithLength(self) -> bytes:

        bStr = self.binaryPack()

        if bStr is None:
            return b''

        return bStr

    def binaryPack(self) -> Optional[bytes]:

        tid = self.getHeader('tid')
        fileName = self.getHeader('fileName')
        content = self.getContent("bytes")
        parent = self.getHeader('parent')
        menu = self.getHeader('menu')

        if type(content) is str:
            return None

        def extend_bytes(n: int, bs: bytes):
            return b' ' * n + bs

        type_field = (1).to_bytes(BinaryLetter.TYPE_FIELD_LEN, "big")
        len_field = len(content).to_bytes(BinaryLetter.LENGTH_FIELD_LEN, "big")

        tid_field = extend_bytes(
            BinaryLetter.TASK_ID_FIELD_LEN - len(tid),
            tid.encode())

        parent_field = extend_bytes(
            BinaryLetter.PARENT_FIELD_LEN -
            len(parent), parent.encode())

        name_field = extend_bytes(
            BinaryLetter.FILE_NAME_FIELD_LEN -
            len(fileName), fileName.encode())

        menu_field = extend_bytes(
            BinaryLetter.MENU_FIELD_LEN - len(menu),
            menu.encode())

        # Safe here content must not str and must a bytes
        # | Type (2Bytes) 00001 :: Int | Length (4Bytes) :: Int
        # | Ext (32 Bytes) | TaskId (64Bytes) :: String
        # | Parent(64 Bytes) :: String | Menu (30 Bytes) :: String
        # | Content :: Bytes |
        packet = type_field + len_field + name_field + tid_field + \
            parent_field + menu_field + content

        return packet

    def getTid(self) -> str:
        return self.getHeader('tid')

    def getFileName(self) -> str:
        return self.getHeader('fileName')

    def getParent(self) -> str:
        return self.getHeader('parent')

    def getMenu(self) -> str:
        return self.getHeader('menu')

    def getBytes(self) -> bytes:
        return self.getContent('bytes')

    def setBytes(self, b: bytes) -> None:
        self.setContent('bytes', b)


class LogLetter(Letter):

    def __init__(self, ident:  str, logId:  str, logMsg:  str) -> None:
        Letter.__init__(
            self,
            Letter.Log,
            {"ident":  ident, "logId":  logId},
            {"logMsg":  logMsg}
        )

    @staticmethod
    def parse(s:  bytes) -> Optional['LogLetter']:
        (type_, header, content) = bytesDivide(s)

        if type_ != Letter.Log:
            return None

        return LogLetter(
            ident=header['ident'],
            logId=header['logId'],
            logMsg=content['logMsg']
        )

    def getIdent(self) -> str:
        return self.getHeader('ident')

    def getLogId(self) -> str:
        return self.getHeader('logId')

    def getLogMsg(self) -> str:
        return self.getContent('logMsg')


class LogRegLetter(Letter):

    def __init__(self, ident:  str, logId:  str) -> None:
        Letter.__init__(
            self,
            Letter.LogRegister,
            {"ident":  ident, "logId":  logId},
            {}
        )

    @staticmethod
    def parse(s:  bytes) -> Optional['LogRegLetter']:
        (type_, header, content) = bytesDivide(s)

        if type_ != Letter.LogRegister:
            return None

        return LogRegLetter(
            ident=header['ident'],
            logId=header['logId']
        )

    def getIdent(self) -> str:
        return self.getHeader('ident')

    def getLogId(self) -> str:
        return self.getHeader('logId')


class ReqLetter(Letter):
    """
    Letter that send from workers to master to
    request something.
    """

    def __init__(self, ident: str, type: str, reqMsg: str) -> None:
        Letter.__init__(self, Letter.Req,
                        {"ident": ident, "type": type},
                        {"reqMsg": reqMsg})

    def getIdent(self) -> str:
        return self.getHeader('ident')

    def getType(self) -> str:
        return self.getHeader('type')

    def setType(self, type: str) -> None:
        self.setHeader('type', type)

    def getMsg(self) -> str:
        return self.getContent('reqMsg')

    def setMsg(self, msg: str) -> None:
        self.setContent('reqMsg', msg)

    @staticmethod
    def parse(s: bytes) -> Optional['ReqLetter']:
        (type_, header, content) = bytesDivide(s)

        if type_ != Letter.Req:
            return None

        return ReqLetter(header['ident'], header['type'], content['reqMsg'])


class HeartbeatLetter(Letter):
    """
    HeartbeatLetter is use to maintain connection
    between master and worker.
    """

    def __init__(self, ident: str, seq: int) -> None:
        Letter.__init__(self, Letter.Heartbeat,
                        {"ident": ident, "seq": str(seq)}, {})

    def setIdent(self, ident: str) -> None:
        self.setHeader('ident', ident)

    def getIdent(self) -> str:
        return self.getHeader('ident')

    def setSeq(self, seq: str) -> None:
        self.setHeader('seq', seq)

    def getSeq(self) -> int:
        return int(self.getHeader('seq'))

    @staticmethod
    def parse(s: bytes) -> Optional['HeartbeatLetter']:
        (type_, header, content) = bytesDivide(s)

        if type_ != Letter.Heartbeat:
            return None

        return HeartbeatLetter(header['ident'], header['seq'])


class TaskLogLetter(Letter):
    """
    Contain message of output of running task.
    """

    def __init__(self, tid: str, message: str) -> None:
        Letter.__init__(self, Letter.TaskLog,
                        {"ident": tid},
                        {"message": message})

    def getIdent(self) -> str:
        return self.getHeader('ident')

    def getMessage(self) -> str:
        return self.getContent("message")

    @staticmethod
    def parse(s: bytes) -> Optional['TaskLogLetter']:
        (type_, header, content) = bytesDivide(s)

        if type_ != Letter.TaskLog:
            return None

        return TaskLogLetter(header['ident'], content['message'])


validityMethods = {
    Letter.NewTask:         newTaskLetterValidity,
    Letter.Response:        responseLetterValidity,
    Letter.PropertyNotify:  propertyLetterValidity,
    Letter.BinaryFile:      binaryLetterValidity,
    Letter.Log:             logLetterValidity,
    Letter.LogRegister:     logRegisterLetterValidity,
    Letter.NewMenu:         lambda letter: True,
    Letter.Command:         lambda letter: True,
    Letter.CmdResponse:     lambda letter: True,
    Letter.Post:            lambda letter: True,
    Letter.TaskCancel:      lambda letter: True,
    Letter.Req:             lambda letter: True,
    Letter.Heartbeat:       lambda letter: True,
    Letter.Notify:          lambda letter: True,
    Letter.TaskLog:         lambda letter: True,
}  # type:   Dict[str, Callable]

parseMethods = {
    Letter.NewTask:          NewLetter,
    Letter.Response:         ResponseLetter,
    Letter.PropertyNotify:   PropLetter,
    Letter.BinaryFile:       BinaryLetter,
    Letter.Log:              LogLetter,
    Letter.LogRegister:      LogRegLetter,
    Letter.Command:          CommandLetter,
    Letter.CmdResponse:      CmdResponseLetter,
    Letter.Post:             PostTaskLetter,
    Letter.TaskCancel:       CancelLetter,
    Letter.Req:              ReqLetter,
    Letter.Heartbeat:        HeartbeatLetter,
    Letter.Notify:           NotifyLetter,
    Letter.TaskLog:          TaskLogLetter
}  # type: Any


# Function to receive a letter from a socket
async def receving(reader: asyncio.StreamReader,
                   timeout=None) -> Optional[Letter]:
    content, remain = b'', 2

    while remain > 0:
        chunk = await asyncio.wait_for(
            reader.read(remain), timeout=timeout
        )

        if chunk == b'':
            raise ConnectionError

        content += chunk
        remain = Letter.letterBytesRemain(content)

    return Letter.parse(content)


async def sending(writer: asyncio.StreamWriter,
                  letter: Letter,
                  lock: asyncio.Lock = None) -> None:
    writer.write(letter.toBytesWithLength())

    if writer.is_closing():
        raise ConnectionError

    # Lock to protect call of drain()
    # concurrent call to drain will
    # cause AssertionError
    if lock is not None:
        async with lock:
            await writer.drain()
    else:
        await writer.drain()

# Function to receive a letter from a socket
def receving_sock(sock: socket.socket) -> Optional[Letter]:
    content = b''
    remain = 2

    # Get first 2 bytes to know is a BinaryFile letter or
    # another letter
    while remain > 0:
        chunk = sock.recv(remain)
        if chunk == b'':
            raise Exception
        remain -= len(chunk)
        content += chunk

    remain = Letter.letterBytesRemain(content)

    while remain > 0:
        chunk = sock.recv(remain)
        if chunk == b'':
            raise Exception

        content += chunk

        remain = Letter.letterBytesRemain(content)

    return Letter.parse(content)


def sending_sock(sock: socket.socket, l: Letter) -> None:
    jBytes = l.toBytesWithLength()
    totalSent = 0
    length = len(jBytes)

    while totalSent < length:
        try:
            sent = sock.send(jBytes[totalSent:])
        except BlockingIOError:
            time.sleep(0.1)
            continue
        except Exception:
            import traceback
            traceback.print_exc()
            return

        if sent == 0:
            raise Exception
        totalSent += sent




# UnitTest
import unittest
from datetime import datetime

class LetterTestCases(unittest.TestCase):

    def test_NewLetter_Parse(self) -> None:
        # Setup
        dateStr = str(datetime.utcnow())
        newLetter = NewLetter("newLetter", "sn_1", "vsn_1",
                              datetime=dateStr, parent="123456",
                              needPost="true", extra={})
        # Exercise
        newLetter = cast(NewLetter, Letter.parse(newLetter.toBytesWithLength()))

        # Verify
        self.assertIsNotNone(newLetter)
        self.assertEqual("sn_1", newLetter.getSN())
        self.assertEqual("vsn_1", newLetter.getVSN())
        self.assertEqual(dateStr, newLetter.getDatetime())
        self.assertEqual('true', newLetter.needPost())
        self.assertEqual('123456', newLetter.getParent())

    def test_ResponseLetter_Parse(self) -> None:
        # Setup
        response = ResponseLetter("ident", "tid_1", Letter.RESPONSE_STATE_IN_PROC, parent = "123456")

        # Exercise
        response_p = cast(ResponseLetter, Letter.parse(response.toBytesWithLength()))  # type: ResponseLetter

        # verify
        self.assertIsNotNone(response_p)
        self.assertEqual("ident", response_p.getIdent())
        self.assertEqual("tid_1", response_p.getTid())
        self.assertEqual(Letter.RESPONSE_STATE_IN_PROC, response_p.getState())
        self.assertEqual("123456", response_p.getParent())

    def test_BinaryLetter_Parse(self) -> None:
        # Setup
        binary = BinaryLetter(
            "tid_1", b"123456",
            menu="menu", fileName="rar", parent="123456")

        binBytes = cast(bytes, binary.binaryPack())
        self.assertIsNotNone(binBytes)

        # Exercise
        binary_parsed = cast(BinaryLetter, Letter.parse(binBytes))

        # Verify
        self.assertIsNotNone(binary_parsed)
        self.assertEqual("tid_1", binary_parsed.getTid())
        self.assertEqual(b"123456", binary_parsed.getBytes())
        self.assertEqual("menu", binary_parsed.getMenu())
        self.assertEqual("123456", binary_parsed.getParent())
        self.assertEqual("rar", binary_parsed.getFileName())

    def test_CommandLetter_Parse(self) -> None:
        # Setup
        commandLetter = CommandLetter("cmd_type", {"1":"1"}, "T", "extra_information")
        commandLetter_bytes = commandLetter.toBytesWithLength()

        # Exercise
        commandLetter_parsed = cast(CommandLetter, Letter.parse(commandLetter_bytes))

        # Verify
        self.assertIsNotNone(commandLetter_parsed)
        self.assertEqual("cmd_type", commandLetter_parsed.getType())
        self.assertEqual("T", commandLetter_parsed.getTarget())
        self.assertEqual("extra_information", commandLetter_parsed.getExtra())
        self.assertEqual("1", commandLetter_parsed.content_("1"))

    def test_CmdResponseLetter_Parse(self) -> None:
        # Setup
        cmdResponseLetter = CmdResponseLetter("wIdent", "post",
                                                CmdResponseLetter.STATE_SUCCESS, reason = "NN",
                                                target = "tt", extra = {})
        cmdRBytes = cmdResponseLetter.toBytesWithLength()

        # Exercise
        cmdRLetter_parsed = cast(CmdResponseLetter, Letter.parse(cmdRBytes))

        # Verify
        self.assertIsNotNone(cmdRLetter_parsed)
        self.assertEqual("wIdent", cmdRLetter_parsed.getIdent())
        self.assertEqual("post", cmdRLetter_parsed.getType())
        self.assertEqual(CmdResponseLetter.STATE_SUCCESS, cmdRLetter_parsed.getState())
        self.assertEqual("NN", cmdRLetter_parsed.getReason())
        self.assertEqual("tt", cmdRLetter_parsed.getTarget())

    def test_HeartbeatLetter_Parse(self) -> None:
        # Setup
        heartbeatLetter = HeartbeatLetter("HB", 1)
        bytestr = heartbeatLetter.toBytesWithLength()

        # Exercise
        heartbeatLetter_parsed = cast(HeartbeatLetter, Letter.parse(bytestr))

        # Verify
        self.assertIsNotNone(heartbeatLetter_parsed)
        self.assertEqual("HB", heartbeatLetter_parsed.getIdent())
        self.assertEqual(1, heartbeatLetter_parsed.getSeq())
