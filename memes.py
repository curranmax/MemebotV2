import discord
from discord import app_commands
import logging

DEFAULT_MEME_FNAME = 'data/memes.txt'


class MemesCommands(app_commands.Group):

    def __init__(self, memes_fname=DEFAULT_MEME_FNAME, *args, **kwargs):
        super(MemesCommands, self).__init__(name='memes', *args, **kwargs)

        self.memes = readMemesFromFile(memes_fname)

        for meme in self.memes:
            self.add_command(meme)


def readMemesFromFile(fname=DEFAULT_MEME_FNAME):
    f = open(fname, 'r')
    memes = []
    for line in f:
        separator_ind = line.strip().find(' ')
        command = line[:separator_ind]
        reply = line[separator_ind + 1:]
        memes.append(Meme(command, reply))
    return memes


class Meme(app_commands.Command):

    def __init__(self, command, reply, *args, **kwargs):
        super(Meme,
              self).__init__(name=command,
                             description='Make the bot say a funny thing',
                             callback=self._handleInteraction,
                             *args,
                             **kwargs)

        self.command = command
        self.reply = reply

    async def _handleInteraction(self, interaction: discord.Interaction):
        logging.info('Replying to meme "{}"'.format(self.command))
        await interaction.response.send_message(self.reply, ephemeral=False)


if __name__ == "__main__":
    memes = readMemesFromFile()
    print(memes)
