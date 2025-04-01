def parse_command(message_text: str):
    if not message_text:
        return None, None
    _split = message_text.strip().strip('/').split(' ')
    _split = [x.strip() for x in _split]

    if len(_split) == 0:
        return None, None
    
    command = _split[0]
    args = _split[1:] if len(_split) > 1 else []
    return command, args
