from pathlib import Path


def test_compose_shares_runtime_state_volume() -> None:
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "- runtime-state:/app/run" in compose_text
    assert "runtime-state:" in compose_text
