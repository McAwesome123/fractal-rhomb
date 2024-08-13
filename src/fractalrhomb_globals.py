# Copyright (C) 2024 McAwesome (https://github.com/McAwesome123)
# This script is licensed under the GNU Affero General Public License version 3 or later.
# For more information, view the LICENSE file provided with this project
# or visit: https://www.gnu.org/licenses/agpl-3.0.en.html

# fractalthorns is a website created by Pierce Smith (https://github.com/pierce-smith1).
# View it here: https://fractalthorns.com

"""General functions for the bot."""

import datetime as dt
import inspect
import json
import logging
import logging.handlers
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import discord
import discord.utils
import requests.exceptions as req

intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

MAX_MESSAGE_LENGTH = 1950
EMPTY_MESSAGE = "give me something to show"

discord_logger = logging.getLogger("discord")


@dataclass
class BotData:
	"""Data class containing bot data/config."""

	bot_channels: dict[str, list[str]]
	purge_cooldowns: dict[str, dict[str, float]]

	def load(self, fp: Path) -> None:
		"""Load data from file."""
		if not fp.exists():
			return

		with fp.open("r") as f:
			data = json.load(f)
			if data.get("bot_channels") is not None:
				self.bot_channels = data["bot_channels"]
			if data.get("purge_cooldowns") is not None:
				self.purge_cooldowns = data["purge_cooldowns"]

	def save(self, fp: Path) -> None:
		"""Save data to file."""
		if fp.exists():
			backup = Path(f"{fp.resolve().as_posix()}.bak")
			fp.replace(backup)
		with fp.open("w") as f:
			json.dump(asdict(self), f)


bot_data = BotData({}, {})

USER_PURGE_COOLDOWN = dt.timedelta(hours=12)
BOT_DATA_PATH = Path("bot_data.json")


def sign(x: int) -> int:
	"""Return 1 if x is positive or -1 if x is negative."""
	return round(math.copysign(1, x))


def truncated_message(
	total_items: int,
	shown_items: int,
	amount: int,
	start_index: int,
	items: str = "items",
) -> str | None:
	"""Get truncation message."""
	message = None

	if amount >= 0 and shown_items < total_items:
		if start_index == 0:
			message = f"the rest of the {total_items} {items} were truncated (limit was {amount})"
		elif start_index < 0:
			message = f"the rest of the {total_items} {items} were truncated (limit was {amount}, starting backwards from {total_items+start_index+1})"
		else:
			message = f"the rest of the {total_items} {items} were truncated (limit was {amount}, starting from {start_index+1})"

	return message


def get_formatting(show: list[str] | tuple[str] | None) -> dict[str, bool] | None:
	"""Get formatting parameters."""
	if show is None:
		return None

	formatting = {}

	for i in show:
		formatting.update({i.lower(): True})

	return formatting


def split_message(message: list[str], join_str: str) -> list[str]:
	"""Split a message that's too long into multiple messages.

	Tries to split by items, then newlines, then spaces, and finally, characters.

	Splitting by anything other than items may eat formatting.
	"""
	split_messages = []
	message_current = ""

	i = 0
	max_loop = 100000
	while i < len(message):
		max_loop -= 1
		if max_loop < 0:  # infinite loop safeguard
			msg = "Loop running for too long."
			raise RuntimeError(msg)

		if len(message[i]) <= MAX_MESSAGE_LENGTH:
			i += 1
			continue

		max_message_length_formatting = MAX_MESSAGE_LENGTH
		if message[i].rfind("\n", 0, max_message_length_formatting) != -1:
			message.insert(
				i + 1,
				message[i][
					message[i].rfind("\n", 0, max_message_length_formatting) + 1 :
				],
			)
			message[i] = message[i][
				: message[i].rfind("\n", 0, max_message_length_formatting)
			]
		elif message[i].rfind(" ", 0, max_message_length_formatting) != -1:
			message.insert(
				i + 1,
				message[i][
					message[i].rfind(" ", 0, max_message_length_formatting) + 1 :
				],
			)
			message[i] = message[i][
				: message[i].rfind(" ", 0, max_message_length_formatting)
			]
		else:
			message.insert(i + 1, message[i][max_message_length_formatting - 1 :])
			message[i] = message[i][: max_message_length_formatting - 1] + "-"

		i += 1

	for i in range(len(message)):
		if len(message_current) + len(message[i]) + len(join_str) > MAX_MESSAGE_LENGTH:
			split_messages.append(message_current)
			message_current = ""

		message_current = join_str.join((message_current, message[i]))

	split_messages.append(message_current)

	return split_messages


