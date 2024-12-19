import asyncio
import discord
from discord import app_commands
import typing
import random

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

AUTOCOMPLETE_LIMIT = 25

# Move this to a central util file.
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

        # Add score based on ind. The goal is that matches of equal length earlier in the string are better.
        this_score += 0.5 * (ind / len(v2))
        
        if best_score is None or this_score < best_score:
            best_score = this_score
        if best_score == 0:
            return best_score
    return best_score


class DatabaseDiscordCommands(app_commands.Group):
    def __init__(self, database_manager, *args, **kwargs):
        super(DatabaseDiscordCommands, self).__init__(name='database',
                                                       *args,
                                                       **kwargs)

        self.database_manager = database_manager

    def _splitVals(self, v: str) -> typing.List[str]:
        return [t.strip() for t in v.split(',')]

    async def typeAutocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        all_types = await self.database_manager.getAllTypes()
        all_types_edit_distance = {
            t: customEditDistance(t, current)
            for t in all_types
        }

        all_types.sort(key=lambda t: (all_types_edit_distance[t], t))

        if len(all_types) > AUTOCOMPLETE_LIMIT:
            all_types = all_types[:AUTOCOMPLETE_LIMIT]

        return [app_commands.Choice(name=t, value=t) for t in all_types]

    async def multiTypeAutocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        # Only does autocomplete on the last tag in the list
        current_types = self._splitVals(current)
        if len(current_types) >= 1:
            current_type = current_types[-1]
            prefix_types = current_types[:-1]
        else:
            current_type = ''
            prefix_types = []

        all_types = await self.database_manager.getAllTypes()
        all_types_edit_distance = {
            t: customEditDistance(t, current_type)
            for t in all_types
        }

        all_types.sort(key=lambda t: (all_types_edit_distance[t], t))

        if len(all_types) > AUTOCOMPLETE_LIMIT:
            all_types = all_types[:AUTOCOMPLETE_LIMIT]

        # Add in the previous tags that aren't apart of the autocomplete.
        all_types = [', '.join(prefix_types + [t]) for t in all_types]

        return [app_commands.Choice(name=t, value=t) for t in all_types]

    async def multiTagAutocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        # Only does autocomplete on the last tag in the list
        current_tags = self._splitVals(current)
        if len(current_tags) >= 1:
            current_tag = current_tags[-1]
            prefix_tags = current_tags[:-1]
        else:
            current_tag = ''
            prefix_tags = []

        all_tags = await self.database_manager.getAllTags()
        all_tags_edit_distance = {
            t: customEditDistance(t, current_tag)
            for t in all_tags
        }

        all_tags.sort(key=lambda t: (all_tags_edit_distance[t], t))

        if len(all_tags) > AUTOCOMPLETE_LIMIT:
            all_tags = all_tags[:AUTOCOMPLETE_LIMIT]
        
        # Add in the previous tags that aren't apart of the autocomplete.
        all_tags = [', '.join(prefix_tags + [t]) for t in all_tags]

        return [app_commands.Choice(name=t, value=t) for t in all_tags]

    @app_commands.command(name='add-thing', description='Add a thing to the database')
    @app_commands.describe(
        name='The name of the thing. Must be unique across all things.',
        type='The type of the thing.',
        tags='The tags of this thing. Tags should be separated by commas. Also all tags need to be registered first by using the "add-tag" command.'
    )
    @app_commands.autocomplete(type=typeAutocomplete, tags=multiTagAutocomplete)
    async def add_thing(self, interaction: discord.Interaction, name: str, type: str, tags: typing.Optional[str]= ''):
        new_thing = Thing(
            name,
            type,
            self._splitVals(tags),
            # TODO - Add a way to specify metadata
            {},
        )
        err_msg = await self.database_manager.addThing(new_thing)
        if err_msg is not None:
            await interaction.response.send_message(f'Error while adding "{new_thing.name}": {err_msg}.', ephemeral=True)
        else:
            await interaction.response.send_message(f'Added "{new_thing.name}" to the database.')

    @app_commands.command(name='add-tag', description='Add a tag that can be used for new things in the database')
    @app_commands.describe(tag='The name of the tag. Must be unique across all tags.')
    async def add_tag(self, interaction: discord.Interaction, tag: str):
        err_msg = await self.database_manager.addTag(tag)
        if err_msg is not None:
            await interaction.response.send_message(f'Error while adding "{tag}": {err_msg}.', ephemeral=True)
        else:
            await interaction.response.send_message(f'Added new tag "{tag}".')

    @app_commands.command(name='query', description='Queries the database for things with specified types + tags.')
    @app_commands.describe(
        types='The set of types (separated by commas) which the things must be one of. Note cannot be empty.',
        tags='The set of tags (separated by commas) which the things must have all of. Note can be empty.',
        num='The number of things to return. If not set or less than or equal to zero, then all matching things will be returned. Note the order of the things will be randomized.',
        visible='Whether or not the results are shown to everyone (True + Default), or shown just to the user that ran the query (False).',
    )
    @app_commands.autocomplete(types=multiTypeAutocomplete, tags=multiTagAutocomplete)
    async def query(self, interaction: discord.Interaction, types: str, tags: typing.Optional[str] = '', num: typing.Optional[int] = -1, visible: typing.Optional[bool] = True):
        matching_things = await self.database_manager.query(self._splitVals(types), self._splitVals(tags))

        if len(matching_things) <= 0:
            await interaction.response.send_message('No matching things found.', ephemeral=not visible)
            return

        num = min(num, len(matching_things)) if num >= 1 else len(matching_things)
        things = random.sample(matching_things, num)

        # Format the output
        message = 'The results of the query are:'
        for i, thing in enumerate(things):
            # TODO Include metadata possibly.
            message += f'\n  {i + 1}) {thing.name}'

        # Send the output
        await interaction.response.send_message(message, ephemeral=not visible)


