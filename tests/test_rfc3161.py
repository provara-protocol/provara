import pytest
import hashlib
from datetime import datetime
from unittest.mock import MagicMock, patch
from provara import rfc3161
from provara.rfc3161 import request_timestamp, verify_timestamp, store_timestamp, verify_all_timestamps, TimestampResult


@pytest.fixture(autouse=True)
def _mock_rfc3161(monkeypatch):
    """Inject a MagicMock as rfc3161_client in the provara.rfc3161 module."""
    mock = MagicMock()
    monkeypatch.setattr(rfc3161, "rfc3161_client", mock)
    monkeypatch.setattr(rfc3161, "HAS_RFC3161", True)
    return mock


@pytest.fixture
def mock_client(_mock_rfc3161):
    """Provide the mock rfc3161_client for tests that configure it."""
    return _mock_rfc3161


@pytest.fixture
def mock_tsa_response():
    return b"dummy-timestamp-token"


def test_request_timestamp(mock_client, mock_tsa_response):
    event_hash = hashlib.sha256(b"test event").digest()
    mock_client.request.return_value = mock_tsa_response

    token = request_timestamp(event_hash)
    assert token == mock_tsa_response
    mock_client.request.assert_called_once_with(
        "http://timestamp.digicert.com",
        data=event_hash,
        hash_data=True
    )


def test_verify_timestamp_valid(mock_client, mock_tsa_response):
    event_hash = hashlib.sha256(b"test event").digest()
    gen_time = datetime(2026, 2, 18, 12, 0, 0)
    tst_info = {
        'gen_time': gen_time,
        'policy': '1.2.3.4',
        'serial_number': 12345,
        'hash_algorithm': 'sha256'
    }
    mock_client.verify.return_value = (True, tst_info)

    result = verify_timestamp(mock_tsa_response, event_hash)
    assert result.valid is True
    assert result.timestamp == gen_time
    assert result.serial_number == 12345


def test_verify_timestamp_invalid(mock_client):
    event_hash = hashlib.sha256(b"test event").digest()
    mock_client.verify.return_value = (False, {})

    result = verify_timestamp(b"bad-token", event_hash)
    assert result.valid is False


def test_store_and_retrieve_timestamp(tmp_path, mock_tsa_response):
    vault_path = tmp_path / "vault"
    event_id = "evt_123"
    store_timestamp(vault_path, event_id, mock_tsa_response)

    ts_file = vault_path / "timestamps" / f"{event_id}.tst"
    assert ts_file.exists()
    assert ts_file.read_bytes() == mock_tsa_response


def test_verify_all_timestamps(mock_client, tmp_path, mock_tsa_response):
    vault_path = tmp_path / "vault"
    events_dir = vault_path / "events"
    events_dir.mkdir(parents=True)

    event_id = "evt_123"
    from provara.canonical_json import canonical_dumps
    event = {"event_id": event_id, "type": "OBS", "payload": {}}
    (events_dir / "events.ndjson").write_text(canonical_dumps(event) + "\n")

    store_timestamp(vault_path, event_id, mock_tsa_response)

    tst_info = {'gen_time': datetime.now(), 'policy': '1.1', 'serial_number': 1}
    mock_client.verify.return_value = (True, tst_info)

    results = verify_all_timestamps(vault_path)
    assert len(results) == 1
    assert results[0].event_id == event_id
    assert results[0].valid is True


def test_handle_tsa_unavailable(mock_client):
    event_hash = hashlib.sha256(b"test").digest()
    mock_client.request.side_effect = Exception("Connection refused")

    with pytest.raises(Exception, match="Connection refused"):
        request_timestamp(event_hash)


def test_dependency_missing_error():
    with patch("provara.rfc3161.HAS_RFC3161", False):
        with pytest.raises(ImportError, match="requires the 'rfc3161-client' package"):
            request_timestamp(b"hash")
