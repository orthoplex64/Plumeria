import asyncio
import io
import logging
from collections import deque

from PIL import Image

from plumeria.transport import Channel
from plumeria.transport import Server
from plumeria.util.http import DefaultClientSession

MAX_BODY_LENGTH = 1900
MAX_LINES = 50
CONTINUATION_STRING = "\n..."

logger = logging.getLogger(__name__)


def create_stack():
    return deque(maxlen=20)


class Message:
    def __init__(self):
        super().__init__()
        self.registers = {}
        self.stack = create_stack()

    async def respond(self, content):
        if isinstance(content, Response):
            if len(content.attachments):
                return await self.channel.send_file(io.BytesIO(await content.attachments[0].read()),
                                                    filename=content.attachments[0].filename,
                                                    content=content.content)
            else:
                body = content.content.strip()
                lines = body.splitlines()

                if len(body) > MAX_BODY_LENGTH or len(lines) > MAX_LINES:
                    buffer = io.StringIO()
                    current_length = len(CONTINUATION_STRING)
                    line_count = 0
                    first = True

                    for line in lines:
                        line_length = len(line)
                        if current_length + line_length > MAX_BODY_LENGTH or line_count > MAX_LINES - 1:
                            break
                        else:
                            if first:
                                first = False
                            else:
                                buffer.write("\n")
                            buffer.write(line)
                            current_length += line_length
                            line_count += 1

                    truncated_body = buffer.getvalue() + CONTINUATION_STRING

                    return await self.channel.send_file(io.BytesIO(body.encode("utf-8")),
                                                        filename="continued.txt",
                                                        content=truncated_body)
                else:
                    return await self.channel.send_message(content.content)
        else:
            return await self.channel.send_message(content)

    def __repr__(self, *args, **kwargs):
        return repr(self.__dict__)

    def __str__(self, *args, **kwargs):
        return repr(self.__dict__)

    def _ide_hint(self):
        # fix unresolved attribute errors
        self.id = None
        self.edited_timestamp = None
        self.timestamp = None
        self.tts = None
        self.type = None
        self.author = None
        self.content = None
        self.nonce = None
        self.embeds = None
        self.channel = None  # type: Channel
        self.server = None  # type: Server
        self.call = None
        self.mention_everyone = None
        self.channel_mentions = None
        self.role_mentions = None
        self.attachments = None
        self.pinned = None
        self.raw_mentions = None
        self.raw_channel_mentions = None
        self.raw_role_mentions = None
        self.clean_content = None
        self.system_content = None


class ProxyMessage:
    def __init__(self, message):
        super().__init__()
        self.delegate = message

    async def respond(self, content):
        return await self.delegate.respond(content)

    def __getattr__(self, item):
        return getattr(self.delegate, item)


class Response:
    def __init__(self, content="", attachments=None, registers=None, stack=None):
        self.content = content
        self.attachments = attachments or []
        self.registers = registers
        self.stack = stack


class Attachment:
    url = None
    filename = None
    mime_type = None

    async def read(self):
        raise NotImplemented()

    def copy(self):
        raise NotImplemented()


class MemoryAttachment:
    def __init__(self, bytes, filename, mime_type):
        self.bytes = bytes
        self.filename = filename
        self.mime_type = mime_type

    async def read(self):
        return self.bytes.getvalue()

    def copy(self):
        return self


class URLAttachment:
    def __init__(self, url, filename, mime_type):
        self.url = url
        self.filename = filename
        self.mime_type = mime_type

    async def read(self):
        with DefaultClientSession() as session:
            async with session.get(self.url) as resp:
                if resp.status == 200:
                    return await resp.read()
                else:
                    raise IOError("Did not get 200 status")

    def copy(self):
        return self


class ImageAttachment(Attachment):
    def __init__(self, image: Image, filename):
        self.image = image
        self.filename = filename + ".png"
        self.mime_type = 'image/png'

    async def read(self):
        def execute():
            out = io.BytesIO()
            self.image.save(out, 'png')
            return out.getvalue()

        return await asyncio.get_event_loop().run_in_executor(None, execute)

    def copy(self):
        return ImageAttachment(self.image.copy(), self.filename)