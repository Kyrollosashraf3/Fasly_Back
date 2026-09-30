from pydantic import BaseModel, ConfigDict


class ORMResponse(BaseModel):
    """Base for every schema hydrated straight from a SQLAlchemy row.

    ``from_attributes`` lets the services return ORM objects as-is; fields
    named after ORM *properties* (``age``, ``display_name``) are filled in
    automatically because the mapper exposes them as regular attributes.
    """

    model_config = ConfigDict(from_attributes=True)
