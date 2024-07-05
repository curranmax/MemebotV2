import asyncio
import discord
from discord import app_commands
import pickle
import random
import typing

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

FIREBASE_COLLECTION = 'food_options'


class FoodChooserDiscordCommands(app_commands.Group):

    def __init__(self, food_manager, *args, **kwargs):
        super(FoodChooserDiscordCommands, self).__init__(name='food-chooser',
                                                         *args,
                                                         **kwargs)

        self.food_manager = food_manager

    # Remove a place?
    # List current options with filters for option_type and location.

    @app_commands.command(name='add-option',
                          description='Adds a new food option')
    @app_commands.describe(
        name='The name of the place.',
        is_dine_in='Whether or not dining in is an option.',
        is_pickup='Whehter or not pickup is an option.',
        is_delivery='Whether or not delivery is an option.',
        # TODO For location, do autocomplete for neighborhoods already in the database.
        location='Where neighborhood is the place located.',
    )
    async def add_option(self, interaction: discord.Interaction, name: str,
                         is_dine_in: bool, is_pickup: bool, is_delivery: bool,
                         location: str):
        option = None
        try:
            option_types = []
            if is_dine_in:
                option_types.append(Option.TYPE_DINE_IN)
            if is_pickup:
                option_types.append(Option.TYPE_PICKUP)
            if is_delivery:
                option_types.append(Option.TYPE_DELIVERY)
            option = Option(name, option_types, location)
        except Exception as e:
            await interaction.response.send_message(
                'Error creating Option: {}'.format(e), ephemeral=True)
            return

        try:
            await self.food_manager.addAndSaveOption(option)
        except Exception as e:
            await interaction.response.send_message(
                'Error adding and saving Option: {}'.format(e), ephemeral=True)
            return

        await interaction.response.send_message(
            'Adding new food option was sucessful', ephemeral=True)

    @app_commands.command(name='random',
                          description='Choose some random options.')
    @app_commands.describe(
        num_options='The number of places to randomly choose.',
        is_dine_in=
        'Whether or not to include dine in options (defaults to False).',
        is_pickup=
        'Whether or not to include pickup options (defaults to False).',
        is_delivery=
        'Whether or not to include delivery options (defaults to False).',
        # TODO For location, do autocomplete for neighborhoods already in the database.
        locations=
        'What locations to include. Separate multiple options with commas. Default is to include everything.',
    )
    async def random(self,
                     interaction: discord.Interaction,
                     num_options: int,
                     is_dine_in: typing.Optional[bool] = False,
                     is_pickup: typing.Optional[bool] = False,
                     is_delivery: typing.Optional[bool] = False,
                     locations: typing.Optional[str] = ''):
        locations = list(filter(lambda v: len(v) > 0, locations.split(',')))
        option_types = []
        if is_dine_in:
            option_types.append(Option.TYPE_DINE_IN)
        if is_pickup:
            option_types.append(Option.TYPE_PICKUP)
        if is_delivery:
            option_types.append(Option.TYPE_DELIVERY)
        options = self.food_manager.getRandomOptions(num_options, option_types,
                                                     locations)
        if len(options) == 0:
            await interaction.response.send_message(
                'No options matched your filters!')
            return

        message = 'The randomly chosen options are:'
        for i, option in enumerate(options):
            message += '\n  {}.) {}'.format(i + 1, option.name)
        await interaction.response.send_message(message)


class FoodManager:

    def __init__(self,
                 firebase_key_fname=None,
                 filename='data/food_options.txt'):
        if firebase_key_fname is not None:
            # Not sure if these need to be kept around
            self.cred = credentials.Certificate(firebase_key_fname)
            self.app = firebase_admin.initialize_app(self.cred)

            self.db = firestore.client()
        else:
            self.db = None

        if self.db is None and filename is not None:
            self.filename = filename
        else:
            self.filename = None

        if self.db is None and self.filename is None:
            raise Exception('No backend specified for FoodManager')

        # List of Options
        self.options = []

        self.options_lock = asyncio.Lock()
        self._loadOptions()

    def getDiscordCommands(self):
        return [FoodChooserDiscordCommands(self)]

    def _loadOptions(self):
        if self.db is not None:
            options_ref = self.db.collection(FIREBASE_COLLECTION)
            options_stream = options_ref.stream()
            for option_ref in options_stream:
                option = Option.fromDict(option_ref.to_dict())
                self.options.append(option)
            return

        if self.filename is not None:
            f = open(self.chores_filename, 'rb')
            self.options = pickle.load(f)
            f.close()

    async def addAndSaveOption(self, new_option):
        async with self.options_lock:
            self.options.append(new_option)

            if self.db is not None:
                new_option_ref = self.db.collection(
                    FIREBASE_COLLECTION).document(new_option.documentId())
                new_option_ref.set(new_option.toDict())
                return

            if self.filename is not None:
                f = open(self.filename, 'wb')
                pickle.dump(self.options, f)
                f.close()
                return

    def getRandomOptions(self, num_options, option_types, locations):
        matching_options = [
            option for option in self.options
            if option.typeFilter(option_types)
            and option.locationFilter(locations)
        ]

        return random.sample(matching_options,
                             min(num_options, len(matching_options)))


class Option:
    FIELD_NAME = 'name'
    FIELD_TYPES = 'types'
    FIELD_LOCATION = 'location'

    TYPE_DINE_IN = 'Dine in'
    TYPE_PICKUP = 'Pickup'
    TYPE_DELIVERY = 'Delivery'
    TYPES = [TYPE_DINE_IN, TYPE_PICKUP, TYPE_DELIVERY]

    def fromDict(option_dict):
        name = option_dict[Option.FIELD_NAME]
        types = option_dict[Option.FIELD_TYPES]
        location = option_dict[Option.LOCATION]

        return Option(name, types=types, location=location)

    def __init__(self, name, option_types=[], location=None):
        self.name = name

        if len(option_types) == 0:
            raise Exception('At least one type must be specified')
        if any(t not in Option.TYPES for t in option_types):
            raise Exception('Invalid types: ' + ', '.join(option_types))
        self.option_types = option_types

        self.location = location

        # TODO Add a way to specify when the option is available (time of day and days of the week).

    def documentId(self):
        return self.name

    def toDict(self):
        return {
            Option.FIELD_NAME: self.name,
            Option.FIELD_TYPES: self.option_types,
            Option.FIELD_LOCATION: self.location,
        }

    def typeFilter(self, option_types):
        return any(t in self.option_types for t in option_types)

    def locationFilter(self, locations):
        return len(locations) == 0 or self.location in locations
