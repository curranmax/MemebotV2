
import asyncio
from collections.abc import Callable
import os.path
import typing

from discord import app_commands

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
            self.validateRecord(record_id, record)


    def validateRecord(self, record_id: str, record: Record):
        if record.record_id != record_id:
            raise Exception(f'DB "{self.name}": Record ID "{record_id}" doesn\'t match record "{record.record_id}"')

        for field_name, field_type in self.record_struct.items():
            if field_name not in record.fields:
                # Record is missing a field (Note that optional fields need to be specified but can be None).
                raise Exception(f'DB "{self.name}": Record "{record_id}" is missing required field "{field_name}"')

            field_value = record.fields[field_name]
            enum_values = None
            if field_type.base_type == FieldType.ENUM:
                if field_type.enum_name not in self.enums:
                    # The enum of the field_type doesn't exist
                    raise Exception(f'DB "{self.name}": Unknown enum "{field_type.enum_name}"')
                enum_values = self.enums[field_type.enum_name]
            if not field_type.validate(field_value, enum_values):
                # Field value doesn't match field type
                raise Exception(f'DB "{self.name}": Record "{record_id}" has invalid value for field "{field_name}": {field_value}')

        # Record has a field that it isn't supposed to
        for field_name, _ in fields.items():
            if field_name not in self.record_struct:
                raise Exception(f'DB "{self.name}": Record "{record_id}" has extra field "{field_name}"')

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
        self.records[record_id] = record
        self.validateRecord(record_id, record)
        return record

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
    

    async def getEnumValuesFromFieldName(self, field_name: str) -> list[EnumValue]:
        async with self.lock:
            return self.database_impl.getEnumValuesFromFieldName(field_name)


# ----------------------------------------
# |                                      |
# |              Restaurants             |
# |                                      |
# ----------------------------------------

class RestaurantDiscordCommands(app_commands.Group):
    def __init__(self, restaurant_database, *args, **kwargs):
        super(OwTrackerDiscordCommands, self).__init__(name='restaurant-db', *args, **kwargs)
        self.restaurant_database = restaurant_database

    async def locationListAutoComplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        # TODO Move this to a helper function so the code can be resued
        
        # Get the enum values for this type
        enum_values = self.restaurant_database.getEnumValuesFromFieldName("locations")

        # Parse current into list of values

        # If an entry is already an enum value, then we are good.

        # If an entry isn't already an enum value, then find the edit distance between it and all enum values

        # Combine the different combinations and come up with a sorted list by overall lowest edit distance

        # Return the first AUTOCOMPLETE_LIMIT entries

        return []



    async def cuisineListAutoComplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        pass

    async def eatingOptionsListAutoComplete(self, interaction: discord.Interaction, current: str) -> typing.List[app_commands.Choice[str]]:
        pass

    @app_commands.command(name='add-restaurant', description='Record lose')
    @app_commands.describe(
        name='Name of the restaurant',
        locations='Comma separated list of locations associated with the restaurant',
        cuisines='Comma separated list of cuisines that the restaurant serves',
        eating_options='Comma separated list of eating options that the restaurant offers',
        hours='Free form string with the general hours of the restaurant',
        url='URL of the restaurant',
    )
    @app_commands.autocomplete(
        locations=locationListAutoComplete,
        cuisines=cuisineListAutoComplete,
        eating_options=eatingOptionsListAutoComplete,
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
#  * Implemented autocomplete functions
#  * Implement the query command
#    * All records or random k records
#    * Selection criteria
#  * Implement command to add enum value
#  * Delete record (by name? by id?)
#  * Delete enum value (by name)
#  * Update commands? (not really needed if we have delete+add)