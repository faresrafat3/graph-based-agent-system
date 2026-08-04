from tools.json_output_parser import extract_first_json_object, parse_json_object_response


def test_extract_raw_json_object():
    assert extract_first_json_object('{"a": 1}') == {"a": 1}


def test_extract_markdown_json_fence():
    response = '```json\n{"filename": "x.py", "code": "def x(): pass"}\n```'
    parsed = extract_first_json_object(response)
    assert parsed["filename"] == "x.py"


def test_extract_json_from_prose():
    response = 'Here is the output: {"a": "brace } inside string", "b": 2} thanks'
    parsed = extract_first_json_object(response)
    assert parsed == {"a": "brace } inside string", "b": 2}


def test_parse_required_keys_success():
    result = parse_json_object_response('{"filename": "x.py", "code": ""}', required_keys=["filename"])
    assert result["success"] is True
    assert result["violations"] == []


def test_parse_required_keys_failure():
    result = parse_json_object_response('{"code": ""}', required_keys=["filename"])
    assert result["success"] is False
    assert "filename" in result["violations"][0]


def test_parse_invalid_json_failure():
    result = parse_json_object_response("not json")
    assert result["success"] is False
    assert result["data"] == {}


def test_extract_invalid_json_after_brace():
    import pytest
    with pytest.raises(ValueError, match="No valid JSON object found in response:"):
        extract_first_json_object('{"invalid_json')


def test_extract_invalid_input_types():
    import pytest
    with pytest.raises(ValueError, match="Response must be a non-empty string."):
        extract_first_json_object(None)
    with pytest.raises(ValueError, match="Response must be a non-empty string."):
        extract_first_json_object("")
    with pytest.raises(ValueError, match="Response must be a non-empty string."):
        extract_first_json_object(123)


def test_extract_non_dict_decoded_value(monkeypatch):
    import json
    import pytest
    
    original_init = json.JSONDecoder.__init__
    
    def fake_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.raw_decode = lambda s, idx=0: ([], len(s))
        
    monkeypatch.setattr(json.JSONDecoder, "__init__", fake_init)
    
    with pytest.raises(ValueError, match="No valid JSON object found in response"):
        extract_first_json_object('{"a": 1}')


