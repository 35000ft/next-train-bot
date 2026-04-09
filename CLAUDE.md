# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Next Train Bot - A QQ bot for querying metro/train real-time information, ticket prices, flight boards, weather radar, and more. Built with `botpy` (QQ Bot Python SDK).

## Development Commands

**Install dependencies:**
```bash
uv sync
```

**Run the bot:**
```bash
uv run python app/main.py
```

**Activate virtual environment:**
```bash
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

## Architecture

### Entry Point
- `app/main.py` - Initializes the bot client and starts the event loop

### Core Components

**Bot Client** (`app/bot/next_train_robot.py`)
- `NextTrainClient` extends `botpy.Client`
- `command_dict` - Maps group chat commands to handlers
- `private_command_dict` - Maps private (C2C) chat commands to handlers
- Uses `AsyncLRUCache` for context command caching
- Uses `CodeManager` for security code validation

**Event Handlers** (`app/events/`)
- Commands are organized by domain:
  - `next_train_events.py` - Metro real-time queries, schedules, pricing
  - `civil_aviation_events.py` - Airport flight boards, weather reports
  - `cma_events.py` - Weather radar queries
  - `cr_events.py` - China Railway EMU queries, ticket prices
  - `common_events.py` - Wiki summaries
  - `auth_events.py` - User registration, group linking

**Command Routing**
Commands follow the pattern: `/command param1 param2 -flag`
- Parsed by `app/utils/command_utils.py` `parse_command()`
- Context-aware commands supported via `find_context_command()`

**Services** (`app/service/`)
- `realtime_service.py` - Metro real-time data fetching
- `ticket_price_service.py` - Train ticket pricing
- `railsystem_service.py` - Rail system metadata
- `personalize_service.py` - User aliases, default rail systems
- `file_service.py` - File upload caching

**Models** (`app/models/`)
- SQLAlchemy async ORM models
- `Railsystem.py` - Station, Line entities
- `Common.py` - Shared base classes

**Configuration** (`app/config.py`)
- Environment variables loaded via `python-dotenv`
- Database URL constructed from `DB_TYPE`, `DB_USER`, `DB_PWD`, etc.
- `Config` class holds bot credentials (`APP_ID`, `SECRET`)

## Key Patterns

**Command Handler Signature:**
```python
async def handler_name(message: GroupMessage | C2CMessage, param1: str, **kwargs):
    # kwargs contains _bot (NextTrainClient instance), g (global flag), etc.
    # Use get_group_and_user_id(message) for group/user IDs
```

**Database Sessions:**
```python
from app.config import get_db_session
async with get_db_session() as session:
    # database operations
```

**Forbidden Word Check:**
Use the `@check_params_contains_forbidden_word("param_name")` decorator on handlers that accept user input.

**Context Commands:**
For multi-step interactions (e.g., selecting from a list):
1. Generate options with `save_context_command()`
2. User replies with option number
3. `find_context_command()` retrieves the full command
4. Re-process with the resolved command

## Dependencies

- `qq-botpy` - QQ Bot SDK
- `SQLAlchemy` + `aiomysql` - Async database ORM
- `selenium` - Web scraping for flight boards
- `pandas` + `openpyxl` - Data processing
- `pillow` - Image generation
- `html2image` - HTML to image conversion
- `china-railway-tools` (GitHub) - Railway data tools

## Environment Variables

Required in `.env`:
- `APP_ID`, `SECRET` - QQ Bot credentials
- `DB_TYPE`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PWD`, `DB_NAME` - Database
- `FORBIDDEN_WORDS` - Comma-separated blocked words
- `ENV` - Set to `prod` for production mode

## Testing

No formal test suite is configured. Test manually by:
1. Running the bot locally
2. Using QQ to send commands to the bot
3. Checking logs for errors
