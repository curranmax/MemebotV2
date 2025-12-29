
import asyncio
from collections.abc import Callable
import copy
import os.path
import pickle
import traceback
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
    def __init__(self, fields: dict[str, typing.Any]):
        self.fields = fields

    def getKey(self, keys: tuple[str]) -> tuple[typing.Any]:
        return tuple(map(lambda k: self.fields[k], keys))


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

        # TODO Add a is_key field.

    # The enum field_type should directly know what its possible enum values are
    def validate(self, value: typing.Any, enum_values: list[str] | None = None) -> bool:
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


# Main Database class
class DatabaseImpl:
    def __init__(
            self,
            name: str,
            # List of Records. Internally this will be changed to a dict of key to Record
            records: list[Record],
            # Tuple of the field names that are used as the key
            keys: tuple[str],
            # Map of field name to FieldType
            record_struct: dict[str, FieldType],
            # Map of enum name to enum values
            enums: dict[str, list[str]],
    ):
        self.name = name

        # Validate that the keys appear in record_struct
        if not all(key in record_struct for key in keys):
            raise Exception('Invalid set of keys.')

        self.keys = keys
        self.record_struct = record_struct
        self.enums = enums

        # Map the records to their key
        self.records: dict[tuple[typing.Any], Record] = {record.getKey(self.keys): record for record in records}

        for _, record in self.records.items():
            self.validateRecord(record)

    # TODO have this return a str error which can either be raised or sent to the user.
    def validateRecord(self, record: Record):
        for key in self.keys:
            if key not in record.fields:
                # Record is missing a field that is required for the key.
                raise Exception(f'DB "{self.name}": Record is missing key field "{key}"')

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
        for field_name, _ in record.fields.items():
            if field_name not in self.record_struct:
                raise Exception(f'DB "{self.name}": Record has extra field "{field_name}"')

        # Everntyhing has been validated

    def addRecord(self, **kwargs) -> (Record | None, str | None):
        record = Record(kwargs)
        if record.getKey(self.keys) in self.records:
            key_str = ', '.join(record.getKey(self.keys))
            return None, f'Record with key "{key_str}" already exists'
        self.validateRecord(record)
        self.records[record.getKey(self.keys)] = record
        return record, None

    def removeRecordByKey(self, key: tuple[typing.Any]) -> str | None:
        if key not in self.records:
            return f'Record with key "{key}" does not exist'
        del self.records[key]
        return None

    def updateRecordByKey(self, key: tuple[typing.Any], **kwargs) -> (Record | None, str | None):
        if key not in self.records:
            return None, f'Record with key "{key}" does not exist'

        # Copy the record
        new_record = copy.deepcopy(self.records[key])

        # Update the copy
        for field_name, field_value in kwargs.items():
            new_record.fields[field_name] = field_value

        # Validate the record
        self.validateRecord(new_record)

        
        new_key = new_record.getKey(self.keys)
        if new_key != key:
            # If the key changed, check that the new key doesn't exist then remove the old version.
            if new_key in self.records:
                return None, f'Record with key "{new_key}" already exists'
            del self.records[key]
        # Update the entry for the new record.
        self.records[new_key] = new_record
        return new_record, None
        

    def addEnumValue(self, enum_name: str, enum_value: str) -> str | None:
        if enum_name not in self.enums:
            return f'Unknown enum "{enum_name}"'
        if enum_value in self.enums[enum_name]:
            return f'Enum value "{enum_value}" already exists in enum "{enum_name}"'
        self.enums[enum_name].append(enum_value)
        return None

    def removeEnumValue(self, enum_name: str, enum_value: str) -> str | None:
        if enum_name not in self.enums:
            return f'Unknown enum "{enum_name}"'
        if enum_value not in self.enums[enum_name]:
            return f'Enum value "{enum_value}" is not in enum "{enum_name}"'
        
        # Remove the enum value from the enum.
        self.enums[enum_name].remove(enum_value)

        # Remove the enum_value from all records
        for _, record in self.records.items():
            if enum_value in record.fields[enum_name]:
                record.fields[enum_name].remove(enum_value)

        return None

    def updateEnumValue(self, enum_name: str, old_enum_value: str, new_enum_value: str) -> str | None:
        if enum_name not in self.enums:
            return f'Unknown enum "{enum_name}"'
        if old_enum_value not in self.enums[enum_name]:
            return f'Old enum value "{old_enum_value}" is not in enum "{enum_name}"'
        if new_enum_value not in self.enums[enum_name]:
            return f'New enum value "{new_enum_value}" already exists in enum "{enum_name}"'

        # Update enum value in self.enums[enum_name]
        for i in range(len(self.enums[enum_name])):
            if self.enums[enum_name][i] == old_enum_value:
                self.enums[enum_name][i] = new_enum_value

        # Update all records that have the old_enum_value
        for _, record in self.records.items():
            if old_enum_value in record.fields[enum_name]:
                for i in range(len(self.record.fields[enum_name])):
                    if self.record.fields[enum_name][i] == old_enum_value:
                        self.record.fields[enum_name][i] = new_enum_value

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
                if not field_type.query(record.fields[field_name], pos_values):
                    match = False
                    break
            if match:
                rv.append(record)

        return rv

    def getEnumValuesFromFieldName(self, field_name: str) -> list[str]:
        if field_name not in self.record_struct:
            raise Exception(f'DB "{self.name}": Unknown field name "{field_name}"')
        field_type = self.record_struct[field_name]

        if field_type.base_type != FieldType.ENUM:
            raise Exception(f'DB "{self.name}": Field "{field_name}" is not an enum')

        enum_name = field_type.enum_name
        
        if enum_name is None or enum_name not in self.enums:
            raise Exception(f'DB "{self.name}": Unknown enum "{enum_name}"')

        return self.enums[enum_name]

    def autocompleteList(self, field_name: str, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        if field_name not in self.record_struct:
            raise Exception(f'DB "{self.name}": Unknown field name "{field_name}"')
        if self.record_struct[field_name].base_type == FieldType.ENUM:
            pos_field_values = self.getEnumValuesFromFieldName(field_name)
        else:
            pos_field_values = list(set(record.fields[field_name] for _, record in self.records.items() if record.field[field_name] is not None))

        # Split the current string by commas
        current_values = parseDiscordList(current)
        print(f'current_values={current_values}')

        # If an entry is already an enum_value, then there is nothing to do for that entry
        # If an entry isn't an enum_value, then find the edit distance between the entry and all of the differnet enum_values
        options = edit_distance.Options(
            edit_distance_type = edit_distance.Options.WORD,
            char_distance_type = edit_distance.Options.CHAR_KEYBORAD_DISTANCE,
            ignore_case = True,
        )
        pos_values = []
        for current_value in current_values:
            if current_value in pos_field_values:
                pos_values.append([(0.0, current_value)])
            else:
                this_pos_values = []
                for pos_field_value in pos_field_values:
                    this_pos_values.append((edit_distance.compute(current_value, pos_field_value, options), pos_field_value))
                this_pos_values.sort()
                pos_values.append(this_pos_values)

        print(f'pos_values={pos_values}')

        # TODO use a min heap here instead of checking everything
        current_indexes = [0] * len(pos_values)
        sorted_combinations = []
        while len(sorted_combinations) <= limit:
            print(f'current_indexes={current_indexes}')
            sorted_combinations.append(", ".join(map(lambda v: v[1], [vs[i] for i, vs in zip(current_indexes, pos_values)])))
            increment_index = None
            increment_value = None  # The minimum amount that would increase the combo total by incrementing one index.
            for i, (ci, pvs) in enumerate(zip(current_indexes, pos_values)):
                if ci >= len(pvs)-1:
                    continue
                if increment_value is None or pvs[ci+1][0]-pvs[ci][0] < increment_value:
                    increment_index = i
                    increment_value = pvs[ci+1][0]-pvs[ci][0]

            if increment_index is None:
                break
            current_indexes[increment_index] += 1

        return sorted_combinations

    def autocompleteSingle(self, field_name: str, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        if field_name not in self.record_struct:
            raise Exception(f'DB "{self.name}": Unknown field name "{field_name}"')
        pos_values = [record.fields[field_name] for _, record in self.records.items()]
        options = edit_distance.Options(
            edit_distance_type = edit_distance.Options.WORD,
            char_distance_type = edit_distance.Options.CHAR_KEYBORAD_DISTANCE,
            ignore_case = True,
        )
        weighted_values = [(edit_distance.compute(current, value, options), value) for value in pos_values]
        # TODO Use a min heap instead of sorting the whole list.
        return [value for _, value in sorted(weighted_values)[:limit]]

    def autocompleteEnumNames(self, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        print('dbimpl-autocompleteEnumNames start')
        pos_values = [enum_name for enum_name, _ in self.enums.items()]
        print(', '.join(pos_values))
        options = edit_distance.Options(
            edit_distance_type = edit_distance.Options.WORD,
            char_distance_type = edit_distance.Options.CHAR_KEYBORAD_DISTANCE,
            ignore_case = True,
        )
        weighted_values = [(edit_distance.compute(current, value, options), value) for value in pos_values]
        print(','.join(map(lambda v: str(v), weighted_values)))
        print('dbimpl-autocompleteEnumNames end')
        return [value for _, value in sorted(weighted_values)[:limit]]

    def autocompleteEnumValues(self, current: str, enum_name: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        if enum_name not in self.enums:
            raise Exception(f'DB "{self.name}": Unknown enum name "{enum_name}"')
        pos_values = self.enums[enum_name]
        options = edit_distance.Options(
            edit_distance_type = edit_distance.Options.WORD,
            char_distance_type = edit_distance.Options.CHAR_KEYBORAD_DISTANCE,
            ignore_case = True,
        )
        weighted_values = [(edit_distance.compute(current, value, options), value) for value in pos_values]
        # TODO Use a min heap instead of sorting the whole list.
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
        print('async-__init__ start')
        self.database_impl = database_impl
        self.filename = filename
        self.lock = asyncio.Lock()
        print('async-__init__ end')

    async def addRecord(self, **kwargs) -> (Record | None, str | None):
        print('async-addRecord start')
        print(f'async-addRecord lock-status {self.lock.locked()}')
        async with self.lock:
            print('async-addRecord got-lock')
            record, err = self.database_impl.addRecord(**kwargs)
            if err is None:
                saveDatabase(self.filename, self.database_impl)
            print('async-addRecord end')
            return record, err

    async def removeRecordByKey(self, key: tuple[typing.Any]) -> str | None:
        print('async-removeRecordByKey start')
        print(f'async-removeRecordByKey lock-status {self.lock.locked()}')
        async with self.lock:
            print('async-removeRecordByKey got-lock')
            err = self.database_impl.removeRecordByKey(key)
            if err is None:
                saveDatabase(self.filename, self.database_impl)
            print('async-removeRecordByKey end')
            return err

    async def updateRecordByKey(self, key: tuple[typing.Any], **kwargs) -> (Record | None, str | None):
        print('async-updateRecordByKey start')
        print(f'async-updateRecordByKey lock-status {self.lock.locked()}')
        async with self.lock:
            print('async-updateRecordByKey got-lock')
            record, err = self.database_impl.updateRecordByKey(key, **kwargs)
            if err is None:
                saveDatabase(self.filename, self.database_impl)
            print('async-updateRecordByKey end')
            return recorrd, err

    async def addEnumValue(self, enum_name: str, enum_value: str) -> str | None:
        print('async-addEnumValue start')
        print(f'async-addEnumValue lock-status {self.lock.locked()}')
        async with self.lock:
            print('async-addEnumValue got-lock')
            err = self.database_impl.addEnumValue(enum_name, enum_value)
            if err is None:
                saveDatabase(self.filename, self.database_impl)
            print('async-addEnumValue end')
            return err
    
    async def removeEnumValue(self, enum_name: str, enum_value: str) -> str | None:
        print('async-removeEnumValue start')
        print(f'async-removeEnumValue lock-status {self.lock.locked()}')
        async with self.lock:
            print('async-removeEnumValue got-lock')
            err = self.database_impl.removeEnumValue(enum_name, enum_value)
            if err is None:
                saveDatabase(self.filename, self.database_impl)
            print('async-removeEnumValue end')
            return err

    async def updateEnumValue(self, enum_name: str, old_enum_value: str, new_enum_value: str) -> str | None:
        print('async-updateEnumValue start')
        print(f'async-updateEnumValue lock-status {self.lock.locked()}')
        async with self.lock:
            print('async-updateEnumValue got-lock')
            err = self.database_impl.updateEnumValue(enum_name, old_enum_value, new_enum_value)
            if err is None:
                saveDatabase(self.filename, self.database_impl)
            print('async-updateEnumValue end')
            return err

    async def query(self, **kwargs) -> list[Record]:
        print('async-query start')
        print(f'async-query lock-status {self.lock.locked()}')
        async with self.lock:
            print('async-query got-lock')
            rv = self.database_impl.query(**kwargs)
            print('async-query end')
            return rv
    
    async def getEnumValuesFromFieldName(self, field_name: str) -> list[str]:
        print('async-getEnumValuesFromFieldName start')
        print(f'async-getEnumValuesFromFieldName lock-status {self.lock.locked()}')
        async with self.lock:
            print('async-getEnumValuesFromFieldName got-lock')
            rv = self.database_impl.getEnumValuesFromFieldName(field_name)
            print('async-getEnumValuesFromFieldName end')
            return rv

    async def autocompleteList(self, field_name: str, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        print('async-autocompleteList start')
        print(f'async-autocompleteList lock-status {self.lock.locked()}')
        async with self.lock:
            print('async-autocompleteList got-lock')
            rv = self.database_impl.autocompleteList(field_name, current, limit = limit)
            print('async-autocompleteList end')
            return rv

    async def autocompleteSingle(self, field_name: str, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        print('async-autocompleteSingle start')
        print(f'async-autocompleteSingle lock-status {self.lock.locked()}')
        async with self.lock:
            print('async-autocompleteSingle got-lock')
            rv = self.database_impl.autocompleteSingle(field_name, current, limit = limit)
            print('async-autocompleteSingle end')
            return rv

    def autocompleteEnumNames(self, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        print('async-autocompleteEnumNames start')
        rv = self.database_impl.autocompleteEnumNames(current, limit = limit)
        print('async-autocompleteEnumNames end')
        return rv

    async def autocompleteEnumValues(self, current: str, enum_name: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        print('async-autocompleteEnumValues start')
        print(self.lock.locked())
        async with self.lock:
            print('async-autocompleteEnumValues got-lock')
            rv = self.database_impl.autocompleteEnum
            print('async-autocompleteEnumValues end')
            return rv


# ----------------------------------------
# |                                      |
# |              Restaurants             |
# |                                      |
# ----------------------------------------

class RestaurantDiscordCommands(app_commands.Group):
    def __init__(self, restaurant_database, *args, **kwargs):
        super(RestaurantDiscordCommands, self).__init__(name='restaurant-db', *args, **kwargs)
        self.restaurant_database = restaurant_database

    async def locationListAutocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        try:
            sorted_autocomplete_values = await self.restaurant_database.autocompleteList("locations", current)
            return [app_commands.Choice(name=v, value=v) for v in sorted_autocomplete_values]
        except Exception:
            traceback.print_exc()

    async def cuisineListAutocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        try:
            sorted_autocomplete_values = await self.restaurant_database.autocompleteList("cuisines", current)
            return [app_commands.Choice(name=v, value=v) for v in sorted_autocomplete_values]
        except Exception:
            traceback.print_exc()

    async def eatingOptionsListAutocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        try:
            sorted_autocomplete_values = await self.restaurant_database.autocompleteList("eating_options", current)
            return [app_commands.Choice(name=v, value=v) for v in sorted_autocomplete_values]
        except Exception:
            traceback.print_exc()

    async def enumNameAutocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        try:
            sorted_enum_names = self.restaurant_database.autocompleteEnumNames(current)
            return [app_commands.Choice(name=v, value=v) for v in sorted_enum_names]
        except Exception as e:
            traceback.print_exc()

    async def enumValueAutocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        try:
            enum_name = interaction.namespace["enum_name"]
            sorted_enum_values = await self.restaurant_database.autocompleteEnumValues(current, enum_name=enum_name)
            return [app_commands.Choice(name=v, value=v) for v in sorted_enum_values]
        except Exception:
            traceback.print_exc()

    async def restaurantNameAutocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        try:
            sorted_restaurant_names = await self.restaurant_database.autocompleteSingle("name", current)
            return [app_commands.Choice(name=v, value=v) for v in sorted_restaurant_names]
        except Exception:
            traceback.print_exc()

    async def restaurantNameListAutocomplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        try:
            sorted_autocomplete_values = await self.restaurant_database.autocompleteList("name", current)
            return [app_commands.Choice(name=v, value=v) for v in sorted_autocomplete_values]
        except Exception:
            traceback.print_exc()

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
        # CHECKED
        kwargs = {
            RestaurantDatabase.NAME_FIELD: name,
            RestaurantDatabase.LOCATIONS_FIELD: parseDiscordList(locations),
            RestaurantDatabase.CUISINES_FIELD: parseDiscordList(cuisines),
            RestaurantDatabase.EATING_OPTIONS_FIELD: parseDiscordList(eating_options),
            RestaurantDatabase.HOURS_FIELD: hours,
            RestaurantDatabase.URL_FIELD: url,
        }
        new_record, err = await self.restaurant_database.addRestaurant(**kwargs)
        if err is None:
            new_record_str = self.restaurant_database.restaurantRecordToStr(new_record)
            msg = f'Successfully added new restaurant!\n\n{new_record_str}'
        else:
            msg = err
        await interaction.response.send_message(msg)

    # TODO Add more powerful querying syntax
    @app_commands.command(name='query', description='Finds the set of restaurants that match the query.')
    @app_commands.describe(
        names='Comma separated list of restaurant names. The returned restaurants must have one of the given names. If this option not set, then the name field won\'t be checked.',
        locations='Comma separated list of locations. The returned restaurants will have at least one of these locations. If this option not set, then the locations field won\'t be checked.',
        cuisines='Comma separated list of cuisines. The returned restaurants will have at least one of these locations. If this option not set, then the cuisines field won\'t be checked.',
        eating_options='Comma separated list of eating options. The returned restaurants will have at least one of these locations. If this option not set, then the eating_options field won\'t be checked.',
        num_restaurants='The number of restaurants to include in the response (If less than zero, then all matching restaurants will be returned). The order of the restaurants will be random.',
        ephemeral='Whether or not to send the response as an ephemeral message (visible only to you).',
    )
    @app_commands.autocomplete(
        names=restaurantNameListAutocomplete,
        locations=locationListAutocomplete,
        cuisines=cuisineListAutocomplete,
        eating_options=eatingOptionsListAutocomplete,
    )
    async def query(
        self,
        interaction: discord.Interaction,
        names: typing.Optional[str] = None,
        locations: typing.Optional[str] = None,
        cuisines: typing.Optional[str] = None,
        eating_options: typing.Optional[str] = None,
        num_restaurants: typing.Optional[int] = 5,
        ephemeral: typing.Optional[bool] = False,
    ):
        kwargs = {}
        if names is not None:
            kwargs["name"] = parseDiscordList(name)
        if locations is not None:
            kwargs["locations"] = parseDiscordList(locations)
        if cuisines is not None:
            kwargs["cuisines"] = parseDiscordList(cuisines)
        if eating_options is not None:
            kwargs["eating_options"] = parseDiscordList(eating_options)
        matching_records = await self.restaurant_database.query(**kwargs)

        total_matches = len(matching_records)

        if num_restaurants >= 0 and num_restaurants < len(matching_records):
            matching_records = random.sample(matching_records, num_restaurants)

        msg = f'Found {total_matches} restaurants that matched this query:\n'
        for record in matching_records:
            msg += '* ' + self.restaurant_database.restaurantRecordToStr(record) + '\n'
        await interaction.response.send_message(msg, ephemeral = ephemeral)

    @app_commands.command(name='remove-restaurant', description='Removes a restaurant from the database.')
    @app_commands.describe(
        name='The name of the restaurant to remove.',
    )
    @app_commands.autocomplete(
        name=restaurantNameAutocomplete,
    )
    async def remove_restaurant(
        self,
        interaction: discord.Interaction,
        name: str,
    ):
        # CHEKCED
        err = await self.restaurant_database.removeRestaurant(name)
        if err is None:
            msg = f'Successfully removed restaurant "{name}"'
        else:
            msg = err
        await interaction.response.send_message(msg)

    @app_commands.command(name='update-restaurant', description='Updates a restaurant from the database.')
    @app_commands.describe(
        name='The name of the restaurant to update.',
        new_name='The new name of the restaurant. If not set, this field is not updated.',
        locations='The new values for the location of the restaurant. If not set, this field is not updated.',
        cuisines='The new values for the cuisines of the restaurant. If not set, this field is not updated.',
        eating_options='The new values for the eating options of the restaurant. If not set, this field is not updated.',
        hours='The new value for the hours of this restaurant. If not set, this field is not updated.',
        url='The new value for the url of this restaurant. If not set, this field is not updated.',
    )
    @app_commands.autocomplete(
        name=restaurantNameAutocomplete,
        locations=locationListAutocomplete,
        cuisines=cuisineListAutocomplete,
        eating_options=eatingOptionsListAutocomplete,
    )
    async def update_restaurant(
        self,
        interaction: discord.Interaction,
        name: str,
        new_name: typing.Optional[str] = None,
        locations: typing.Optional[str] = None,
        cuisines: typing.Optional[str] = None,
        eating_options: typing.Optional[str] = None,
        hours: typing.Optional[str] = None,
        url: typing.Optional[str] = None,
    ):
        kwargs = {}
        if new_name is not None:
            kwargs[RestaurantDatabase.NAME_FIELD] = new_name
        if locations is not None:
            kwargs[RestaurantDatabase.LOCATIONS_FIELD] = parseDiscordList(locations)
        if cuisines is not None:
            kwargs[RestaurantDatabase.CUISINES_FIELD] = parseDiscordList(cuisines)
        if eating_options is not None:
            kwargs[RestaurantDatabase.EATING_OPTIONS_FIELD] = parseDiscordList(eating_options)
        if hours is not None:
            kwargs[RestaurantDatabase.HOURS_FIELD] = hours
        if url is not None:
            kwargs[RestaurantDatabase.URL_FIELD] = field
        updated_record, err = self.restaurant_database.updateRestaurant(name, **kwargs)
        if err is None:
            updated_record_str = self.restaurant_database.restaurantRecordToStr(updated_record)
            msg = f'Successfully updated restaurant "{name}" to:\n\n{updated_record_str}'
        else:
            msg = err
        await interaction.response.send_message(msg)

    @app_commands.command(name='add-enum-value', description='Adds a new enum value to the database.')
    @app_commands.describe(
        enum_name='The name of the enum to add the value to.',
        new_enum_value='The value to add to the enum.',
    )
    @app_commands.autocomplete(
        enum_name=enumNameAutocomplete,
    )
    async def add_enum_value(
        self,
        interaction: discord.Interaction,
        enum_name: str,
        new_enum_value: str,
    ):
        # CHECKED
        err = await self.restaurant_database.addEnumValue(enum_name, new_enum_value)

        if err is None:
            msg = f'Successfully added new enum value "{new_enum_value}" to enum "{enum_name}"'
        else:
            msg = err
        
        await interaction.response.send_message(msg)

    @app_commands.command(name='remove-enum-value', description='Removes a enum value from the given enum.')
    @app_commands.describe(
        enum_name='The name of enum to remove the value from.',
        enum_value='The value to remove from the enum.',
    )
    @app_commands.autocomplete(
        enum_name=enumNameAutocomplete,
        enum_value=enumValueAutocomplete,
    )
    async def remove_enum_value(
        self,
        interaction: discord.Interaction,
        enum_name: str,
        enum_value: str,
    ):
        err = await self.restaurant_database.removeEnumValue(enum_name, enum_value)
        if err is None:
            msg = f'Successfully removed enum_value "{enum_value}" from enum "{enum_name}" and all existing records'
        else:
            msg = err
        await interaction.response.send_message(msg)

    @app_commands.command(name='update-enum-value', description='Updates the given enum value in the given enum.')
    @app_commands.describe(
        enum_name='The name of enum to remove the value from.',
        old_enum_value='The existing value in the enum to update.',
        new_enum_value='The new value to update to in the enum.',
    )
    @app_commands.autocomplete(
        enum_name=enumNameAutocomplete,
        old_enum_value=enumValueAutocomplete,
    )
    async def update_enum_value(
        self,
        interaction: discord.Interaction,
        enum_name: str,
        old_enum_value: str,
        new_enum_value: str,
    ):
        err = await self.restaurant_database.updateEnumValue(enum_name, old_enum_value, new_enum_value)
        if err is None:
            msg = f'Successfully updated enum_value from "{old_enum_value}" to "{new_enum_value}" in enum "{enum_name}" and all existing records'
        else:
            msg = err
        await interaction.response.send_message(msg)


class RestaurantDatabase:
    # Field Names
    NAME_FIELD = "name"
    LOCATIONS_FIELD = "locations"
    CUISINES_FIELD = "cuisines"
    EATING_OPTIONS_FIELD = "eating_options"
    HOURS_FIELD = "hours"
    URL_FIELD = "url"

    # Enum Names
    LOCATIONS_ENUM = "locations"
    CUISINES_ENUM = "cuisines"
    EATING_OPTIONS_ENUM = "eating_options"


    def __init__(self, filename = "data/restaurant_database.pickle"):
        keys = (RestaurantDatabase.NAME_FIELD,)
        record_struct = {
            RestaurantDatabase.NAME_FIELD: FieldType(FieldType.STR, FieldType.REQUIRED),
            RestaurantDatabase.LOCATIONS_FIELD: FieldType(FieldType.ENUM, FieldType.REPEATED, RestaurantDatabase.LOCATIONS_ENUM),
            RestaurantDatabase.CUISINES_FIELD: FieldType(FieldType.ENUM, FieldType.REPEATED, RestaurantDatabase.CUISINES_ENUM),
            RestaurantDatabase.EATING_OPTIONS_FIELD: FieldType(FieldType.ENUM, FieldType.REPEATED, RestaurantDatabase.EATING_OPTIONS_ENUM),
            RestaurantDatabase.HOURS_FIELD: FieldType(FieldType.STR, FieldType.OPTIONAL),
            RestaurantDatabase.URL_FIELD: FieldType(FieldType.STR, FieldType.OPTIONAL),

            # TODO maybe add other fields: google maps URL, description, ...
        }
        base_enums = {
            RestaurantDatabase.LOCATIONS_ENUM: [],
            RestaurantDatabase.CUISINES_ENUM: [],
            RestaurantDatabase.EATING_OPTIONS_ENUM: [
               "delivery", "pick-up", "dine-in",
            ],
        }

        # Try and load the database from file, if not initialize it to empty with the right fields.
        database_impl = loadDatabase(filename)
        if database_impl is None:
            # Init the database if there isn't a saved version.
            database_impl = DatabaseImpl("restaurants", [], keys, record_struct, base_enums)
            saveDatabase(filename, database_impl)

        # TODO Make sure that database_impl matches with keys, record_struct, and base_enums. It's okay if the loaded version has extra enum_values.

        # Wrap the database_impl in an AsyncDatabaseWrapper.
        self.async_database = AsyncDatabaseWrapper(database_impl, filename)

    def getDiscordCommands(self):
        return [RestaurantDiscordCommands(self)]

    # kwargs should match record_struct
    async def addRestaurant(self, **kwargs) -> (Record | None, str | None):
        return await self.async_database.addRecord(**kwargs)

    async def removeRestaurant(self, name: str) -> str | None:
        return await self.async_database.removeRecordByKey((name,))

    async def updateRestaurant(self, old_name: str, **kwargs) -> (Record | None, str | None):
        return await self.async_database.removeRecordByKey((old_name,), **kwargs)

    async def addEnumValue(self, enum_name: str, enum_value: str) -> str | None:
        return await self.async_database.addEnumValue(enum_name, enum_value)

    async def removeEnumValue(self, enum_name: str, enum_value: str) -> str | None:
        return await self.async_database.removeEnumValue(enum_name, enum_value)

    async def updateEnumValue(self, enum_name: str, old_enum_value: str, new_enum_value: str) -> str | None:
        return await self.async_database.updateEnumValue(enum_name, old_enum_value, new_enum_value)

    async def query(self, **kwargs) -> list[Record]:
        return await self.async_database.query(**kwargs)

    async def autocompleteList(self, field_name: str, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        return await self.async_database.autocompleteList(field_name, current, limit = limit)

    async def autocompleteSingle(self, field_name: str, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        return await self.async_database.autocompleteSingle(field_name, current, limit = limit)

    def autocompleteEnumNames(self, current: str, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        print('RestaurantDatabase-autocompleteEnumNames start ASDFASDFASDF')
        rv = self.async_database.autocompleteEnumNames(current, limit = limit)
        print('RestaurantDatabase-autocompleteEnumNames end')
        return rv

    async def autocompleteEnumValues(self, current: str, enum_name: str | None = None, limit: int = AUTOCOMPLETE_LIMIT) -> list[str]:
        return await self.asnyc_database.autocompleteEnumValues(current, enum_name, limit = limit)

    async def getEnumValuesFromFieldName(self, field_name: str) -> list[str]:
        return await self.async_database.getEnumValuesFromFieldName(field_name)

    def restaurantRecordToStr(self, record: Record, line_prefix = "") -> str:
        name = record.fields["name"]
        locations = record.fields["locations"]
        cuisines = record.fields["cuisines"]
        eating_options = record.fields["eating_options"]
        hours = record.fields["hours"]
        url = record.fields["url"]

        rv = ""
        if url is None:
            rv += f"{line_prefix}**{name}**: "
        else:
            rv += f"{line_prefix}**[{name}]({url})**: "

        location_str = ", ".join(map(lambda v: f'"{v}"', locations)) if len(locations) > 0 else "None"
        rv += f"\n{line_prefix}\t*Locations* = {location_str}"

        cuisine_str = ", ".join(map(lambda v: f'"{v}"', cuisines)) if len(cuisines) > 0 else "None"
        rv += f"\n{line_prefix}\t*Cuisines* = {cuisine_str}"

        eating_option_str = ", ".join(map(lambda v: f'"{v}"', eating_options)) if len(eating_options) > 0 else "None"
        rv += f"\n{line_prefix}\t*Eating Options* = {eating_option_str}"

        if hours is not None:
            rv += f"\n{line_prefix}\t*Hours*: \"{hours}\""

        return rv
