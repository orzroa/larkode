"""
Tmux 会话管理
"""
import subprocess
import time
import os
from pathlib import Path
from typing import Optional, AsyncGenerator

import psutil
from src.config.settings import get_settings
from src.utils.text_utils import clean_ansi_codes

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# 常量定义
AI_STARTUP_WAIT_SECONDS = 3  # 等待 AI 进程启动的时间
AI_READY_POLL_INTERVAL = 0.5  # 轮询检查 AI 就绪的间隔
MAX_READY_WAIT_SECONDS = 5  # 最大等待 AI 就绪时间


class TmuxSessionManager:
    """Tmux 会话管理器"""

    TMUX_SESSION_NAME = "cc"

    def __init__(self, workspace: Optional[Path] = None):
        # 根据 AI_ASSISTANT_TYPE 配置选择 CLI 和 tmux session
        if get_settings().AI_ASSISTANT_TYPE == "iflow":
            self._cli_path = get_settings().IFLOW_CLI
            self.workspace = workspace or get_settings().IFLOW_DIR
        else:
            self._cli_path = get_settings().CLAUDE_CODE_CLI_PATH
            self.workspace = workspace or get_settings().CLAUDE_CODE_WORKSPACE_DIR

        self._tmux_session = get_settings().TMUX_SESSION_NAME

        # 输出初始化调试信息
        self._log_debug_info()

    def _log_debug_info(self):
        """输出当前配置的调试信息"""
        logger.info("=" * 50)
        logger.info("📋 AI 会话管理器配置信息:")
        logger.info(f"  - 工作目录: {self.workspace}")
        logger.info(f"  - CLI 命令: {self._cli_path}")
        logger.info(f"  - Tmux 会话名: {self._tmux_session}")

        # 输出 tmux 会话列表
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True
            )
            sessions = result.stdout.strip().split('\n') if result.stdout.strip() else []
            logger.info(f"  - Tmux 会话数: {len(sessions)}")
            for s in sessions:
                logger.info(f"    - {s}")
        except Exception as e:
            logger.warning(f"  - 获取 tmux 会话列表失败: {e}")

        # 输出 Claude 进程信息
        self._log_claude_processes()

    def _log_claude_processes(self):
        """输出 Claude 进程信息"""
        process_name = get_settings().get_process_name()
        cli_keyword = os.path.basename(self._cli_path).split()[0] if self._cli_path else "claude"

        logger.info(f"  - 进程检测关键字: {cli_keyword} / {process_name}")

        found_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if not proc.info['cmdline']:
                    continue
                cmdline_str = ' '.join(proc.info['cmdline']).lower()
                name_lower = proc.info['name'].lower() if proc.info['name'] else ''

                if cli_keyword in cmdline_str or cli_keyword in name_lower or \
                   process_name in cmdline_str or process_name in name_lower:
                    # 获取工作目录
                    try:
                        cwd = proc.info['cmdline'][0] if proc.info['cmdline'] else ''
                    except:
                        cwd = 'unknown'

                    found_processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmdline': ' '.join(proc.info['cmdline'][:3])  # 只显示前3个参数
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if found_processes:
            logger.info(f"  - 找到 {len(found_processes)} 个相关进程:")
            for p in found_processes[:5]:  # 最多显示5个
                logger.info(f"    - PID={p['pid']}: {p['name']} {p['cmdline']}")
        else:
            logger.info("  - 未找到相关进程")

        logger.info("=" * 50)

    def _check_tmux_session(self) -> bool:
        """检查 tmux session 是否存在"""
        try:
            result = subprocess.run(
                ["tmux", "list-sessions"],
                capture_output=True,
                text=True
            )
            exists = self._tmux_session in result.stdout
            logger.debug(f"  → tmux session '{self._tmux_session}' 存在: {exists}")
            if result.stdout.strip():
                logger.debug(f"  → 所有 session:\n{result.stdout.strip()}")
            return exists
        except Exception as e:
            logger.error(f"检查 tmux session 失败: {e}")
            return False

    def _check_ai_running_in_session(self) -> bool:
        """检查 tmux session 中是否有对应的进程在运行"""
        cli_keyword = os.path.basename(self._cli_path.split()[0]).lower()
        process_name = get_settings().get_process_name()

        logger.debug(f"  → 检查 AI 进程: cli_keyword={cli_keyword}, process_name={process_name}")

        try:
            # 获取 tmux session 的 pane_pid
            result = subprocess.run(
                ["tmux", "list-panes", "-t", self._tmux_session, "-F", "#{pane_pid}"],
                capture_output=True,
                text=True,
                check=True
            )

            if not result.stdout.strip():
                logger.debug(f"  → tmux session '{self._tmux_session}' 没有 pane")
                return False

            pane_pid = result.stdout.strip()
            logger.debug(f"  → pane_pid: {pane_pid}")

            # 从 pane_pid 向下查找所有子进程（更高效）
            try:
                parent = psutil.Process(int(pane_pid))
                for child in parent.children(recursive=True):
                    try:
                        # 使用 psutil 方法而非 .info 属性（兼容不同版本）
                        cmdline = child.cmdline() or []
                        cmdline_str = ' '.join(cmdline).lower()
                        name = child.name() or ''
                        name_lower = name.lower()

                        cli_match = cli_keyword in cmdline_str or cli_keyword in name_lower
                        name_match = process_name in name_lower
                        process_match = process_name in cmdline_str

                        if cli_match or name_match or process_match:
                            logger.debug(f"  → 找到 AI 进程: pid={child.pid}, name={name}")
                            return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                logger.debug(f"  → pane_pid {pane_pid} 不存在或无法访问")
                return False

            return False
        except subprocess.CalledProcessError:
            logger.warning(f"tmux session '{self._tmux_session}' 不存在或无法访问")
            return False
        except Exception as e:
            logger.error(f"检查 session 中 AI 进程失败: {e}", exc_info=True)
            return False

    def _create_tmux_session(self) -> bool:
        """创建 tmux session 并启动 AI"""
        try:
            logger.info(f"🆕 创建 tmux session: {self._tmux_session}")
            logger.info(f"  → 工作目录: {self.workspace}")
            logger.info(f"  → 启动命令: {self._cli_path}")
            logger.info(f"  → 完整命令: cd {self.workspace} && {self._cli_path}")

            # 先 kill 可能存在的同名 session
            subprocess.run(["tmux", "kill-session", "-t", self._tmux_session],
                      capture_output=True)
            logger.info(f"  → 已清理旧 session")

            # 创建新的 session，启动 AI
            cmd = [
                "tmux", "new-session", "-d",
                "-s", self._tmux_session,
                "-n", "ai",
                f"cd {self.workspace} && {self._cli_path}"
            ]
            logger.info(f"  → 执行: {' '.join(cmd)}")

            subprocess.run(cmd, check=True)
            logger.info(f"✅ tmux session {self._tmux_session} 已创建，AI 已启动")

            # 等待 AI 进程启动
            time.sleep(AI_STARTUP_WAIT_SECONDS)

            return True
        except Exception as e:
            logger.error(f"创建 tmux session 失败: {e}", exc_info=True)
            return False

    def _ensure_tmux_session(self) -> tuple[bool, bool]:
        """确保 tmux session 存在且 AI 进程在运行

        Returns:
            tuple[bool, bool]: (是否成功, 是否刚刚启动了新的 AI 进程)
        """
        logger.info("🔍 检查 tmux session 状态...")

        # 检查 tmux session 是否存在
        has_tmux = self._check_tmux_session()
        logger.info(f"  - tmux session '{self._tmux_session}' 存在: {has_tmux}")

        # 检查 AI 进程是否在运行
        ai_running = self._check_ai_running_in_session()
        logger.info(f"  - AI 进程运行中: {ai_running}")

        if not has_tmux:
            # tmux session 不存在，创建新 session
            logger.info(f"  → 创建新 tmux session: {self._tmux_session}")
            logger.info(f"  → 启动命令: cd {self.workspace} && {self._cli_path}")
            success = self._create_tmux_session()
            return success, True  # 返回 True 表示刚刚创建了新 session

        # tmux session 存在，检查 AI 进程是否在运行
        if not ai_running:
            logger.warning(f"tmux session '{self._tmux_session}' 存在但 AI 进程未运行，尝试启动...")
            success = self._start_ai_in_existing_session()
            return success, True  # 返回 True 表示刚刚启动了 AI 进程

        return True, False  # session 和 AI 进程都在运行

    def _start_ai_in_existing_session(self) -> bool:
        """在现有的 tmux session 中启动 AI"""
        try:
            logger.info(f"🚀 在 tmux session '{self._tmux_session}' 中启动 AI")
            logger.info(f"  → 启动命令: {self._cli_path}")

            # 发送启动 AI 的命令到 tmux session
            # 使用环境变量标记这是启动命令，让 hook 忽略
            cmd = [
                "tmux", "send-keys", "-t", f"{self._tmux_session}:0",
                f"CLAUDE_STARTUP=1 {self._cli_path}"
            ]
            logger.info(f"  → tmux send-keys: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)

            # 发送回车执行
            subprocess.run(
                ["tmux", "send-keys", "-t", f"{self._tmux_session}:0", "C-m"],
                check=True
            )

            # 等待 AI 进程启动
            time.sleep(AI_STARTUP_WAIT_SECONDS)

            logger.info(f"AI 已在 tmux session '{self._tmux_session}' 中启动")
            return True

        except Exception as e:
            logger.error(f"在 tmux session 中启动 AI 失败: {e}", exc_info=True)
            return False

    async def send_command(self, command: str, skip_ensure: bool = False) -> AsyncGenerator[str, None]:
        """
        发送命令到 tmux session 并获取输出

        Args:
            command: 要发送的命令
            skip_ensure: 是否跳过 session 检查（当外部已经检查过时设为 True）

        Yields:
            str: 输出内容
        """
        try:
            # 确保 session 存在且 AI 进程在运行（如果外部没有检查过）
            just_started = False
            if not skip_ensure:
                success, just_started = self._ensure_tmux_session()
                if not success:
                    yield "错误: 无法创建 tmux session"
                    return

                # 如果刚刚启动了 AI 进程，提醒用户并等待更长时间让它初始化
                if just_started:
                    yield "⚠️ 检测到 AI 进程未运行，已自动启动"
                    yield ""
                    # 等待 AI 完全初始化（Claude Code 启动需要更长时间）
                    logger.info("  → 等待 AI 初始化...")
                    time.sleep(MAX_READY_WAIT_SECONDS)

            logger.info(f"发送命令到 tmux session '{self._tmux_session}': {command}")

            # 清空 tmux 历史和屏幕，确保只捕获新命令的输出
            # 1. 清空历史缓冲区
            subprocess.run(
                ["tmux", "clear-history", "-t", f"{self._tmux_session}"],
                capture_output=True
            )
            # 2. 发送 C-l 清除屏幕（终端控制字符，不是输入到程序）
            subprocess.run(
                ["tmux", "send-keys", "-t", f"{self._tmux_session}", "C-l"],
                capture_output=True
            )
            time.sleep(0.5)  # 等待屏幕清空完成

            # 发送命令到 tmux session
            # 先 C-u 清除当前输入行，然后发送命令
            clear_cmd = ["tmux", "send-keys", "-t", f"{self._tmux_session}", "C-u"]
            subprocess.run(clear_cmd, capture_output=True)

            # 发送命令
            send_cmd = [
                "tmux", "send-keys", "-t", f"{self._tmux_session}",
                command
            ]
            subprocess.run(send_cmd, capture_output=True)

            # 发送两个 Enter 提交命令（带延迟确保正确接收）
            # 实测得到，只能人工调整
            for _ in range(2):
                time.sleep(AI_READY_POLL_INTERVAL)
                subprocess.run(["tmux", "send-keys", "-t", f"{self._tmux_session}", "C-m"], capture_output=True)

            # 发送完成后直接返回，不等待输出
            yield f"命令已发送到 AI"

        except Exception as e:
            logger.error(f"发送命令时出错: {e}", exc_info=True)
            yield f"\n执行出错: {str(e)}"

    def _clean_tmux_output(self, output: str) -> str:
        """清理 tmux 输出中的 ANSI 控制字符"""
        output = clean_ansi_codes(output)
        # 移除 tmux 特有的标记
        output = output.replace('\x1b[?2004l', '')
        output = output.replace('\x0f', '')

        # 缩短长分隔线（─────────────────────────────────────────────── 缩短到 1/7）
        import re
        # 匹配连续 20 个以上横线或破折号的行
        output = re.sub(r'^([─\-=━]{20,})$', lambda m: m.group(1)[:len(m.group(1))//7] if len(m.group(1)) > 7 else m.group(1), output, flags=re.MULTILINE)

        # # 前面添加空格（飞书特殊字符转义）
        output = re.sub(r'(?<!\s)#', ' #', output)

        return output.strip()

    def capture_output(
        self,
        callback,
        poll_interval: float = 0.3,
        max_wait: float = 300.0,
    ) -> str:
        """
        捕获 tmux 输出并通过回调发送增量更新

        Args:
            callback: 回调函数，签名: callback(content: str, is_last: bool) -> None
            poll_interval: 轮询间隔（秒）
            max_wait: 最大等待时间（秒）

        Returns:
            str: 完整输出内容
        """
        import time
        import asyncio

        output_lines = []
        last_position = 0
        start_time = time.time()

        logger.info(f"开始捕获 tmux 输出，poll_interval={poll_interval}s, max_wait={max_wait}s")

        # 检查回调是否是异步的
        if asyncio.iscoroutinefunction(callback):
            # 如果是异步回调，使用异步版本
            return asyncio.get_event_loop().run_until_complete(
                self.capture_output_async(callback, poll_interval, max_wait)
            )

        while True:
            elapsed = time.time() - start_time

            # 检查是否超时
            if elapsed > max_wait:
                logger.info(f"捕获超时 ({max_wait}s)，返回已收集的内容")
                break

            # 捕获当前 pane 内容
            try:
                # 使用 -S 0 捕获当前可见内容（不包括历史）
                result = subprocess.run(
                    ["tmux", "capture-pane", "-pS", "0", "-t", f"{self._tmux_session}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0 and result.stdout:
                    current_output = self._clean_tmux_output(result.stdout)

                    # 检查是否有新内容
                    if len(current_output) > last_position:
                        new_content = current_output[last_position:]
                        last_position = len(current_output)

                        # 过滤掉命令本身（如果还在输出中）
                        if new_content.strip():
                            output_lines.append(new_content)
                            # 传递新增内容而不是累积内容
                            callback(new_content, is_last=False)

                # 检查 AI 是否仍在运行（如果进程不在了，说明输出完成）
                if not self._check_ai_running_in_session():
                    logger.info("检测到 AI 进程已结束，停止捕获")
                    break

            except subprocess.TimeoutExpired:
                logger.warning("捕获 pane 超时")
            except Exception as e:
                logger.error(f"捕获输出失败: {e}")

            time.sleep(poll_interval)

        # 发送最终内容（仅当有内容时）
        full_content = '\n'.join(output_lines)
        if full_content.strip():
            callback(full_content, is_last=True)

        return full_content

    async def capture_output_async(
        self,
        callback,
        poll_interval: float = 0.3,
        max_wait: float = 300.0,
        command: str = "",
    ) -> str:
        """
        异步捕获 tmux 输出并通过回调发送增量更新

        Args:
            callback: 异步回调函数，签名: async callback(content: str, is_last: bool) -> None
            poll_interval: 轮询间隔（秒）
            max_wait: 最大等待时间（秒）
            command: 发送的命令（用于检测命令是否完成）

        Returns:
            str: 完整输出内容
        """
        import time
        import asyncio

        output_lines = []
        last_position = 0
        start_time = time.time()
        last_output_time = time.time()  # 上次有新输出的时间

        logger.info(f"开始异步捕获 tmux 输出，poll_interval={poll_interval}s, max_wait={max_wait}s")

        # 注意：tmux 历史和屏幕已在 send_command 中清空，这里不需要再清空

        while True:
            elapsed = time.time() - start_time
            time_since_last_output = time.time() - last_output_time

            # 检查是否超时
            if elapsed > max_wait:
                logger.info(f"捕获超时 ({max_wait}s)，返回已收集的内容")
                break

            # 检查无新输出超时 - 如果一段时间没有新输出，认为 AI 已完成

            # 捕获当前 pane 内容
            had_new_output = False
            current_output = ""

            try:
                # 抓全量：每次都发送当前屏幕的全部内容
                result = await asyncio.create_subprocess_exec(
                    "tmux", "capture-pane", "-pS", "0", "-t", f"{self._tmux_session}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await result.communicate()

                if result.returncode == 0 and stdout:
                    current_output = self._clean_tmux_output(stdout.decode('utf-8'))
                    current_len = len(current_output)

                    if current_output.strip():
                        had_new_output = True
                        last_output_time = time.time()
                        # 发送全量内容
                        await callback(current_output, is_last=False)
                        logger.info(f"捕获长度={current_len}")

            except asyncio.TimeoutExpired:
                logger.warning("捕获 pane 超时")
            except Exception as e:
                logger.error(f"捕获输出失败: {e}")

            # 检查内容是否变化：如果连续 2 次捕获内容相同，认为 AI 已完成
            # 只有当有实际内容时才检查
            if had_new_output and current_output:
                # 标准化内容进行比较（去除首尾空格和多余空白）
                normalized_output = ' '.join(current_output.split())

                if not hasattr(self, '_last_captured_output'):
                    self._last_captured_output = normalized_output
                    self._no_change_count = 0
                elif normalized_output == self._last_captured_output:
                    self._no_change_count += 1
                else:
                    self._no_change_count = 0
                    self._last_captured_output = normalized_output

                # 连续 2 次内容没变化，认为 AI 已完成
                if self._no_change_count >= 2:
                    logger.info(f"连续{self._no_change_count}次内容无变化，AI 已完成，停止捕获")
                    break

            await asyncio.sleep(poll_interval)

        # 发送最终内容（仅当有内容时）
        full_content = '\n'.join(output_lines)
        if full_content.strip():
            await callback(full_content, is_last=True)

        return full_content