class DatabaseManager:

    TYPES_COLLECTION = 'types'
    TAGS_COLLECTION = 'tags'
    THINGS_COLLECTION = 'things'

    def __init__(self, firebase_key_fname: str | None = None):
        if firebase_key_fname is not None:
            # Not sure if these need to be kept around
            self.cred = credentials.Certificate(firebase_key_fname)
            self.app = firebase_admin.initialize_app(self.cred)

            self.db = firestore.client()
        else:
            self.db = None

        # Map from types to possible sub-types.
        self.types = {}

        # List of possible tags.
        self.tags = []

        # List of things.
        self.things = []

        self.data_lock = asyncio.Lock()
        self._loadFromDatabase()

    def getDiscordCommands(self):
        return [DatabaseDiscordCommands(self)]

    def _loadFromDatabase(self):
        if self.db is None:
            return
        
        # Populate self.types.
        types_ref = self.db.collection(DatabaseManager.TYPES_COLLECTION)
        types_stream = types_ref.stream()
        for type_ref in types_stream:
            self.types[type_ref.id] = type_ref.get("sub_types")

        # Populate self.tags.
        tags_ref = self.db.collection(DatabaseManager.TAGS_COLLECTION)
        tags_stream = tags_ref.stream()
        for tag_ref in tags_stream:
            self.tags.append(tag_ref.id)

        # Populate self.things.
        things_ref = self.db.collection(DatabaseManager.THINGS_COLLECTION)
        things_stream = things_ref.stream()
        for thing_ref in things_stream:
            self.things.append(Thing(thing_ref.id,
                                        thing_ref.get('sub_type'),
                                        thing_ref.get('tags'),
                                        thing_ref.get('metadata')))
    
    async def addTag(self, new_tag):
        async with self.data_lock:
            if new_tag in self.tags:
                return 'Tag already exists'

            self.tags.append(new_tag)

            if self.db is None:
                return
            
            new_tag_ref = self.db.collection(DatabaseManager.TAGS_COLLECTION).document(new_tag)
    
    async def addThing(self, new_thing):
        async with self.data_lock:
            if new_thing in self.things:
                return 'Thing with the same name already exists'

            if not any(new_thing.sub_type in sts for _, sts in self.types.items()):
                return f'Type "{new_thing.sub_type}" is not valid'

            # TODO - Maybe disallow duplicate tags in a thing.

            for tag in new_thing.tags:
                if tag not in self.tags:
                    return f'Tag "{tag}" does not exist (use add-tag command to add it)'

            self.things.append(new_thing)

            if self.db is None:
                return
            
            new_thing_ref = self.db.collection(DatabaseManager.THINGS_COLLECTION).document(new_thing.name)
            new_thing_ref.set({
                'sub_type': new_thing.sub_type,
                'tags': new_thing.tags,
                'metadata': new_thing.metadata,
            })

    async def getAllTypes(self):
        async with self.data_lock:
            return [t for _, sts in self.types.items() for t in sts]

    async def getAllTags(self):
        async with self.data_lock:
            # Return a copy of self.tags.
            return [t for t in self.tags]

    async def query(self, types: typing.List[str], tags: typing.List[str]):
        async with self.data_lock:
            # Return a copy of self.things.
            return [
                thing for _, thing in self.things
                    if thing.sub_type in types and 
                    all(tag in thing.tags for tag in tags)
            ]


class Thing:
    def __init__(self, name: str, sub_type: str, tags: typing.List[str], metadata: typing.Mapping[str, str]):
        self.name = name
        self.sub_type = sub_type
        self.tags = tags
        self.metadata = metadata

    def __eq__(self, other):
        if not isinstance(other, Thing):
            return False
        # Match only by name
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)