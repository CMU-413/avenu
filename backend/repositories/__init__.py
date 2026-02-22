from .common import run_in_transaction, to_api_doc
from .mailboxes_repository import find_owner_mailbox
from .teams_repository import find_team_by_optix_id
from .users_repository import find_user, find_user_by_optix_id, has_users_with_team


# Backward-compatibility aliases used by existing service code/tests during phased refactor.
start_txn = run_in_transaction
owner_mailbox = find_owner_mailbox


def insert_idempotency(doc):
    from config import idempotency_keys_collection

    return idempotency_keys_collection.insert_one(doc)
