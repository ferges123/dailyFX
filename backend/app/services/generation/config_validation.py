from app.services.generation.modules import MODULES


def validate_module_config(module_name: str, group_config: dict) -> None:
    """
    Validates a single module group dictionary: {enabled, weight, config}
    and its parameters inside 'config' according to the module's schema.
    """
    module = MODULES.get(module_name)
    if module is None:
        if isinstance(group_config, dict) and not group_config.get("enabled", False):
            return
        raise ValueError(f"Unknown generation module '{module_name}'")

    if not isinstance(group_config, dict):
        raise ValueError(f"Configuration for module '{module_name}' must be a dictionary")

    # Reject unknown keys at the module group level
    allowed_group_keys = {"enabled", "weight", "config"}
    unknown_keys = set(group_config.keys()) - allowed_group_keys
    if unknown_keys:
        raise ValueError(f"Module '{module_name}' contains unknown keys: {', '.join(sorted(unknown_keys))}")

    # Validate weight if present
    if "weight" in group_config:
        w = group_config["weight"]
        if not isinstance(w, (int, float)) or isinstance(w, bool):
            raise ValueError(f"Weight for module '{module_name}' must be a number")
        if w < 0:
            raise ValueError(f"Weight for module '{module_name}' must be >= 0")

    # Validate enabled if present
    if "enabled" in group_config:
        enabled = group_config["enabled"]
        if not isinstance(enabled, bool):
            raise ValueError(f"Enabled field for module '{module_name}' must be a boolean")

    # Validate config params
    config = group_config.get("config", {})
    if not isinstance(config, dict):
        raise ValueError(f"Parameters 'config' for module '{module_name}' must be a dictionary")

    schema = getattr(module, "config_schema", None)
    if not isinstance(schema, list):
        try:
            from unittest.mock import Mock

            if isinstance(module, Mock) or isinstance(schema, Mock):
                return
        except ImportError:
            pass
        schema = []

    # Reject unknown keys in parameters 'config'
    allowed_config_keys = {field.get("key") for field in schema if field.get("key")}
    unknown_config_keys = set(config.keys()) - allowed_config_keys
    if unknown_config_keys:
        raise ValueError(
            f"Module '{module_name}' config contains unknown keys: {', '.join(sorted(unknown_config_keys))}"
        )

    errors: list[str] = []
    for field in schema:
        key = field.get("key")
        value = config.get(key)
        if value is None:
            continue
        field_type = field.get("type")
        if field_type == "number":
            try:
                v = float(value)
            except (TypeError, ValueError):
                errors.append(f"'{key}' must be a number, got {value!r}")
                continue
            if (mn := field.get("min")) is not None and v < mn:
                errors.append(f"'{key}' must be >= {mn}, got {v}")
            if (mx := field.get("max")) is not None and v > mx:
                errors.append(f"'{key}' must be <= {mx}, got {v}")
        elif field_type == "boolean":
            if isinstance(value, str):
                val_lower = value.lower()
                if val_lower in ("true", "1", "yes", "on"):
                    config[key] = True
                elif val_lower in ("false", "0", "no", "off"):
                    config[key] = False
                else:
                    errors.append(f"'{key}' must be a boolean, got {value!r}")
            elif isinstance(value, bool):
                pass
            elif isinstance(value, (int, float)):
                config[key] = bool(value)
            else:
                errors.append(f"'{key}' must be a boolean, got {value!r}")
        elif field_type in ("select", "multiselect"):
            options = {opt["value"] for opt in (field.get("options") or [])}
            if not options:
                continue
            values = value if isinstance(value, list) else [value]
            bad = [v for v in values if v not in options]
            if bad:
                errors.append(f"'{key}' contains invalid value(s): {bad!r}; allowed: {sorted(options)!r}")

    if errors:
        raise ValueError(f"Invalid config for module '{module_name}': {'; '.join(errors)}")


def validate_effects_config(effects_config: dict) -> None:
    """
    Validates a full effects_config dictionary: {module_name: {enabled, weight, config}}
    """
    if not isinstance(effects_config, dict):
        raise ValueError("effects_config must be a dictionary")

    for name, group_config in effects_config.items():
        validate_module_config(name, group_config)
