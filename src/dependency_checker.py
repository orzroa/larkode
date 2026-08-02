"""
依赖服务检查器

在 AI 启动（tmux session 启动）之前检查依赖服务（如 ccr、lut）状态，
未启动则自动拉起。该机制设计为不依赖 AI：当 AI 助手本身不可用时
（依赖服务挂了），仍能保证基础服务可用。

为何放在 tmux 启动时而不是每条命令：
- 没必要每条命令都检查（节流可减少开销）
- tmux 启动意味着 AI 即将开始工作，此刻拉起依赖最合适
- 启动完成后再检查，CCR/LUT 状态已稳定，不会每条命令都看到「启动中」噪音

配置项（在 .env 中）：
- DEPENDENCY_CHECK_ENABLED: 是否启用（默认 true）
- DEPENDENCY_CHECK_INTERVAL: 检查节流间隔（秒，默认 30）
- DEPENDENT_SERVICES: JSON 列表，每项包含:
    - name: 服务名称
    - start_cmd: 启动命令（字符串，shell 解析）
    - status_cmd: 状态检测命令
    - running_pattern: 状态输出中表示「运行中」的正则（不区分大小写）
    - start_pattern: 启动输出中表示「成功」的正则（可选，默认空）
- DEPENDENCY_START_TIMEOUT: 启动超时（秒，默认 15）
- DEPENDENCY_STATUS_TIMEOUT: 状态检测超时（秒，默认 5）
"""
import asyncio
import json
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional

try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

logger = get_logger(__name__) if 'get_logger' in dir() else logging.getLogger(__name__)


def _get_settings_safe():
    """延迟导入 settings，避免循环依赖"""
    try:
        from src.config.settings import get_settings
        return get_settings()
    except Exception:
        return None


@dataclass
class DependentService:
    """依赖服务配置"""
    name: str
    start_cmd: str
    status_cmd: str
    running_pattern: str = "Running"
    start_pattern: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "DependentService":
        return cls(
            name=data["name"],
            start_cmd=data["start_cmd"],
            status_cmd=data["status_cmd"],
            running_pattern=data.get("running_pattern", "Running"),
            start_pattern=data.get("start_pattern", ""),
        )


@dataclass
class ServiceCheckResult:
    """单个服务的检查结果"""
    service: DependentService
    running: bool
    started: bool = False
    error: Optional[str] = None
    detail: str = ""

    @property
    def needs_attention(self) -> bool:
        """是否需要通知用户（启动了 或 出错了）"""
        return self.started or bool(self.error)


@dataclass
class DependencyCheckSummary:
    """一次检查的汇总结果"""
    results: List[ServiceCheckResult] = field(default_factory=list)
    skipped: bool = False

    @property
    def needs_notification(self) -> bool:
        return any(r.needs_attention for r in self.results)

    def message_lines(self) -> List[str]:
        """生成用户可读的通知消息"""
        lines = []
        for r in self.results:
            if r.started:
                lines.append(f"- ✅ **{r.service.name}** 已自动启动")
            elif r.error:
                lines.append(f"- ❌ **{r.service.name}** 启动失败: {r.error}")
        return lines


