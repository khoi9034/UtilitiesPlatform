from app import models


def test_database_model_imports() -> None:
    assert models.UtilitySystem.__tablename__ == "utility_systems"
    assert models.UtilityAsset.__tablename__ == "utility_assets"
    assert models.QaIssue.__tablename__ == "qa_issues"
