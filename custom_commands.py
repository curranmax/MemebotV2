import asyncio
import discord
from discord import app_commands
import logging
import os.path
import re
import typing

CUSTOM_COMMAND_FILENAME = 'data/custom_commands.txt'


class CustomCommands(app_commands.Group):

    def __init__(self, custom_command_manager, *args, **kwargs):
        super(CustomCommands, self).__init__(name='commands', *args, **kwargs)

        self.custom_command_manager = custom_command_manager

    async def autocomplete(
            self, interaction: discord.Interaction,
            current: str) -> typing.List[app_commands.Choice[str]]:
        return await self.custom_command_manager.commandAutocomplete(current)

    # Basic command to replay stuff
    @app_commands.command(name='command', description='Run a command!')
    @app_commands.describe(
        name='The name of the command to run.',
        visible=
        'Overrides the default of showing the command to everyone or not',
    )
    @app_commands.autocomplete(name=autocomplete)
    async def command(self,
                      interaction: discord.Interaction,
                      name: str,
                      visible: typing.Optional[bool] = None):
        command = await self.custom_command_manager.getCommand(name)
        if command is None:
            await interaction.response.send_message(
                'Failed: Command with name "{}" not found'.format(name),
                ephemeral=True)
        else:
            # Determine whether the output is shown to everyone or just the person that ran it.
            if visible is None:
                if command.visible is None:
                    # Use overall default
                    ephemeral = True
                else:
                    # Use command specific default
                    ephemeral = not command.visible
            else:
                # Use command overide
                ephemeral = not visible

            await interaction.response.send_message(command.output,
                                                    ephemeral=ephemeral)


class CustomCommandsAdmin(app_commands.Group):

    def __init__(self, custom_command_manager, *args, **kwargs):
        super(CustomCommandsAdmin, self).__init__(name='commands-admin',
                                                  *args,
                                                  **kwargs)

        self.custom_command_manager = custom_command_manager

    async def autocomplete(self, interaction: discord.Interaction,
                           current: str):
        return await self.custom_command_manager.commandAutocomplete(current)

    # Add / update command
    @app_commands.command(
        name='add-command',
        description=
        'Opens a modal to add a command. Can also overwrite an existing one.')
    @app_commands.describe(
        visible=
        'Whether, by default, the command is visibile to everyone or just the person that runs it. Defaults to False (so command is only visible to the person that runs it).',
    )
    async def add_command(self,
                          interaction: discord.Interaction,
                          visible: typing.Optional[bool] = None):
        await interaction.response.send_modal(
            AddCommandModal(self.custom_command_manager, visible=visible))

    # Remove command
    @app_commands.command(name='remove-command',
                          description='Removes a command.')
    @app_commands.describe(
        name='The name of the command to remove.', )
    @app_commands.autocomplete(name=autocomplete)
    async def remove_command(self, interaction: discord.Interaction,
                             name: str):
        success, msg = await self.custom_command_manager.removeCommand(name)
        await interaction.response.send_message('{} --> {}'.format(
            'Success' if success else 'Failed', msg),
                                                ephemeral=True)


class AddCommandModal(discord.ui.Modal, title='Add Command'):
    name = discord.ui.TextInput(label='Name')
    output = discord.ui.TextInput(label='Output',
                                  style=discord.TextStyle.paragraph)

    def __init__(self, custom_command_manager, visible=None, *args, **kwargs):
        super(AddCommandModal, self).__init__(title='Add a Command',
                                              *args,
                                              **kwargs)
        self.custom_command_manager = custom_command_manager
        self.visible = visible

    async def on_submit(self, interaction: discord.Interaction):
        command = Command(str(self.name),
                          str(self.output),
                          visible=self.visible)
        success, msg = await self.custom_command_manager.addCommand(command)
        await interaction.response.send_message('{} --> {}'.format(
            'Success' if success else 'Failed', msg),
                                                ephemeral=True)


