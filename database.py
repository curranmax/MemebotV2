
import asyncio
from collections.abc import Callable
import os.path
import typing
import random

import discord
from discord import app_commands

import edit_distance

AUTOCOMPLETE_LIMIT = 25

# Helper function for parsing comma separated lists to lists of strings.
def parseDiscordList(discord_list: str, separator: str = ",") -> list[str]:
    return list(map(lambda v: v.strip(), discord_list.split(separator)))


# ----------------------------------------
# |                                      |
# |            Main Database             |
# |                                      |
# ----------------------------------------

# Helper classes for the database
class Record:
    def __init__(self, record_id: str, fields: dict[str, typing.Any]):
        self.record_id = record_id
        self.fields = fields


class FieldType:
    INT = 'int'
    STR = 'str'
    ENUM = 'enum'
    ALL_TYPES = [INT, STR, ENUM]

    REQUIRED = 'required'  # field must be specfieid as the base_type
    OPTIONAL = 'optional'  # Field can be the base_type or None
    REPEATED = 'repeated'  # Fioeld must be a list of the base_type
    ALL_MODES = [REQUIRED, OPTIONAL, REPEATED]
    
    def __init__(self, base_type: str, mode: str, enum_name: str | None = None):
        self.base_type = base_type
        # Validate base_type
        if self.base_type not in FieldType.ALL_TYPES:
            all_types = ', '.join(map(lambda v: f'"{v}"', FieldType.ALL_TYPES))
            raise Exception(f'Unknown field type "{self.base_type}"; must be one of {all_types}')

        self.mode = mode
        if self.mode not in FieldType.ALL_MODES:
            all_modes = ', '.join(map(lambda v: f'"{v}"', FieldType.ALL_MODES))
            raise Exception(f'Unknown field mode "{self.mode}"; must be one of {all_modes}')

        self.enum_name = enum_name
        # Validate enum_name
        if self.enum_name is not None and self.base_type != FieldType.ENUM:
            raise Exception(f'Only need to specify enum_name when base_type is "{FieldType.ENUM}"; given base_type was "{self.base_type}"')

    # The enum field_type should directly know what its possible enum values are
    def validate(self, value: typing.Any, enum_values: list[EnumValue] | None = None) -> bool:
        if value is None:
            return self.mode == FieldType.OPTIONAL

        # Check INT types
        if self.base_type == FieldType.INT:
            if self.mode == FieldType.REPEATED:
                return isinstance(value, list) and all(map(lambda v: isinstance(v, int), value))
            return isinstance(value, int)
        # Check STR types
        if self.base_type == FieldType.STR:
            if self.mode == FieldType.REPEATED:
                return isinstance(value, list) and all(map(lambda v: isinstance(v, str), value))
            return isinstance(value, str)
        # Check ENUM types
        if self.base_type == FieldType.ENUM:
            if enum_values is None:
                raise Exception(f'When validating field_type of "{self.enum_name}", unexpected enum_values: None')
            if self.mode == FieldType.REPEATED:
                return isinstance(value, list) and all(map(lambda v: v in enum_values, value))
            return v in enum_values

    def query(self, value: typing.Any, pos_values: list[typing.Any] | None) -> bool:
        if pos_values is None:
            return True

        if self.mode == FieldType.OPTIONAL and value is None and pos_values is not None:
            return False

        if self.mode == FieldType.REPEATED:
            for v in values:
                if v in pos_values:
                    return True
            return True
        else:
            return value in pos_values


class EnumValue:
    def __init__(self, enum_type: str, enum_value: str):
        self.enum_type = enum_type
        self.enum_value = enum_value


