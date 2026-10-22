import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")


class RegisterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=30)]
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=254)]
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def _username(cls, v):
        if not USERNAME_RE.match(v):
            raise ValueError("Username 3–30 karakter: huruf, angka, titik, garis bawah, atau strip.")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        if not EMAIL_RE.match(v):
            raise ValueError("Format email tidak valid.")
        return v.lower()

    @model_validator(mode="after")
    def _password_strength(self):
        p = self.password
        if not (re.search(r"[A-Za-z]", p) and re.search(r"\d", p)):
            raise ValueError("Password minimal 8 karakter dan mengandung huruf serta angka.")
        if self.username.lower() in p.lower():
            raise ValueError("Password tidak boleh mengandung username.")
        return self


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identifier: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=254)] = Field(description="Username atau email")
    password: str = Field(min_length=1, max_length=128)
