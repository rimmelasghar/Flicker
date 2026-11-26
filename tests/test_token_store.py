from server.auth import TOKEN_FILE, TokenStore


def test_creates_and_persists_token(tmp_path):
    store = TokenStore(tmp_path)
    assert len(store.current) >= 40
    assert (tmp_path / TOKEN_FILE).read_text() == store.current


def test_reuses_token_across_restarts(tmp_path):
    first = TokenStore(tmp_path).current
    assert TokenStore(tmp_path).current == first


def test_empty_token_file_gets_new_token(tmp_path):
    (tmp_path / TOKEN_FILE).write_text("")
    assert TokenStore(tmp_path).current


def test_rotate_replaces_and_persists(tmp_path):
    store = TokenStore(tmp_path)
    old = store.current
    new = store.rotate()
    assert new != old
    assert store.current == new
    assert TokenStore(tmp_path).current == new
