"""Generate believable signup identities."""
from __future__ import annotations

import random
import string
from dataclasses import dataclass
from datetime import date

from faker import Faker


@dataclass
class Identity:
    first_name: str
    last_name: str
    username: str
    password: str
    dob: date
    address: str
    city: str
    state: str
    zip_code: str
    country: str = "US"
    locale: str = "en_US"


_LOCALES = ["en_US", "en_GB", "en_CA", "en_AU"]


def _password(length: int = 16) -> str:
    pool = string.ascii_letters + string.digits + "!@#$%&*"
    # always include at least one of each class
    base = [
        random.choice(string.ascii_lowercase),
        random.choice(string.ascii_uppercase),
        random.choice(string.digits),
        random.choice("!@#$%&*"),
    ]
    base += [random.choice(pool) for _ in range(length - len(base))]
    random.shuffle(base)
    return "".join(base)


def generate(locale: str | None = None) -> Identity:
    locale = locale or random.choice(_LOCALES)
    fake = Faker(locale)
    first = fake.first_name()
    last = fake.last_name()
    username = (
        first.lower()
        + last.lower()
        + str(random.randint(10, 9999))
    )
    return Identity(
        first_name=first,
        last_name=last,
        username=username,
        password=_password(),
        dob=fake.date_of_birth(minimum_age=22, maximum_age=55),
        address=fake.street_address(),
        city=fake.city(),
        state=fake.state_abbr() if hasattr(fake, "state_abbr") else "",
        zip_code=fake.postcode(),
        country=locale.split("_")[1],
        locale=locale,
    )
