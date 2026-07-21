"""AutoDriver — çevrimdışı testler (sahte runner; gerçek `claude -p` spawn YOK).

deep-hunt'ı claude -p ile sürme + PASS→onaya ilerletme + Kural-8 (onayda durur, eğitim
asla otomatik başlamaz) doğrulanır.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.orchestration.driver import (
    AutoDriver,
    build_hunt_command,
    parse_hunt_verdict,
)
from app.orchestration.orchestrator import RunContext, StageResult, TrainingOrchestrator
from app.orchestration.pipeline import StageStatus
from app.orchestration.store import OrchestrationStore


def _drive_delegates() -> dict:
    def make(status: StageStatus, msg: str):
        def d(ctx: RunContext) -> StageResult:
            return StageResult(status, msg, {})

        return d

    def deep_hunt(ctx: RunContext) -> StageResult:
        if ctx.params.get("hunt_ack"):
            return StageResult(StageStatus.completed, "ack", {})
        return StageResult(StageStatus.blocked, "hunt_ack yok", {})

    return {
        "preflight": make(StageStatus.completed, "preflight ok"),
        "deep-hunt": deep_hunt,
        "data-gate": make(StageStatus.completed, "GO"),
        "curriculum": make(StageStatus.completed, "L0-L4"),
        "dry-run": make(StageStatus.completed, "komut hazır"),
        "approval": make(StageStatus.blocked, "taze onay gerekli"),  # Kural 8 sınırı
        "train": make(StageStatus.blocked, "handoff"),
        "evaluate": make(StageStatus.skipped, "handoff"),
        "registry": make(StageStatus.skipped, "handoff"),
    }


@pytest.fixture
def driver(tmp_path: Path) -> AutoDriver:
    orch = TrainingOrchestrator(
        store=OrchestrationStore(db_path=tmp_path / "drv.db"), delegates=_drive_delegates()
    )
    return AutoDriver(orchestrator=orch)


def _fake_pass(
    command: list[str], timeout: int, env: dict[str, str] | None = None
) -> tuple[int, str]:
    return 0, "denetim raporu...\nciddi bulgu yok\nACHILLES_HUNT_VERDICT: PASS\n"


def _fake_fail(
    command: list[str], timeout: int, env: dict[str, str] | None = None
) -> tuple[int, str]:
    return 0, "BLOCKER: x\nACHILLES_HUNT_VERDICT: FAIL bir sorun var\n"


# ── saf yardımcılar ───────────────────────────────────────────────────────────


def test_build_command_is_claude_p() -> None:
    cmd = build_hunt_command({"adapter_name": "myad"})
    assert cmd[0] == "claude" and cmd[1] == "-p"
    assert "myad" in cmd[2] and "KADEME-2" in cmd[2]
    assert "EĞİTİM BAŞLATMA" in cmd[2]  # salt-rapor güvencesi promptta


def test_parse_verdict() -> None:
    assert parse_hunt_verdict("...\nACHILLES_HUNT_VERDICT: PASS")["passed"] is True
    assert parse_hunt_verdict("...\nACHILLES_HUNT_VERDICT: FAIL x")["passed"] is False
    assert parse_hunt_verdict("verdict yok")["passed"] is False  # güvenli taraf


# ── drive ─────────────────────────────────────────────────────────────────────


def test_dry_run_does_not_spawn(driver: AutoDriver) -> None:
    run_id = driver.orch.start(model="m", profile="p", adapter_name="a")
    res = driver.drive(run_id, execute=False)
    assert res["ok"] is True
    assert res["drove"] is False
    assert res["dry_run"] is True
    assert res["command"][0] == "claude"
    # deep-hunt hâlâ blocked (sürülmedi)
    by_name = {s["name"]: s for s in res["stages"]}
    assert by_name["deep-hunt"]["status"] == StageStatus.blocked.value


def test_pass_advances_to_approval_and_stops(driver: AutoDriver) -> None:
    run_id = driver.orch.start(model="m", profile="p", adapter_name="a")
    res = driver.drive(run_id, execute=True, runner=_fake_pass)
    assert res["ok"] is True and res["drove"] is True and res["hunt_passed"] is True
    by_name = {s["name"]: s for s in res["stages"]}
    assert by_name["deep-hunt"]["status"] == StageStatus.completed.value
    assert by_name["data-gate"]["status"] == StageStatus.completed.value
    # Kural 8: onay kapısında DURUR; gerçek eğitim ASLA otomatik başlamaz
    assert res["run"]["status"] == "blocked"
    assert res["run"]["current_stage"] == "approval"
    assert by_name["train"]["status"] != StageStatus.completed.value


def test_fail_keeps_hunt_blocked(driver: AutoDriver) -> None:
    run_id = driver.orch.start(model="m", profile="p", adapter_name="a")
    res = driver.drive(run_id, execute=True, runner=_fake_fail)
    assert res["drove"] is True and res["hunt_passed"] is False
    by_name = {s["name"]: s for s in res["stages"]}
    assert by_name["deep-hunt"]["status"] == StageStatus.blocked.value
    assert by_name["approval"]["status"] == StageStatus.pending.value  # ulaşmadı


def test_runner_exception_is_safe(driver: AutoDriver) -> None:
    def boom(
        command: list[str], timeout: int, env: dict[str, str] | None = None
    ) -> tuple[int, str]:
        raise RuntimeError("spawn patladı")

    run_id = driver.orch.start(model="m", profile="p", adapter_name="a")
    res = driver.drive(run_id, execute=True, runner=boom)
    assert res["ok"] is False
    assert "patladı" in res["reason"]
    # koşu çökmez; deep-hunt bloklu kalır
    assert driver.orch.store.get_stage(run_id, "deep-hunt")["status"] == StageStatus.blocked.value


def test_unknown_run_returns_error(driver: AutoDriver) -> None:
    res = driver.drive("orc_yok", execute=False)
    assert res["ok"] is False
