<p align="center">
    <a href="github.address">
        <img src="https://raw.githubusercontent.com/LinuxV3/pyshad/refs/heads/main/pyshad_icon.png" alt="PyShad" width="128">
    </a>
    <br>
    <b>SHAD API Framework for Python</b>
    <br>
    <a href="https://github.com/LinuxV3/pyshad">
        Homepage
    </a>
    •
    <a href="https://docs.rubpy.site">
        Documentation
    </a>
    •
    <a href="https://pypi.org/project/pyshad/#history">
        Releases
    </a>
    •
    <a href="https://t.me/pyshad_library">
        News
    </a>
</p>

## PyShad

> Elegant, modern and asynchronous Shad API framework in Python for users and bots
## Pyshad is based on [Rubpy](https://pypi.org/project/rubpy/)
> In fact Pyshad is based on rubpy and copied
> But I will add new features to Pyshad

### Async Accounts
```python
from pyshad import Client, filters, utils
from pyshad.types import Updates

bot = Client(name='pyshad')

@bot.on_message_updates(filters.text)
async def updates(update: Updates):
    print(update)
    await update.reply(utils.Code('hello') + utils.Underline('from') + utils.Bold('rubpy'))

bot.run()
```

**Async Another Example:**
```python
from pyshad import Client
import asyncio

async def main():
    async with Client(name='pyshad') as bot:
        result = await bot.send_message('me', '`hello` __from__ **pyshad**')
        print(result)

asyncio.run(main())
```

### Sync Accounts
```python
from pyshad import Client

bot = Client('pyshad')

@bot.on_message_updates()
def updates(message):
    message.reply('`hello` __from__ **pyshad**')

bot.run()
```

**Sync Another Example:**
```python
from pyshad import Client

with Client(name='pyshad') as client:
    result = client.send_message('me', '`hello` __from__ **pyshad**')
    print(result)
```

**pyshad** is a modern, elegant and asynchronous framework. It enables you to easily interact with the main Rubika API through a user account (custom client) or a bot
identity (bot API alternative) using Python.


### Key Features

- **Ready**: Install Rubpy with pip and start building your applications right away.
- **Easy**: Makes the Rubika API simple and intuitive, while still allowing advanced usages.
- **Elegant**: Low-level details are abstracted and re-presented in a more convenient way.
- **Fast**: Boosted up by pycryptodome, a high-performance cryptography library written in C.
- **Async**: Fully asynchronous (also usable synchronously if wanted, for convenience).
- **Powerful**: Full access to Shad's API to execute any official client action and more.

### Installing

``` bash
pip3 install -U pyshad
```
