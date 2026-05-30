import asyncio

from _contract_helpers import configure_contract_test_db, make_notification_preset_row

from app.api import routes_presets
from app.database import SessionLocal, init_db
from app.models.notification_preset import NotificationPresetModel

test_db = configure_contract_test_db("api_contracts_notification_preset_tests")


def test_notification_preset_test_contract(monkeypatch):
    init_db()
    db = SessionLocal()
    try:
        db.query(NotificationPresetModel).delete()
        db.commit()

        row = make_notification_preset_row(
            name="Contract Notification",
            provider="web,telegram",
            url="https://notify.example.test",
            topic="-123456789",
            encrypted_token="encrypted-token",
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        async def fake_run_notification_preset_test(preset_row):
            assert preset_row.id == row.id
            return ["web", "telegram"], ["telegram: simulated warning"]

        monkeypatch.setattr(routes_presets, "run_notification_preset_test", fake_run_notification_preset_test)

        payload = asyncio.run(routes_presets.test_notification_preset(row.id, db=db))

        assert payload.model_dump(mode="json") == {
            "ok": True,
            "sent": ["web", "telegram"],
            "errors": ["telegram: simulated warning"],
        }
    finally:
        db.close()
        test_db.unlink(missing_ok=True)
