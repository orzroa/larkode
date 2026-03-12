"""
AI 执行器基础类
"""
import asyncio
import shlex
from pathlib import Path
from typing import Optional, AsyncGenerator

from src.config.settings import get_settings

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class AIExecutor:
    """AI 执行器基础类"""

    def __init__(self, workspace: Optional[Path] = None):
        self.workspace = workspace or get_settings().CLAUDE_CODE_WORKSPACE_DIR
        self._running_process = None

    async def execute_command(
        self,
        command: str,
        workspace: Optional[Path] = None
    ) -> AsyncGenerator[str, None]:
        """
        执行 Claude Code 命令并实时返回输出

        Args:
            command: 要执行的命令
            workspace: 工作目录

        Yields:
            str: 命令输出
        """
        work_dir = workspace or self.workspace

        if not work_dir or not work_dir.exists():
            yield f"错误: 工作目录不存在: {work_dir}"
            return

        logger.info(f"开始执行命令: {command}")

        try:
            # 获取 AI CLI 的完整路径
            claude_code_cli_path = get_settings().CLAUDE_CODE_CLI_PATH

            if not Path(claude_code_cli_path).exists():
                yield f"错误: AI CLI 未找到: {claude_code_cli_path}"
                return

            # 使用 AI CLI 执行命令
            cmd_args = [claude_code_cli_path] + shlex.split(command)

            logger.info(f"执行命令: {' '.join(cmd_args)}")

            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                cwd=str(work_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            self._running_process = process

            # 实时读取输出
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                yield line.decode('utf-8', errors='replace').rstrip('\n')

            # 等待进程结束
            return_code = await process.wait()

            # 读取错误输出
            if process.stderr:
                stderr_content = await process.stderr.read()
                if stderr_content:
                    yield f"\n错误输出:\n{stderr_content.decode('utf-8', errors='replace')}"

            if return_code != 0:
                yield f"\n命令执行失败，返回码: {return_code}"

        except Exception as e:
            logger.error(f"执行命令时出错: {e}", exc_info=True)
            yield f"\n执行出错: {str(e)}"
        finally:
            self._running_process = None

    def cancel_task(self, task_id: str) -> bool:
        """取消正在运行的进程"""
        if self._running_process:
            self._running_process.terminate()
            logger.info(f"已取消执行")
            return True
        return False

    def is_task_running(self, task_id: str) -> bool:
        """检查是否有进程在运行"""
        return self._running_process is not None