class CustomCommandManager:

    NAME_RE_FORMAT = r'[ a-zA-Z0-9_-]{1,100}'
    NAME_REGEX = re.compile(r'^{}$'.format(NAME_RE_FORMAT))
    OPTIONS_FILE_REGEX = re.compile(
        r'^(?P<name>{})(?:\{{(?P<options>{}:{}(?:,{}:{})*)\}})?$'.format(
            NAME_RE_FORMAT, NAME_RE_FORMAT, NAME_RE_FORMAT, NAME_RE_FORMAT,
            NAME_RE_FORMAT))

    def __init__(self, filename=CUSTOM_COMMAND_FILENAME):
        self.filename = filename

        # Key is Command.name, value is Command.
        # Therefore Command.names must be unique.
        self.commands = {}
        self.commands_lock = asyncio.Lock()

        asyncio.run(self._loadCommands())

    def getDiscordCommands(self):
        return [CustomCommands(self), CustomCommandsAdmin(self)]

    async def _loadCommands(self):
        if not os.path.exists(self.filename):
            await self._saveCommands()
            return

        async with self.commands_lock:
            # Output commands in a human readable format so I can add stuff to the text file directly
            # Format:
            # !name{otion:value,option:value}
            # multi-line output
            # ...
            # ...
            # !name
            # multi-line output
            # ...
            # ...

            f = open(self.filename, 'r')

            current_command = None
            for line in f:
                # On new command, add current_command to
                if len(line) > 0 and line[0] == '!':
                    # Add the previous command
                    if current_command is not None:
                        if current_command.name not in self.commands:
                            self.commands[
                                current_command.name] = current_command
                        else:
                            logging.info('Duplicate command name: %s',
                                         current_command.name)
                        current_command = None
                    # Create a new command
                    match = CustomCommandManager.OPTIONS_FILE_REGEX.match(
                        line[1:].rstrip('\n'))
                    if match is None:
                        logging.info('Invalid file format: %s', line)
                        continue
                    name = match.group("name")
                    options = match.group("options")
                    current_command = Command(name, "", options=options)
                # Add line to "current command"
                elif current_command is not None:
                    v = line.rstrip('\n')
                    if len(current_command.output) > 0:
                        current_command.output += '\n'
                    current_command.output += v

            # Add the last command
            if current_command is not None:
                if current_command.name not in self.commands:
                    self.commands[current_command.name] = current_command
                else:
                    logging.info('Duplicate command name: %s',
                                 current_command.name)

            print('\nLoaded Commands:')
            for name, command in self.commands.items():
                options = command.optionsStr()
                print(
                    name + ("" if options == "" else "{{{}}}".format(options)),
                    '-->', command.output)
            print('')

            f.close()

    async def _saveCommands(self):
        # Format:
        # !name{otion:value,option:value}
        # multi-line output
        # ...
        # ...
        # !name
        # multi-line output
        # ...
        # ...
        async with self.commands_lock:
            f = open(self.filename, 'w')

            for _, command in self.commands.items():
                options = command.optionsStr()
                f.write('!' + command.name +
                        ("" if options == "" else "{{{}}}".format(options)) +
                        '\n')
                f.write(command.output + '\n')

            f.close()

    # Returns (true, msg) on success, and (false, err_msg) on failure.
    # Note this can overwrite an existing command.
    async def addCommand(self, command):
        # Check name format
        if not CustomCommandManager.NAME_REGEX.match(command.name):
            return False, 'Invalid command name "{}". Can only include a-z, A-Z, 0-9, spppaces, underscores, or hyphens. With a length between 1 and 100.'.format(
                command.name)

        # Check output format
        for line in command.output.split('\n'):
            if len(line) > 0 and line[0] == '!':
                return False, 'Invalid output. Lines cannot start with "!"'

        # Updated command.
        msg = ""
        async with self.commands_lock:
            if command.name in self.commands:
                msg = 'Command "{}" updated successfully'.format(command.name)
            else:
                msg = 'Command "{}" added successfully'.format(command.name)
            self.commands[command.name] = command
        await self._saveCommands()
        return True, msg

    async def removeCommand(self, name):
        # Check that the message actually exists.
        if name not in self.commands:
            return False, 'No command with name "{}" exists'.format(name)

        # Remove the command.
        async with self.commands_lock:
            del self.commands[name]
        await self._saveCommands()
        return True, 'Command "{}" removed successfully'.format(name)

    async def getCommand(self, name):
        async with self.commands_lock:
            if name in self.commands:
                return self.commands[name]
            else:
                return None

    def customEditDistance(v1, v2):
        # Convert to lower case
        v1 = v1.lower()
        v2 = v2.lower()

        # Swap the strings if v1 is longer.
        if len(v1) > len(v2):
            v1, v2 = v2, v1

        best_score = None
        for ind in range(0, len(v2) - len(v1) + 1):
            this_score = 0
            for c1, c2 in zip(v1, v2[ind:ind + len(v1)]):
                # TODO handle special characters
                if c1 != c2:
                    this_score += 1
            if best_score is None or this_score < best_score:
                best_score = this_score
            if best_score == 0:
                return best_score
        return best_score

    AUTOCOMPLETE_LIMIT = 25

    async def commandAutocomplete(self, current):
        async with self.commands_lock:
            command_names = [
                app_commands.Choice(name=n, value=n)
                for n, _ in self.commands.items()
            ]

        command_edit_distace = {
            n.name: CustomCommandManager.customEditDistance(n.name, current)
            for n in command_names
        }

        command_names.sort(
            key=lambda n: (command_edit_distace[n.name], n.name))

        if len(command_names) > CustomCommandManager.AUTOCOMPLETE_LIMIT:
            command_names = command_names[:CustomCommandManager.
                                          AUTOCOMPLETE_LIMIT]
        return command_names


class Command:

    def __init__(self, name, output, visible=None, options=None):
        self.name = name
        self.output = output

        self.visible = visible

        if options is not None:
            # Format for options is 'key:value,key:value,key:value'
            entries = options.split(',')
            for entry in entries:
                vs = entry.split(':')
                if len(vs) != 2:
                    continue
                key, value = vs

                if key == 'visible':
                    self.visible = bool(value)

    def optionsStr(self):
        # Format for options is 'key:value,key:value,key:value'
        vs = []
        if self.visible is not None:
            vs.append('visible:' + str(self.visible))
        return ','.join(vs)

    def __str__(self):
        return self.output
