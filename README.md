# natspy-lock

[![PyPI - Version](https://img.shields.io/pypi/v/natspy-lock.svg)](https://pypi.org/project/natspy-lock)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/natspy-lock.svg)](https://pypi.org/project/natspy-lock)

-----

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
    await NatsLock.init(nc.jetstream(), "test_lock", 100)
    async with NatsLock.lock("test_lock", 1) as lock:
        # do something
        pass
    await nc.close()
```

## License

`natspy-lock` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
