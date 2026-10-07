"""Tests run against an in-memory MongoDB (mongomock) - no Atlas connection needed."""
import mongomock
import pytest

from app.repository import MongoRepository, use_repo


def _bulk_write(self, requests, ordered=True, **_):
    # mongomock's bulk_write doesn't understand newer pymongo ReplaceOne objects; emulate it.
    for op in requests:
        if type(op).__name__ == "UpdateOne":
            self.update_one(op._filter, op._doc, upsert=op._upsert)
        else:
            self.replace_one(op._filter, op._doc, upsert=op._upsert)


mongomock.collection.Collection.bulk_write = _bulk_write


@pytest.fixture(autouse=True)
def mongo_repo():
    repo = MongoRepository("mongodb://test", "test_db", client=mongomock.MongoClient())
    use_repo(repo)
    from app.services.cache import cache
    cache.clear()
    yield repo
