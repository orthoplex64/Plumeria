"""Commands to manage emoji on a server."""

import asyncio
import io
import re

from plumeria.command import commands, CommandError, channel_only
from plumeria.message import Message
from plumeria.message.image import read_image
from plumeria.perms import have_all_perms
from plumeria.transport.transport import ForbiddenError

VALID_EMOJI_NAME_RE = re.compile("^[A-Za-z0-9_]{2,20}$")


@commands.create('emoji create', 'emoji add', 'createemoji', 'addemoji', 'create emoji', 'add emoji',
                 category='Management')
@channel_only
@have_all_perms('manage_emojis')
async def create_emoji(message: Message):
    """
    Creates new emoji.

    Example::

        /drawtext Hello there! | emoji create test

    Requires an input image.
    """
    attachment = await read_image(message)
    if not attachment:
        raise CommandError("No image is available to process.")

    name = message.content.strip().replace(":", "")
    if not VALID_EMOJI_NAME_RE.match(name):
        raise CommandError("Invalid emoji name.")

    def execute():
        buffer = io.BytesIO()
        attachment.image.save(buffer, "png")
        return buffer.getvalue()

    image_data = await asyncio.get_event_loop().run_in_executor(None, execute)

    try:
        # first delete existing emoji
        for emoji in message.server.emojis:
            if not emoji.managed and emoji.name == name:
                await message.server.delete_custom_emoji(emoji)
        await message.server.create_custom_emoji(name=name, image=image_data)
        return "Emoji created as :{}:".format(name)
    except ForbiddenError as e:
        raise CommandError("The bot doesn't have the permissions to do this: {}".format(str(e)))


@commands.create('emoji delete', 'emoji remove', 'deleteemoji', 'removeemoji', 'delete emoji', 'remove emoji',
                 category='Management')
@channel_only
@have_all_perms('manage_emojis')
async def delete_emoji(message: Message):
    """
    Delete custom emoji with a certain name.

    Example::

        /emoji delete example
    """
    name = message.content.strip().replace(":", "")
    try:
        count = 0
        for emoji in message.server.emojis:
            if not emoji.managed and emoji.name == name:
                await message.server.delete_custom_emoji(emoji)
                count += 1
        return "{} deleted.".format(count)
    except ForbiddenError as e:
        raise CommandError("The bot doesn't have the permissions to do this: {}".format(str(e)))


def setup():
    commands.add(create_emoji)
    commands.add(delete_emoji)
