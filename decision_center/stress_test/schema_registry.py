import json
from pathlib import Path

from decision_center.stress_test.models import SchemaDescriptor, SchemaRunTarget


def discover_schemas(schemas_dir: Path) -> list[SchemaDescriptor]:
    discovered: list[SchemaDescriptor] = []
    for path in sorted(schemas_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue

        if not isinstance(raw, dict):
            continue

        if "schema" in raw:
            schema_dict = raw.get("schema")
        else:
            schema_dict = raw
            reserved_keys = {"name", "description"}
            if set(raw.keys()).issubset(reserved_keys):
                continue

        if not isinstance(schema_dict, dict) or not schema_dict:
            continue

        discovered.append(
            SchemaDescriptor(
                slug=path.stem,
                path=path,
                display_name=raw.get("name", path.stem),
                description=raw.get("description", ""),
                schema_dict=schema_dict,
            )
        )

    return discovered


def expand_schema_selection(selection: str, schemas: list[SchemaDescriptor]) -> list[SchemaRunTarget]:
    schema_map = {schema.slug: schema for schema in schemas}

    if selection == "all":
        targets = [
            SchemaRunTarget(mode="schema", slug=schema.slug, descriptor=schema)
            for schema in schemas
        ]
        targets.append(SchemaRunTarget(mode="none", slug="none", descriptor=None))
        return targets

    if selection == "none":
        return [SchemaRunTarget(mode="none", slug="none", descriptor=None)]

    if selection not in schema_map:
        available = ", ".join([*schema_map.keys(), "none", "all"])
        raise ValueError(f"Unknown schema '{selection}'. Available values: {available}")

    return [SchemaRunTarget(mode="schema", slug=selection, descriptor=schema_map[selection])]
