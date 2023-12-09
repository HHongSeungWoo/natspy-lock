# natspy-lock

[![PyPI - Version](https://img.shields.io/pypi/v/natspy-lock.svg)](https://pypi.org/project/natspy-lock)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/natspy-lock.svg)](https://pypi.org/project/natspy-lock)

-----

`natspy-lock` is a distributed lock library using nats.

**Table of Contents**

- [Installation](#installation)
- [Example](#example)
- [License](#license)


## Installation

```console
pip install natspy-lock
```

## Example

```python
import nats
from natspy_lock import NatsLock

async def main():
    nc = await nats.connect("nats://127.0.0.1:4222")
    await NatsLock.init(nc, "test_lock", 60)
    async with NatsLock.get_lock("test_lock", 1):
    #     do something
        pass
    await nc.drain()
```

## License

`natspy-lock` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