class DependencyChecker:
    """依赖服务检查器（单例）"""

    _instance: Optional["DependencyChecker"] = None

    def __init__(self):
        self._services: List[DependentService] = []
        self._last_check_at: float = 0.0
        self._lock = asyncio.Lock()
        self._lock_sync = threading.Lock()
        self._loaded = False

    @classmethod
    def instance(cls) -> "DependencyChecker":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_services(self) -> List[DependentService]:
        """从配置加载依赖服务列表"""
        if self._loaded:
            return self._services

        settings = _get_settings_safe()
        if settings is None:
            logger.warning("获取配置失败，依赖服务检查器未启用")
            return []

        if not settings.dependency_check_enabled:
            logger.debug("依赖服务自动检查已禁用")
            return []

        raw = (settings.dependent_services or "").strip()
        if not raw:
            logger.debug("DEPENDENT_SERVICES 未配置，依赖服务检查器跳过")
            return []

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"DEPENDENT_SERVICES JSON 解析失败: {e}")
            return []

        if not isinstance(data, list):
            logger.error("DEPENDENT_SERVICES 必须是 JSON 列表")
            return []

        services: List[DependentService] = []
        for item in data:
            if not isinstance(item, dict):
                logger.warning(f"跳过非字典项: {item}")
                continue
            try:
                services.append(DependentService.from_dict(item))
            except KeyError as e:
                logger.warning(f"依赖服务缺少字段 {e}，跳过: {item}")

        self._services = services
        self._loaded = True
        logger.info(f"已加载 {len(services)} 个依赖服务: {[s.name for s in services]}")
        return services

    def _should_skip(self) -> bool:
        """是否应该跳过本次检查（节流）"""
        if not self._services:
            return True
        settings = _get_settings_safe()
        interval = settings.dependency_check_interval if settings else 30.0
        return (time.time() - self._last_check_at) < interval

    async def ensure_services_running(
        self, force: bool = False
    ) -> DependencyCheckSummary:
        """
        检查所有依赖服务，未运行则启动。

        Args:
            force: 强制检查（忽略节流）。

        Returns:
            DependencyCheckSummary: 检查结果汇总
        """
        services = self._load_services()
        summary = DependencyCheckSummary()

        if not services:
            return summary

        if not force and self._should_skip():
            summary.skipped = True
            return summary

        async with self._lock:
            if not force and self._should_skip():
                summary.skipped = True
                return summary

            self._last_check_at = time.time()
            logger.debug("开始检查依赖服务状态")

            for svc in services:
                try:
                    result = await self._check_and_start(svc)
                except Exception as e:
                    logger.error(f"检查 {svc.name} 时异常: {e}", exc_info=True)
                    result = ServiceCheckResult(
                        service=svc,
                        running=False,
                        error=str(e),
                    )
                summary.results.append(result)

        return summary

    async def _check_and_start(self, svc: DependentService) -> ServiceCheckResult:
        """检查单个服务，未运行则启动"""
        settings = _get_settings_safe()
        status_timeout = settings.dependency_status_timeout if settings else 5.0

        running, detail = await self._check_status(svc, timeout=status_timeout)
        if running:
            logger.debug(f"{svc.name} 已在运行")
            return ServiceCheckResult(service=svc, running=True, detail=detail)

        logger.info(f"{svc.name} 未运行，尝试启动")
        started, start_detail = await self._start_service(svc)

        if started:
            logger.info(f"{svc.name} 启动成功")
            return ServiceCheckResult(
                service=svc,
                running=True,
                started=True,
                detail=start_detail,
            )

        logger.error(f"{svc.name} 启动失败: {start_detail}")
        return ServiceCheckResult(
            service=svc,
            running=False,
            error=start_detail,
        )

    async def _check_status(
        self, svc: DependentService, timeout: float
    ) -> tuple:
        """执行状态检测"""
        try:
            proc = await asyncio.create_subprocess_shell(
                svc.status_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                return False, f"status 检测超时（{timeout}s）"

            output = (stdout or b"").decode("utf-8", errors="replace")
            if stderr:
                output += "\n" + stderr.decode("utf-8", errors="replace")

            running = self._matches(output, svc.running_pattern)
            return running, output.strip()
        except FileNotFoundError:
            return False, f"命令不存在: {svc.status_cmd.split()[0]}"
        except Exception as e:
            return False, f"status 执行失败: {e}"

    async def _start_service(self, svc: DependentService) -> tuple:
        """执行启动命令"""
        settings = _get_settings_safe()
        start_timeout = settings.dependency_start_timeout if settings else 15.0

        try:
            proc = await asyncio.create_subprocess_shell(
                svc.start_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=start_timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                # 启动后台进程时常见「启动后 detach」，超时未必是失败
                return True, f"启动命令超时（{start_timeout}s），可能已在后台运行"

            output = (stdout or b"").decode("utf-8", errors="replace")
            if stderr:
                output += "\n" + stderr.decode("utf-8", errors="replace")

            if proc.returncode == 0:
                return True, output.strip()
            if svc.start_pattern and self._matches(output, svc.start_pattern):
                return True, output.strip()
            return False, output.strip() or f"返回码 {proc.returncode}"
        except FileNotFoundError:
            return False, f"命令不存在: {svc.start_cmd.split()[0]}"
        except Exception as e:
            return False, f"启动失败: {e}"

    @staticmethod
    def _matches(output: str, pattern: str) -> bool:
        """正则匹配（不区分大小写）"""
        if not pattern:
            return False
        try:
            return bool(re.search(pattern, output, re.IGNORECASE))
        except re.error:
            return pattern.lower() in output.lower()

    def ensure_services_running_sync(
        self, force: bool = False
    ) -> DependencyCheckSummary:
        """同步版本：使用 subprocess 替代 asyncio.create_subprocess_shell。
        适用于不能 await 的场景（如 tmux session 启动前的同步检查）。"""
        services = self._load_services()
        summary = DependencyCheckSummary()

        if not services:
            return summary

        if not force and self._should_skip():
            summary.skipped = True
            return summary

        with self._lock_sync:
            if not force and self._should_skip():
                summary.skipped = True
                return summary

            self._last_check_at = time.time()
            logger.debug("开始同步检查依赖服务状态")

            for svc in services:
                try:
                    result = self._check_and_start_sync(svc)
                except Exception as e:
                    logger.error(f"同步检查 {svc.name} 时异常: {e}", exc_info=True)
                    result = ServiceCheckResult(
                        service=svc,
                        running=False,
                        error=str(e),
                    )
                summary.results.append(result)

        return summary

    def _check_and_start_sync(self, svc: DependentService) -> ServiceCheckResult:
        """同步检查单个服务"""
        settings = _get_settings_safe()
        status_timeout = settings.dependency_status_timeout if settings else 5.0

        running, detail = self._check_status_sync(svc, timeout=status_timeout)
        if running:
            logger.debug(f"{svc.name} 已在运行")
            return ServiceCheckResult(service=svc, running=True, detail=detail)

        logger.info(f"{svc.name} 未运行，尝试启动")
        started, start_detail = self._start_service_sync(svc)

        if started:
            logger.info(f"{svc.name} 启动成功")
            return ServiceCheckResult(
                service=svc,
                running=True,
                started=True,
                detail=start_detail,
            )

        logger.error(f"{svc.name} 启动失败: {start_detail}")
        return ServiceCheckResult(
            service=svc,
            running=False,
            error=start_detail,
        )

    def _check_status_sync(
        self, svc: DependentService, timeout: float
    ) -> tuple:
        """同步执行状态检测"""
        try:
            result = subprocess.run(
                svc.status_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout or ""
            if result.stderr:
                output += "\n" + result.stderr
            running = self._matches(output, svc.running_pattern)
            return running, output.strip()
        except subprocess.TimeoutExpired:
            return False, f"status 检测超时（{timeout}s）"
        except FileNotFoundError:
            return False, f"命令不存在: {svc.status_cmd.split()[0]}"
        except Exception as e:
            return False, f"status 执行失败: {e}"

    def _start_service_sync(self, svc: DependentService) -> tuple:
        """同步执行启动命令"""
        settings = _get_settings_safe()
        start_timeout = settings.dependency_start_timeout if settings else 15.0

        try:
            result = subprocess.run(
                svc.start_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=start_timeout,
            )
            output = result.stdout or ""
            if result.stderr:
                output += "\n" + result.stderr

            if result.returncode == 0:
                return True, output.strip()
            if svc.start_pattern and self._matches(output, svc.start_pattern):
                return True, output.strip()
            return False, output.strip() or f"返回码 {result.returncode}"
        except subprocess.TimeoutExpired:
            # 启动后台进程时常见「启动后 detach」，超时未必是失败
            return True, f"启动命令超时（{start_timeout}s），可能已在后台运行"
        except FileNotFoundError:
            return False, f"命令不存在: {svc.start_cmd.split()[0]}"
        except Exception as e:
            return False, f"启动失败: {e}"


# 全局访问入口
def get_dependency_checker() -> DependencyChecker:
    return DependencyChecker.instance()
