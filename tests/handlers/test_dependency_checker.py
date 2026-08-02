"""
测试 DependencyChecker
"""
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestDependentService:
    def test_from_dict_minimal(self):
        from src.dependency_checker import DependentService
        svc = DependentService.from_dict({
            "name": "ccr",
            "start_cmd": "ccr start",
            "status_cmd": "ccr status",
        })
        assert svc.name == "ccr"
        assert svc.start_cmd == "ccr start"
        assert svc.status_cmd == "ccr status"
        assert svc.running_pattern == "Running"
        assert svc.start_pattern == ""

    def test_from_dict_full(self):
        from src.dependency_checker import DependentService
        svc = DependentService.from_dict({
            "name": "lut",
            "start_cmd": "lut start",
            "status_cmd": "lut status",
            "running_pattern": "Alive",
            "start_pattern": "ok",
        })
        assert svc.running_pattern == "Alive"
        assert svc.start_pattern == "ok"


class TestDependencyChecker:
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """每个测试前重置单例"""
        from src import dependency_checker
        dependency_checker.DependencyChecker._instance = None
        yield
        dependency_checker.DependencyChecker._instance = None

    @pytest.fixture
    def checker(self):
        from src.dependency_checker import DependencyChecker
        return DependencyChecker()

    @pytest.fixture
    def settings_mock(self):
        s = MagicMock()
        s.dependency_check_enabled = True
        s.dependency_check_interval = 30.0
        s.dependency_start_timeout = 5.0
        s.dependency_status_timeout = 5.0
        s.dependent_services = json.dumps([
            {"name": "ccr", "start_cmd": "ccr start",
             "status_cmd": "ccr status", "running_pattern": "Running"},
            {"name": "lut", "start_cmd": "lut start",
             "status_cmd": "lut status", "running_pattern": "Running"},
        ])
        return s

    def test_load_services(self, checker, settings_mock):
        with patch("src.dependency_checker._get_settings_safe", return_value=settings_mock):
            services = checker._load_services()
        assert len(services) == 2
        assert {s.name for s in services} == {"ccr", "lut"}

    def test_load_services_disabled(self, checker, settings_mock):
        settings_mock.dependency_check_enabled = False
        with patch("src.dependency_checker._get_settings_safe", return_value=settings_mock):
            services = checker._load_services()
        assert services == []

    def test_load_services_invalid_json(self, checker, settings_mock):
        settings_mock.dependent_services = "{not-json"
        with patch("src.dependency_checker._get_settings_safe", return_value=settings_mock):
            services = checker._load_services()
        assert services == []

    def test_load_services_missing_field(self, checker, settings_mock):
        settings_mock.dependent_services = json.dumps([{"name": "x"}])
        with patch("src.dependency_checker._get_settings_safe", return_value=settings_mock):
            services = checker._load_services()
        assert services == []

    def test_load_services_not_a_list(self, checker, settings_mock):
        settings_mock.dependent_services = json.dumps({"name": "x"})
        with patch("src.dependency_checker._get_settings_safe", return_value=settings_mock):
            services = checker._load_services()
        assert services == []

    def test_matches_case_insensitive(self, checker):
        assert checker._matches("Status: Running", "running") is True
        assert checker._matches("Status: Stopped", "running") is False

    def test_matches_regex(self, checker):
        assert checker._matches("pid: 12345", r"pid:\s*\d+") is True
        assert checker._matches("no pid here", r"pid:\s*\d+") is False

    def test_matches_invalid_regex_falls_back_to_substring(self, checker):
        # 错误正则不应该抛异常
        assert checker._matches("Hello World", "[invalid") is False

    def test_matches_empty_pattern(self, checker):
        assert checker._matches("anything", "") is False

    @pytest.mark.asyncio
    async def test_ensure_services_running_all_up(self, checker, settings_mock):
        with patch("src.dependency_checker._get_settings_safe", return_value=settings_mock):
            checker._services = checker._load_services()
            async def fake_status(svc, timeout):
                return True, "Status: Running"
            with patch.object(checker, "_check_status", AsyncMock(side_effect=fake_status)):
                summary = await checker.ensure_services_running(force=True)

        assert summary.needs_notification is False
        assert len(summary.results) == 2
        assert all(r.running for r in summary.results)
        assert all(r.started is False for r in summary.results)

    @pytest.mark.asyncio
    async def test_ensure_services_running_start_one(self, checker, settings_mock):
        with patch("src.dependency_checker._get_settings_safe", return_value=settings_mock):
            checker._services = checker._load_services()

            async def fake_status(svc, timeout):
                if svc.name == "ccr":
                    return True, "Status: Running"
                return False, "Status: Not Running"

            async def fake_start(svc):
                return True, "started successfully"

            with patch.object(checker, "_check_status", AsyncMock(side_effect=fake_status)), \
                 patch.object(checker, "_start_service", AsyncMock(side_effect=fake_start)):
                summary = await checker.ensure_services_running(force=True)

        assert summary.needs_notification is True
        by_name = {r.service.name: r for r in summary.results}
        assert by_name["ccr"].started is False
        assert by_name["lut"].started is True

    @pytest.mark.asyncio
    async def test_ensure_services_running_start_fails(self, checker, settings_mock):
        with patch("src.dependency_checker._get_settings_safe", return_value=settings_mock):
            checker._services = checker._load_services()

            async def fake_status(svc, timeout):
                return False, "Not Running"

            async def fake_start(svc):
                return False, "command not found"

            with patch.object(checker, "_check_status", AsyncMock(side_effect=fake_status)), \
                 patch.object(checker, "_start_service", AsyncMock(side_effect=fake_start)):
                summary = await checker.ensure_services_running(force=True)

        assert summary.needs_notification is True
        assert all(r.error for r in summary.results)

    @pytest.mark.asyncio
    async def test_throttle_skips_recent_check(self, checker, settings_mock):
        with patch("src.dependency_checker._get_settings_safe", return_value=settings_mock):
            checker._services = checker._load_services()
            checker._last_check_at = 9999999999.0

            summary = await checker.ensure_services_running(force=False)

        assert summary.skipped is True

    @pytest.mark.asyncio
    async def test_force_bypasses_throttle(self, checker, settings_mock):
        with patch("src.dependency_checker._get_settings_safe", return_value=settings_mock):
            checker._services = checker._load_services()
            checker._last_check_at = 9999999999.0

            async def fake_status(svc, timeout):
                return True, "Running"
            with patch.object(checker, "_check_status", AsyncMock(side_effect=fake_status)):
                summary = await checker.ensure_services_running(force=True)

        assert summary.skipped is False
        assert len(summary.results) == 2

    @pytest.mark.asyncio
    async def test_no_services_returns_empty(self, checker, settings_mock):
        empty_mock = MagicMock()
        empty_mock.dependent_services = ""
        with patch("src.dependency_checker._get_settings_safe", return_value=empty_mock):
            checker._services = []
            checker._loaded = True
            summary = await checker.ensure_services_running(force=True)
        assert summary.results == []
        assert summary.skipped is False

    def test_ensure_services_running_sync_all_up(self, checker, settings_mock):
        with patch("src.dependency_checker._get_settings_safe", return_value=settings_mock):
            checker._services = checker._load_services()

            def fake_status(svc, timeout):
                return True, "Status: Running"
            with patch.object(checker, "_check_status_sync", side_effect=fake_status):
                summary = checker.ensure_services_running_sync(force=True)

        assert summary.needs_notification is False
        assert len(summary.results) == 2
        assert all(r.running for r in summary.results)

    def test_ensure_services_running_sync_start_one(self, checker, settings_mock):
        with patch("src.dependency_checker._get_settings_safe", return_value=settings_mock):
            checker._services = checker._load_services()

            def fake_status(svc, timeout):
                if svc.name == "ccr":
                    return True, "Running"
                return False, "Not Running"

            def fake_start(svc):
                return True, "started successfully"

            with patch.object(checker, "_check_status_sync", side_effect=fake_status), \
                 patch.object(checker, "_start_service_sync", side_effect=fake_start):
                summary = checker.ensure_services_running_sync(force=True)

        assert summary.needs_notification is True
        by_name = {r.service.name: r for r in summary.results}
        assert by_name["lut"].started is True

    def test_ensure_services_running_sync_throttle(self, checker, settings_mock):
        with patch("src.dependency_checker._get_settings_safe", return_value=settings_mock):
            checker._services = checker._load_services()
            checker._last_check_at = 9999999999.0
            summary = checker.ensure_services_running_sync(force=False)
        assert summary.skipped is True

    def test_ensure_services_running_sync_no_services(self, checker, settings_mock):
        empty_mock = MagicMock()
        empty_mock.dependent_services = ""
        with patch("src.dependency_checker._get_settings_safe", return_value=empty_mock):
            checker._services = []
            checker._loaded = True
            summary = checker.ensure_services_running_sync(force=True)
        assert summary.results == []
        assert summary.skipped is False


