from agentgate.case import DatasetService
from agentgate.domain import Case, CaseTurn
from agentgate.storage.sqlite import SQLiteRepository


def test_canonical_json_export_import_round_trip(tmp_path):
    source = DatasetService(SQLiteRepository(tmp_path / "source.db"))
    dataset = source.create_dataset("Exported")
    source.create_draft(dataset.id)
    source.save_case(dataset.id, Case(
        id="case", name="Case",
        turns=(CaseTurn(id="turn", input={"message": "hello"}),),
    ))
    published = source.publish_draft(dataset.id)
    exported = source.export_version(dataset.id, published.version)

    target = DatasetService(SQLiteRepository(tmp_path / "target.db"))
    imported_dataset, imported_version = target.import_dataset(
        exported.model_dump(mode="json")
    )
    assert imported_dataset == dataset
    assert imported_version.content_sha256 == published.content_sha256
    assert imported_version.cases[0].turns[0].input["message"] == "hello"
