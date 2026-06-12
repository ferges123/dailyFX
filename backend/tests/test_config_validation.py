import pytest
from fastapi.testclient import TestClient
from _contract_helpers import configure_contract_test_db

# Initialize the test DB first
test_db = configure_contract_test_db("config_validation")

from app.database import SessionLocal, init_db
init_db()

from app.main import app
from app.security import require_auth
from app.services.generation.config_validation import (
    validate_module_config,
    validate_effects_config,
)
from app.models.effect_preset import EffectPresetModel

@pytest.fixture
def authenticated_client():
    app.dependency_overrides[require_auth] = lambda: None
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        db.query(EffectPresetModel).delete()
        db.commit()
        yield db
    finally:
        db.close()

def test_validate_module_config_success():
    # Valid bokeh_blur
    validate_module_config("bokeh_blur", {
        "enabled": True,
        "weight": 3,
        "config": {
            "blur_strength": 15,
            "focus_area": "auto"
        }
    })

def test_validate_module_config_invalid_module():
    with pytest.raises(ValueError, match="Unknown generation module 'unknown_xyz'"):
        validate_module_config("unknown_xyz", {"config": {}})

def test_validate_module_config_invalid_group_type():
    with pytest.raises(ValueError, match="Configuration for module 'bokeh_blur' must be a dictionary"):
        validate_module_config("bokeh_blur", "not-a-dict")

def test_validate_module_config_unknown_group_keys():
    with pytest.raises(ValueError, match="contains unknown keys: invalid_key"):
        validate_module_config("bokeh_blur", {"enabled": True, "invalid_key": 123})

def test_validate_module_config_invalid_weight():
    with pytest.raises(ValueError, match="Weight for module 'bokeh_blur' must be a number"):
        validate_module_config("bokeh_blur", {"weight": "heavy"})
    with pytest.raises(ValueError, match="Weight for module 'bokeh_blur' must be a number"):
        # bool is subclass of int in python, should be explicitly rejected
        validate_module_config("bokeh_blur", {"weight": True})
    with pytest.raises(ValueError, match="Weight for module 'bokeh_blur' must be >= 0"):
        validate_module_config("bokeh_blur", {"weight": -1})

def test_validate_module_config_invalid_enabled():
    with pytest.raises(ValueError, match="Enabled field for module 'bokeh_blur' must be a boolean"):
        validate_module_config("bokeh_blur", {"enabled": "yes"})

def test_validate_module_config_invalid_config_type():
    with pytest.raises(ValueError, match="Parameters 'config' for module 'bokeh_blur' must be a dictionary"):
        validate_module_config("bokeh_blur", {"config": "not-a-dict"})

def test_validate_module_config_unknown_config_keys():
    with pytest.raises(ValueError, match="config contains unknown keys: invalid_param"):
        validate_module_config("bokeh_blur", {"config": {"invalid_param": 123}})

def test_validate_module_config_number_bounds():
    # Min bound (min is 5)
    with pytest.raises(ValueError, match="'blur_strength' must be >= 5"):
        validate_module_config("bokeh_blur", {"config": {"blur_strength": 4}})
    # Max bound (max is 25)
    with pytest.raises(ValueError, match="'blur_strength' must be <= 25"):
        validate_module_config("bokeh_blur", {"config": {"blur_strength": 26}})
    # Invalid float value
    with pytest.raises(ValueError, match="'blur_strength' must be a number"):
        validate_module_config("bokeh_blur", {"config": {"blur_strength": "not-a-number"}})

def test_validate_module_config_select_options():
    # Invalid select option
    with pytest.raises(ValueError, match="'focus_area' contains invalid value"):
        validate_module_config("bokeh_blur", {"config": {"focus_area": "invalid_option"}})

def test_validate_effects_config_success():
    validate_effects_config({
        "bokeh_blur": {
            "enabled": True,
            "weight": 2.5,
            "config": {
                "blur_strength": 10
            }
        }
    })

def test_validate_effects_config_invalid_type():
    with pytest.raises(ValueError, match="effects_config must be a dictionary"):
        validate_effects_config("not-a-dict")

def test_preset_api_validation(authenticated_client, db_session):
    # Test POST /api/presets/effects reject unknown module name
    response = authenticated_client.post(
        "/api/presets/effects",
        json={
            "name": "Test Invalid Preset",
            "groups": {
                "unknown_module": {
                    "enabled": True
                }
            }
        }
    )
    assert response.status_code == 400
    assert "Unknown generation module" in response.json()["detail"]

    # Test POST /api/presets/effects reject invalid weight
    response = authenticated_client.post(
        "/api/presets/effects",
        json={
            "name": "Test Invalid Weight Preset",
            "groups": {
                "bokeh_blur": {
                    "weight": -5
                }
            }
        }
    )
    assert response.status_code == 400
    assert "Weight for module 'bokeh_blur' must be >= 0" in response.json()["detail"]

    # Test POST /api/presets/effects success
    response = authenticated_client.post(
        "/api/presets/effects",
        json={
            "name": "Test Valid Preset",
            "groups": {
                "bokeh_blur": {
                    "enabled": True,
                    "weight": 2.0,
                    "config": {
                        "blur_strength": 12
                    }
                }
            }
        }
    )
    assert response.status_code == 201
    preset_id = response.json()["id"]

    # Test PUT /api/presets/effects/{preset_id} reject invalid option
    response = authenticated_client.put(
        f"/api/presets/effects/{preset_id}",
        json={
            "name": "Test Valid Preset",
            "groups": {
                "bokeh_blur": {
                    "config": {
                        "focus_area": "invalid_val"
                    }
                }
            }
        }
    )
    assert response.status_code == 400
    assert "contains invalid value" in response.json()["detail"]

def test_studio_api_validation(authenticated_client):
    import io
    # Test POST /api/studio/preview reject invalid config
    from PIL import Image
    img = Image.new("RGB", (10, 10))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    response = authenticated_client.post(
        "/api/studio/preview",
        files={"file": ("test.jpg", buf, "image/jpeg")},
        data={
            "effect_id": "bokeh_blur",
            "config": '{"blur_strength": 1}' # less than 5
        }
    )
    assert response.status_code == 400
    assert "must be >= 5" in response.json()["detail"]