class TestServiceCheckResult:
    def test_needs_attention_started(self):
        from src.dependency_checker import ServiceCheckResult, DependentService
        svc = DependentService(name="x", start_cmd="x", status_cmd="x")
        r = ServiceCheckResult(service=svc, running=True, started=True)
        assert r.needs_attention is True

    def test_needs_attention_error(self):
        from src.dependency_checker import ServiceCheckResult, DependentService
        svc = DependentService(name="x", start_cmd="x", status_cmd="x")
        r = ServiceCheckResult(service=svc, running=False, error="fail")
        assert r.needs_attention is True

    def test_no_attention_when_running(self):
        from src.dependency_checker import ServiceCheckResult, DependentService
        svc = DependentService(name="x", start_cmd="x", status_cmd="x")
        r = ServiceCheckResult(service=svc, running=True)
        assert r.needs_attention is False


class TestDependencyCheckSummary:
    def test_message_lines(self):
        from src.dependency_checker import (
            DependencyCheckSummary, ServiceCheckResult, DependentService
        )
        svc1 = DependentService(name="ccr", start_cmd="c", status_cmd="c")
        svc2 = DependentService(name="lut", start_cmd="l", status_cmd="l")
        summary = DependencyCheckSummary(results=[
            ServiceCheckResult(service=svc1, running=True, started=True),
            ServiceCheckResult(service=svc2, running=False, error="not found"),
        ])
        lines = summary.message_lines()
        assert any("ccr" in line and "已自动启动" in line for line in lines)
        assert any("lut" in line and "启动失败" in line for line in lines)