async def standard_exception_handler(
	ctx: discord.ApplicationContext, logger: logging.Logger, exc: Exception, cmd: str
) -> None:
	"""Handle standard requests exceptions."""
	cmd_name = cmd
	try:
		frame = inspect.currentframe()
		if frame is not None:
			cmd_name = frame.f_back.f_code.co_qualname
	finally:
		del frame

	msg = f"A request exception occurred in command {cmd_name}"

	response = ""
	level = logging.ERROR
	if isinstance(exc, req.HTTPError):
		response = f"{str(exc).lower()}"
		level = logging.WARNING
	elif isinstance(exc, req.Timeout):
		response = "server request timed out"
	elif isinstance(exc, req.ConnectionError):
		response = "a connection error occurred"
	elif isinstance(exc, req.TooManyRedirects):
		response = "server redirected too many times"

	logger.log(level, msg, exc_info=True)

	await ctx.respond(response)


class BotWarningView(discord.ui.View):
	"""A view for bot channel warnings."""

	def __init__(self) -> "BotWarningView":
		"""Create a bot channel warning view."""
		super().__init__()
		self.value = None

	async def finish_callback(
		self, button: discord.ui.Button, interaction: discord.Interaction
	) -> None:
		"""Finish a callback after pressing a butotn."""
		for i in self.children:
			i.style = discord.ButtonStyle.secondary
		button.style = discord.ButtonStyle.success

		self.disable_all_items()
		await interaction.response.edit_message(view=self)

		self.stop()

	@discord.ui.button(emoji="✔️", label="Yes", style=discord.ButtonStyle.primary)
	async def confirm_button_callback(
		self, button: discord.ui.Button, interaction: discord.Interaction
	) -> None:
		"""Give True if the Yes button is clicked."""
		self.value = True

		await self.finish_callback(button, interaction)

	@discord.ui.button(emoji="❌", label="No", style=discord.ButtonStyle.primary)
	async def decline_button_callback(
		self, button: discord.ui.Button, interaction: discord.Interaction
	) -> None:
		"""Give False if the No button is clicked."""
		self.value = False

		await self.finish_callback(button, interaction)


async def bot_channel_warning(ctx: discord.ApplicationContext) -> bool | None:
	"""Give a warning if the command is not run in a bot channel (if any exist).

	If a warning was not given, or was accepted, returns True. If declined, returns False. If timed out, returns None.
	"""
	if ctx.guild_id is None:
		return True

	guild_id = str(ctx.guild_id)
	if (
		guild_id not in bot_data.bot_channels
		or len(bot_data.bot_channels[guild_id]) < 1
	):
		return True

	channel_id = str(ctx.channel_id)
	if channel_id in bot_data.bot_channels[guild_id]:
		return True

	confirmation = BotWarningView()
	await ctx.respond(
		"❗ you are trying to use a command in a non-bot channel. are you sure?",
		view=confirmation,
		ephemeral=True,
	)
	await confirmation.wait()
	return confirmation.value


async def message_length_warning(
	ctx: discord.ApplicationContext, response: list[str] | None, warn_length: int | None
) -> bool | None:
	"""Give a warning if the command would produce a long response.

	If respones or warn_length are None, or the length of the responses is longer than the warn length, gives a warning.
	If a warning was not given, or was accepted, returns True. If declined, returns False. If timed out, returns None.
	"""
	if response is not None and warn_length is not None:
		total_length = 0
		for i in response:
			total_length += len(i)

		if total_length < warn_length:
			return True

		long = "long"
		if total_length >= 6 * warn_length:
			long = "**very long**"
		elif total_length >= 2.5 * warn_length:
			long = "very long"
		msg = f"❗ this command would produce a {long} response. are you sure?"
	else:
		msg = "❗ this command might produce a long response. are you sure?"

	confirmation = BotWarningView()
	await ctx.respond(
		msg,
		view=confirmation,
		ephemeral=True,
	)
	await confirmation.wait()
	return confirmation.value