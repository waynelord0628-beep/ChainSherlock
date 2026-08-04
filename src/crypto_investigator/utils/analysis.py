from crypto_investigator.domain.transaction import Chain, Direction, Transaction


def addresses_equal(chain: Chain, left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return False
    if chain is Chain.ETHEREUM:
        return left.casefold() == right.casefold()
    return left == right


def transaction_direction(transaction: Transaction, target_address: str | None) -> Direction:
    if target_address is None:
        return transaction.direction
    from_target = addresses_equal(
        transaction.chain, transaction.from_address, target_address
    )
    to_target = addresses_equal(transaction.chain, transaction.to_address, target_address)
    if from_target and to_target:
        return Direction.SELF
    if from_target:
        return Direction.OUTGOING
    if to_target:
        return Direction.INCOMING
    return transaction.direction


def counterparty_address(
    transaction: Transaction, target_address: str | None
) -> str | None:
    direction = transaction_direction(transaction, target_address)
    if direction is Direction.INCOMING:
        return transaction.from_address
    if direction is Direction.OUTGOING:
        return transaction.to_address
    return None
