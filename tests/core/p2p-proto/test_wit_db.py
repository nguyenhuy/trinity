import pytest

from eth.db.backends.memory import MemoryDB

from trinity.exceptions import WitnessHashesUnavailable
from trinity.protocol.wit.db import AsyncWitnessDB
from trinity.tools.factories import Hash32Factory


@pytest.mark.asyncio
async def test_persisting_and_looking_up():
    wit_db = AsyncWitnessDB(MemoryDB())

    hash1 = Hash32Factory()
    with pytest.raises(WitnessHashesUnavailable):
        await wit_db.coro_get_witness_hashes(hash1)

    hash1_witnesses = tuple(Hash32Factory.create_batch(5))
    await wit_db.coro_persist_witness_hashes(hash1, hash1_witnesses)
    loaded_hashes = await wit_db.coro_get_witness_hashes(hash1)

    assert set(loaded_hashes) == set(hash1_witnesses)


@pytest.mark.asyncio
async def test_witness_for_recent_blocks():
    wit_db = AsyncWitnessDB(MemoryDB())
    hash1 = Hash32Factory()
    hash1_witnesses = tuple(Hash32Factory.create_batch(5))
    await wit_db.coro_persist_witness_hashes(hash1, hash1_witnesses)

    # *almost* push the first witness out of history
    for _ in range(wit_db._max_witness_history - 1):
        await wit_db.coro_persist_witness_hashes(Hash32Factory(), Hash32Factory.create_batch(2))

    # It should still be there...
    loaded_hashes = await wit_db.coro_get_witness_hashes(hash1)
    assert set(loaded_hashes) == set(hash1_witnesses)

    # Until one more new witness is added.
    await wit_db.coro_persist_witness_hashes(Hash32Factory(), Hash32Factory.create_batch(2))

    # Now the old witness has been flushed out of the history
    with pytest.raises(WitnessHashesUnavailable):
        await wit_db.coro_get_witness_hashes(hash1)

    assert len(wit_db._get_recent_blocks_with_witnesses()) == wit_db._max_witness_history


@pytest.mark.asyncio
async def test_witness_history_on_repeat_blocks():
    """
    Repeated blocks should not consume more slots in the limited history of block witnesses
    """
    wit_db = AsyncWitnessDB(MemoryDB())
    hash1 = Hash32Factory()
    hash1_witnesses = tuple(Hash32Factory.create_batch(5))
    await wit_db.coro_persist_witness_hashes(hash1, hash1_witnesses)

    hash2 = Hash32Factory()
    await wit_db.coro_persist_witness_hashes(hash2, tuple(Hash32Factory.create_batch(5)))

    # *almost* push the first witness out of history
    for _ in range(wit_db._max_witness_history - 2):
        await wit_db.coro_persist_witness_hashes(Hash32Factory(), Hash32Factory.create_batch(2))

    # It should still be there...
    loaded_hashes = await wit_db.coro_get_witness_hashes(hash1)
    assert set(loaded_hashes) == set(hash1_witnesses)

    # Add one more new witness, for an existing block
    await wit_db.coro_persist_witness_hashes(hash2, Hash32Factory.create_batch(2))

    # That new witness should *not* consume a block slot in history, so the first hash's
    #   witness should still be available.
    loaded_hashes = await wit_db.coro_get_witness_hashes(hash1)
    assert set(loaded_hashes) == set(hash1_witnesses)


@pytest.mark.asyncio
async def test_witness_eviction_on_repeat_blocks():
    """
    After witnesses are persisted twice for the same block, make sure that eviction
    does not cause any failures.
    """
    wit_db = AsyncWitnessDB(MemoryDB())
    hash_ = Hash32Factory()
    await wit_db.coro_persist_witness_hashes(hash_, Hash32Factory.create_batch(2))
    await wit_db.coro_persist_witness_hashes(hash_, Hash32Factory.create_batch(2))
    for _ in range(wit_db._max_witness_history):
        await wit_db.coro_persist_witness_hashes(Hash32Factory(), Hash32Factory.create_batch(2))


@pytest.mark.asyncio
async def test_witness_union():
    wit_db = AsyncWitnessDB(MemoryDB())
    hash1 = Hash32Factory()
    hash1_witnesses_unique1 = set(Hash32Factory.create_batch(3))
    hash1_witnesses_unique2 = set(Hash32Factory.create_batch(3))
    hash1_witnesses_both = set(Hash32Factory.create_batch(2))
    hash1_witnesses1 = tuple(hash1_witnesses_unique1 | hash1_witnesses_both)
    hash1_witnesses2 = tuple(hash1_witnesses_unique2 | hash1_witnesses_both)

    await wit_db.coro_persist_witness_hashes(hash1, hash1_witnesses1)
    await wit_db.coro_persist_witness_hashes(hash1, hash1_witnesses2)

    stored_hashes = await wit_db.coro_get_witness_hashes(hash1)

    expected = hash1_witnesses_unique1 | hash1_witnesses_both | hash1_witnesses_unique2
    assert set(stored_hashes) == expected