# Main Database class
class DatabaseImpl:
    def __init__(
            self,
            name: str,
            # Map of unique ID to record
            records: dict[str, Record],
            # Map of field name to FieldType
            record_struct: dict[str, FieldType],
            # Map of enum name to EnumValues
            enums: dict[str, list[EnumValue]],
    ):
        self.name = name

        self.records = records
        self.record_struct = record_structs
        self.enums = enums

        self.next_record_id = 0

        # TODO Move this to a validateAllRecords function
        for record_id, record in self.records.items():
            self.validateRecord(record, record_id=record_id)


    def validateRecord(self, record: Record, record_id: str = None):
        if record_id is not None and record.record_id != record_id:
            raise Exception(f'DB "{self.name}": Record ID "{record_id}" doesn\'t match record "{record.record_id}"')

        for field_name, field_type in self.record_struct.items():
            if field_name not in record.fields:
                # Record is missing a field (Note that optional fields need to be specified but can be None).
                raise Exception(f'DB "{self.name}": Record is missing required field "{field_name}"')

            field_value = record.fields[field_name]
            enum_values = None
            if field_type.base_type == FieldType.ENUM:
                if field_type.enum_name not in self.enums:
                    # The enum of the field_type doesn't exist
                    raise Exception(f'DB "{self.name}": Unknown enum "{field_type.enum_name}"')
                enum_values = self.enums[field_type.enum_name]
            if not field_type.validate(field_value, enum_values):
                # Field value doesn't match field type
                raise Exception(f'DB "{self.name}": Record has invalid value for field "{field_name}": {field_value}')

        # Record has a field that it isn't supposed to
        for field_name, _ in fields.items():
            if field_name not in self.record_struct:
                raise Exception(f'DB "{self.name}": Record has extra field "{field_name}"')

        # Everntyhing has been validated


    def _getNextRecordId(self) -> str:
        # If the first million records are used then something went wrong.
        for i in range(1000000):
            # Found an unused record ID
            if str(self.next_record_id) not in self.records:
                rv = self.next_record_id
                self.next_record_id += 1
                return rv
                
            self.next_record_id += 1

        raise Exception("Failed to find a valid record ID")


    def addRecord(self, **kwargs) -> Record:
        record_id = self._getNextRecordId()
        record = Record(record_id, kwargs)
        self.validateRecord(record)
        self.records[record_id] = record
        return record

    def removeRecord(self, field_name: str, field_value: typing.Any) -> str | None:
        if field_name not in self.record_struct:
            return f'Unknown field name "{field_name}"'

        record_ids_to_remove = [
            record_id
            for record_id, record in self.records.items()
            if record.field[field_name] == field_value
        ]

        if len(record_ids_to_remove) == 0:
            return f'No records found with field "{field_name}" = "{field_value}"'

        for record_id in record_ids_to_remove:
            del self.recordds[record_id]
        return None

    def addEnumValue(self, enum_name: str, enum_value: str) -> str | None:
        if enum_name not in self.enums:
            return f'Unknown enum "{enum_name}"'
        if enum_value in self.enums[enum_name]:
            return f'Enum value "{enum_value}" already exists in enum "{enum_name}"'
        self.enums[enum_name].append(enum_value)
        return None

    def query(self, **kwargs) -> list[Record]:
        rv = []

        query_args = {}
        for field_name, pos_values in kwargs.items():
            if field_name not in self.record_struct:
                raise Exception(f'DB "{self.name}": Unknown field name "{field_name}"')
            query_args[field_name] = (pos_values, self.record_struct[field_name])

        for _, record in self.records.items():
            match = True
            for field_name, (pos_values, field_type) in query_args.items():
                if not field_type.query(record.field[field_name], pos_values):
                    match = False
                    break
            if match:
                rv.append(record)

        return rv

    def getEnumValuesFromFieldName(self, field_name: str) -> list[EnumValue]:
        if field_name not in self.record_struct:
            raise Exception(f'DB "{self.name}": Unknown field name "{field_name}"')
        field_type = self.record_struct[field_name]

        if field_type.base_type != FieldType.ENUM:
            raise Exception(f'DB "{self.name}": Field "{field_name}" is not an enum')

        enum_name = field_type.enum_name
        
        if enum_name is None or enum_name not in self.enums:
            raise Exception(f'DB "{self.name}": Unknown enum "{enum_name}"')

        return self.enums[enum_name]

    
    def autocompleteList(field_name: str, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        # Get the enum values that could be used for this autocomplete
        enum_values = self.getEnumValuesFromFieldName(field_name)

        # Split the current string by commas
        current_values = parseDiscordList(current)

        # If an entry is already an enum_value, then there is nothing to do for that entry
        # If an entry isn't an enum_value, then find the edit distance between the entry and all of the differnet enum_values
        options = edit_distance.Options(
            edit_distance_type = edit_distance.Options.WORD,
            char_distance_type = edit_distance.Options.CHAR_KEYBORAD_DISTANCE,
            ignore_case = True,
        )
        pos_values = []
        for current_value in current_values:
            if current_value in enum_values:
                pos_values.append([(0.0, current_values)])
            else:
                this_pos_values = []
                for enum_value in enum_values:
                    this_pos_values.append((edit_distance.compute(current_value, enum_value, options), enum_value))
                this_pos_values.sort()
                pos_values.append(this_pos_values)

        # TODO use a min heap here instead of checking everything
        current_indexes = [0] * len(pos_values)
        sorted_combinations = []
        while len(sorted_combinations) <= limit:
            sorted_combinations.append(", ".join(map(lambda v: v[1], [vs[i] for i, vs in zip(current_indexes, pos_values)])))
            increment_index = None
            increment_value = None
            for i, vs in zip(current_indexes, pos_values):
                if i >= len(vs) - 1:
                    continue
                if increment_value is None or vs[i+1][0] < increment_value:
                    increment_index = i
                    increment_value = vs[i+1][0]

            if increment_index is None:
                break
            current_indexes[increment_index] += 1

        return sorted_combinations

    def autocompleteSingle(self, field_name: str, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        if field_name not in self.record_struct:
            raise Exception(f'DB "{self.name}": Unknown field name "{field_name}"')
        pos_values = [record.field[field_name] for _, record in self.records.items()]
        options = edit_distance.Options(
            edit_distance_type = edit_distance.Options.WORD,
            char_distance_type = edit_distance.Options.CHAR_KEYBORAD_DISTANCE,
            ignore_case = True,
        )
        weighted_values = [(edit_distance.compute(current, value, options), value) for value in pos_values]
        # TODO Use a min heap instead of sorting the whole list.
        return [value for _, value in sorted(weighted_values)[:limit]]

    def autocompleteEnumNames(self, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        pos_values = [enum_name for enum_name, _ in self.enums.items()]
        options = edit_distance.Options(
            edit_distance_type = edit_distance.Options.WORD,
            char_distance_type = edit_distance.Options.CHAR_KEYBORAD_DISTANCE,
            ignore_case = True,
        )
        weighted_values = [(edit_distance.compute(current, value, options), value) for value in pos_values]
        return [value for _, value in sorted(weighted_values)[:limit]]


# Helpers for loading and saving a DatabaseImpl
def loadDatabase(filenname) -> DatabaseImpl | None:
     # If file does not exist, return None
    if not os.path.exists(filenname):
        return None
    # Otherwise open file, and load the pickled object.
    f = open(filenname, 'rb')
    return pickle.load(f)


def saveDatabase(filename, database_impl):
    f = open(filename, 'wb')
    pickle.dump(database_impl, f)


# Wraps DatabaseImpl with a lock and async accessors.
class AsyncDatabaseWrapper:
    def __init__(self, database_impl: DatabaseImpl, filename: str):
        self.database_impl = database_impl
        self.filename = filename
        self.lock = asyncio.Lock()

    async def addRecord(self, **kwargs) -> Record:
        async with self.lock:
            record = self.database_impl.addRecord(**kwargs)
            saveDatabase(self.filename, self.database_impl)
            return record

    async def removeRecord(self, field_name: str, field_value: typing.Any) -> str | None:
        async with self.lock:
            err = self.database_impl.removeRecord(field_name, field_value)
            saveDatabase(self.filename, self.database_impl)
            return err

    async def addEnumValue(self, enum_name: str, enum_value: str) -> str | None:
        async with self.lock:
            err = self.database_impl.addEnumValue(enum_name, enum_value)
            saveDatabase(self.filename, self.database_impl)
            return err

    async def query(self, **kwargs) -> list[Record]:
        async with self.lock:
            return self.database_impl.query(**kwargs)
    

    async def getEnumValuesFromFieldName(self, field_name: str) -> list[EnumValue]:
        async with self.lock:
            return self.database_impl.getEnumValuesFromFieldName(field_name)


    async def autocompleteList(field_name: str, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        async with self.lock:
            return self.database_impl.autocompleteList(field_name, current, limit = limit)

    async def autocompleteSingle(self, field_name: str, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        async with self.lock:
            return self.database_impl.autocompleteSingle(field_name, current, limit = limit)

    async def autocompleteEnumNames(current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        async with self.lock:
            return self.database_impl.autocompleteEnumNames(current, limit = limit)


# ----------------------------------------
# |                                      |
# |              Restaurants             |
# |                                      |
# ----------------------------------------

class RestaurantDiscordCommands(app_commands.Group):
    def __init__(self, restaurant_database, *args, **kwargs):
        super(OwTrackerDiscordCommands, self).__init__(name='restaurant-db', *args, **kwargs)
        self.restaurant_database = restaurant_database

    async def locationListAutocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        sorted_autocomplete_values = await self.restaurant_database.autocompleteList("locations", current)
        return [app_commands.Choice(name=v, value=v) for v in sorted_autocomplete_values]

    async def cuisineListAutocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        sorted_autocomplete_values = await self.restaurant_database.autocompleteList("cuisines", current)
        return [app_commands.Choice(name=v, value=v) for v in sorted_autocomplete_values]

    async def eatingOptionsListAutocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        sorted_autocomplete_values = await self.restaurant_database.autocompleteList("eating_options", current)
        return [app_commands.Choice(name=v, value=v) for v in sorted_autocomplete_values]

    async def enumNameAutocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        sorted_enum_names = await self.restaurant_database.autocompleteEnumNames(current)
        return [app_commands.Choice(name=v, value=v) for v in sorted_enum_names]

    async def enumValueAutocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        enum_name = interaction.namespace["enum_name"]
        sorted_enum_values = await self.restaurant_database.autocompleteEnumValues(current, enum_name=enum_name)
        return [app_commands.Choice(name=v, value=v) for v in sorted_enum_values]

    async def restaurantNameAutocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        sorted_restaurant_names = await self.restaurant_database.autocompleteSingle("name", current)
        return [app_commands.Choice(name=v, value=v) for v in sorted_restaurant_names]

    @app_commands.command(name='add-restaurant', description='Add a restaurant to the database')
    @app_commands.describe(
        name='Name of the restaurant',
        locations='Comma separated list of locations associated with the restaurant',
        cuisines='Comma separated list of cuisines that the restaurant serves',
        eating_options='Comma separated list of eating options that the restaurant offers',
        hours='Free form string with the general hours of the restaurant',
        url='URL of the restaurant',
    )
    @app_commands.autocomplete(
        locations=locationListAutocomplete,
        cuisines=cuisineListAutocomplete,
        eating_options=eatingOptionsListAutocomplete,
    )
    async def add_restaurant(
            self,
            interaction: discord.Interaction,
            name: str,
            locations: str,
            cuisines: str,
            eating_options: str,
            hours: typing.Optional[str] = None,
            url: typing.Optional[str] = None,
    ):
        new_record = await self.restaurant_database.addRestaurant(
            name = name,
            locations = parseDiscordList(locations),
            cuisines = parseDiscordList(cuisines),
            eating_options = parseDiscordList(eating_options),
            hours = hours,
            url = url,
        )
        new_record_str = self.restaurant_database.restaurantRecordToStr(new_record)
        await interaction.response.send_message(f'Successfully added new restaurant!\n\n{new_record_str}')

    # TODO Add more powerful querying syntax
    @app_commands.command(name='query', description='Query the database. Returned restaurants must match the locations, cuisines, and eating_options filter.')
    @app_commands.describe(
        locations='Comma separated list of locations. The returned restaurants will have at least one of these locations. If this option not set, then the locations field won\'t be checked.',
        cuisines='Comma separated list of cuisines. The returned restaurants will have at least one of these locations. If this option not set, then the cuisines field won\'t be checked.',
        eating_options='Comma separated list of eating options. The returned restaurants will have at least one of these locations. If this option not set, then the eating_options field won\'t be checked.',
        num_restaurants='The number of restaurants to include in the response (If less than zero, then all matching restaurants will be returned). The order of the restaurants will be random.',
        ephemeral='Whether or not to send the response as an ephemeral message (visible only to you).',
    )
    @app_commands.autocomplete(
        locations=locationListAutocomplete,
        cuisines=cuisineListAutocomplete,
        eating_options=eatingOptionsListAutocomplete,
    )
    async def query(
        self,
        interaction: discord.Interaction,
        locations: typing.Optional[str] = None,
        cuisines: typing.Optional[str] = None,
        eating_options: typing.Optional[str] = None,
        num_restaurants: typing.Optional[int] = 5,
        ephemeral: typing.Optional[bool] = False,
    ):
        args = {}
        if locations is not None:
            args["locations"] = parseDiscordList(locations)
        if cuisines is not None:
            args["cuisines"] = parseDiscordList(cuisines)
        if eating_options is not None:
            args["eating_options"] = parseDiscordList(eating_options)
        matching_records = await self.restaurant_database.query(**args)

        total_matches = len(matching_records)

        if num_restaurants >= 0 and num_restaurants < len(matching_records):
            matching_records = random.sample(matching_records, num_restaurants)

        msg = f'Found {total_matches} restaurants that matched this query:\n'
        for record in matching_records:
            msg += '* ' + self.restaurant_database.restaurantRecordToStr(record) + '\n'
        await interaction.response.send_message(msg, ephemeral = ephemeral)

    @app_commands.command(name='add-enum-value', description='Adds a new enum value to the database.')
    @app_commands.describe(
        enum_name='The name of the enum to add the value to.',
        new_enum_value='The value to add to the enum.',
    )
    @app_commands.autocomplete(
        enum_name=self.enumNameAutocomplete,
    )
    async def add_enum_value(
        self,
        interaction: discord.Interaction,
        enum_name: str,
        new_enum_value: str,
    ):
        err = await self.restaurant_database.addEnumValue(enum_name, new_enum_value)

        if err is None:
            msg = f'Successfully added new enum value "{new_enum_value}" to enum "{enum_name}"'
        else:
            msg = err
        
        await interaction.response.send_message(msg)

    @app_commands.command(name='remove-restaurant', description='Removes a restaurant from the database.')
    @app_commands.describe(
        name='The name of the restaurant to remove.',
    )
    @app_commands.autocomplete(
        name=self.restaurantNameAutocomplete,
    )
    async def remove_restaurant(
        self,
        interaction: discord.Interaction,
        name: str,
    ):
        err = await self.restaurant_database.removeRestaurant(name)
        if err is None:
            msg = f'Successfully removed restaurant "{name}"'
        else:
            msg = err
        await interaction.response.send_message(msg)

    @app_commands.command(name='remove-enum-value', description='Removes a enum value from the given enum. Also removes the enum value from any restaurants in the db.')
    @app_commands.describe(
        enum_name='The name of enum to remove the value from.',
        enum_value='The value to remove from the enum.',
    )
    @app_commands.autocomplete(
        enum_name=self.enumNameAutocomplete,
        enum_value=self.enumValueAutocomplete,
    )
    async def remove_restaurant(
        self,
        interaction: discord.Interaction,
        enum_name: str,
        enum_value: str,
    ):
        err = await self.restaurant_database.removeEnumValue(enum_name, enum_value)
        if err is None:
            msg = f'Successfully removed enum_value "{enum_value}" from enum "{enum_name}"'
        else:
            msg = err
        await interaction.response.send_message(msg)


class RestaurantDatabase:
    def __init__(self, filenname = "data/restaurant_database.pickle"):
        record_struct = {
            "name": FieldType(FieldType.STR, FieldType.REQUIRED),
            "locations": FieldType(FieldType.ENUM, FieldType.REPEATED, "locations"),
            "cuisines": FieldType(FieldType.ENUM, FieldType.REPEATED, "cuisines"),
            "eating_options": FieldType(FieldType.ENUM, FieldType.REPEATED, "eating_options"),
            "hours": FieldType(FieldType.STR, FieldType.OPTIONAL),
            "url": FieldType(FieldType.STR, FieldType.OPTIONAL),

            # TODO maybe add other fields: google maps URL, description, ...
        }
        base_enums = {
            "locations": [],
            "cuisines": [],
            "eating_options": [
                EnumValue("eating_options", "delivery"),
                EnumValue("eating_options", "pick-up"),
                EnumValue("eating_options", "dine-in"),
            ],
        }

        # Try and load the database from file, if not initialize it to empty with the right fields.
        database_impl = loadDatabase(filename)
        if database_impl is None:
            # Init the database if there isn't a saved version.
            database_impl = DatabaseImpl("restaurants", dict(), record_struct, base_enums)
            saveDatabase(filename, database_impl)

        # TODO Make sure that database_impl matches with record_struct and base_enums. It's okay if the loaded version has extra enum_values.

        # Wrap the database_impl in an AsyncDatabaseWrapper.
        self.async_database = AsyncDatabaseWrapper(database_impl, filename)

    def getDiscordCommands(self):
        return [RestaurantDiscordCommands(self)]

    # kwargs should match record_struct
    async def addRestaurant(self, **kwargs) -> Record:
        await self.async_database.addRecord(**kwargs)

    async def removeRestaurant(self, name: str) -> str | None:
        return await self.async_database.removeRestaurant("name", name)

    async def addEnumValue(self, enum_name: str, enum_value: str) -> str | None:
        return await self.async_database.addEnumValue(enum_name, enum_value)

    async def query(self, **kwargs) -> list[Record]:
        return await self.async_database.query(**kwargs)

    async def autocompleteList(self, field_name: str, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        return await self.async_database.autocompleteList(field_name, current, limit = limit)

    async def autocompleteSingle(self, field_name: str, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        return await self.async_database.autocompleteSingle(field_name, current, limit = limit)

    async def autocompleteEnumNames(self, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        return await self.async_database.autocompleteEnumNames(current, limit = limit)

    async def autocompleteEnumValues(self, current: str, enum_name: str | None = None, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        raise Exception('Enum value autocomplete is not implemented yet.')

    async def getEnumValuesFromFieldName(self, field_name: str) -> list[EnumValue]:
        return await self.async_database.getEnumValuesFromFieldName(field_name)

    def restaurantRecordToStr(self, record: Record) -> str:
        name = record.field["name"]
        locations = record.field["locations"]
        cuisines = record.field["cuisines"]
        eating_options = record.field["eating_options"]
        hours = record.field["hours"]
        url = record.field["url"]

        rv = ""
        if url is None:
            rv += f"**{name}**: "
        else:
            rv += f"**[{name}]({url})**: "

        location_str = ", ".join(map(lambda v: f'"{v.enum_value}"', locations)) if len(locations) > 0 else "None"
        rv += f"*Location Tags* = {location_str}"

        cuisine_str = ", ".join(map(lambda v: f'"{v.enum_value}"', cuisines)) if len(cuisines) > 0 else "None"
        rv += f"; *Cuisine Tags* = {cuisine_str}"

        eating_option_str = ", ".join(map(lambda v: f'"{v.enum_value}"', eating_options)) if len(eating_options) > 0 else "None"
        rv += f"; *Eating Option Tags* = {eating_option_str}"

        if hours is not None:
            rv += f"; *Hours*: \"{hours}\""

        return rv





# Next Steps 12/20:
#  * (DONE) Implemented autocomplete functions
#  * (DONE) Implement the query command
#    * All records or random k records
#    * Selection criteria
#  * (Done) Implement command to add enum value
#  * (Done) Delete record (by name? by id?)
#  * Delete enum value (by name)
#     * Need to go and delete the enum value from any records
#  * Update commands? (not really needed if we have delete+add)