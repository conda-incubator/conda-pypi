def post_command(command: str):
    if command not in ("install", "create"):
        return
