import uuid


def gen_request_id() -> str:
    return uuid.uuid4().hex
