import pydantic
from typing import Optional, Type


class CreateUser(pydantic.BaseModel):
    username: str
    password: str

    @pydantic.validator("password")
    def validate_password(cls, value):
        if len(value) < 8:
            raise ValueError('Password is too short')
        return value


class CreateAdvertisement(pydantic.BaseModel):
    title: Optional[str]
    description: Optional[str]


VALIDATION_CLASS = Type[CreateAdvertisement] | Type[CreateUser]
