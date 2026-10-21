"""The UI is generated from /tools; conditional fields must carry a `show_when` hint."""


def props(client, tool_id):
    tool = next(t for t in client.get("/api/v1/tools").json() if t["id"] == tool_id)
    return tool["params_schema"]["properties"]


def test_split_fields_declare_when_they_apply(client):
    p = props(client, "split")
    assert p["ranges"]["show_when"] == {"mode": ["ranges", "extract", "remove"]}
    assert p["every"]["show_when"] == {"mode": ["every"]}
    assert p["max_kb"]["show_when"] == {"mode": ["size"]}
    assert p["merge_after"]["show_when"] == {"mode": ["ranges"]}


def test_watermark_text_fields_only_in_text_mode(client):
    p = props(client, "watermark")
    for name in ("text", "font", "font_size"):
        assert p[name]["show_when"] == {"mode": ["text"]}
    assert p["scale"]["show_when"] == {"mode": ["image"]}


def test_secret_fields_are_flagged_for_the_ui(client):
    p = props(client, "protect")
    assert p["password"]["secret"] is True
    assert p["owner_password"]["secret"] is True


def test_every_show_when_references_an_existing_field_and_value(client):
    for tool in client.get("/api/v1/tools").json():
        properties = tool["params_schema"]["properties"]
        for name, spec in properties.items():
            for dep, values in spec.get("show_when", {}).items():
                assert dep in properties, f"{tool['id']}.{name} depends on missing {dep}"
                allowed = properties[dep].get("enum", [])
                assert set(values) <= set(allowed), f"{tool['id']}.{name} has unknown values"
