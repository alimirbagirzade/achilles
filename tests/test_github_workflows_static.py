"""Phase 4A — GitHub workflow ŞABLONLARI statik güvenlik testleri (offline).

Workflow GERÇEK çalıştırılmaz; yalnız dosya içeriği doğrulanır: auto-merge yok,
tehlikeli aksiyon yasak metni var, protected-path guard (pre+post) var, doğru CI
komutları var, secret literal değer yok, nightly kod değiştirmiyor, doküman güvenlik
modelini içeriyor.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_WF = _ROOT / ".github" / "workflows"
_TASK = _WF / "claude-code-task.yml"
_NIGHTLY = _WF / "nightly-automation-audit.yml"
_DOC = _ROOT / "docs" / "PHASE4_GITHUB_AUTOMATION.md"
_GUARD = _ROOT / "scripts" / "check_protected_paths.py"


def _r(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_workflow_and_doc_files_exist() -> None:
    assert _TASK.exists()
    assert _NIGHTLY.exists()
    assert _DOC.exists()
    assert _GUARD.exists()


def test_no_auto_merge_mechanism() -> None:
    for p in (_TASK, _NIGHTLY):
        c = _r(p).lower()
        assert "gh pr merge" not in c
        assert "--auto" not in c
        assert "automerge" not in c
        assert "auto_merge" not in c
        assert "merge_method" not in c


def test_task_workflow_forbids_dangerous_actions() -> None:
    c = _r(_TASK)
    assert "train --run" in c  # SERT kurallarda yasak
    assert "Do not push to main" in c
    assert "Do not promote adapters" in c
    assert "Do not modify data/, storage/, vector_db/, models/" in c


def test_task_workflow_has_protected_guard_pre_and_post() -> None:
    c = _r(_TASK)
    assert c.count("check_protected_paths.py") >= 2  # pre + post guard


def test_task_workflow_ci_commands() -> None:
    c = _r(_TASK)
    assert "uv sync --extra dev" in c
    assert "uv run ruff check app tests" in c
    assert "uv run ruff format --check app tests" in c
    assert "uv run mypy app" in c
    assert 'pytest -m "not ollama"' in c


def test_task_workflow_minimal_perms_no_push_main() -> None:
    c = _r(_TASK)
    assert "permissions:" in c
    assert "git push origin main" not in c
    assert "push --force" not in c
    assert "force-push" not in c.lower()


def test_no_literal_secret_values() -> None:
    for p in (_TASK, _NIGHTLY, _DOC):
        c = _r(p)
        assert "sk-ant" not in c  # gerçek Anthropic anahtar deseni yok
    # Secret YALNIZ ${{ secrets.* }} referansıyla geçer (literal değer değil)
    assert "secrets.ANTHROPIC_API_KEY" in _r(_TASK)


def test_task_only_triggers_on_claude_task_label() -> None:
    c = _r(_TASK)
    assert "claude-task" in c
    assert "github.event.label.name == 'claude-task'" in c


def test_nightly_is_report_only_no_code_change() -> None:
    c = _r(_NIGHTLY)
    assert "train --run" not in c
    assert "git commit" not in c
    assert "git push" not in c
    assert "create-pull-request" not in c
    assert "upload-artifact" in c  # rapor repoya commit edilmez → artifact


def test_nightly_cron_default_off() -> None:
    c = _r(_NIGHTLY)
    assert "schedule:" in c
    assert "ENABLE_NIGHTLY_AUDIT" in c  # zamanlanmış koşu varsayılan KAPALI


def test_doc_has_safety_model_sections() -> None:
    d = _r(_DOC)
    assert "Strict Safety Model" in d
    assert "Protected Paths" in d
    assert "ANTHROPIC_API_KEY" in d
    assert "auto-merge" in d.lower() or "merge" in d.lower()
    assert "TEMPLATE" in d or "ŞABLON" in d  # aktivasyon kullanıcıda


def test_guard_referenced_by_task_workflow() -> None:
    assert "scripts/check_protected_paths.py" in _r(_TASK)
