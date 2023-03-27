async def test_config_endpoint(session, client, client_headers, default_branch):
    with client:
        response = client.get(
            "/config",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.json() is not None

    config = response.json()

    assert "logging" in config
    assert "analytics" in config
