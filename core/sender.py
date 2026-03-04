from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.core.message.components import Record

from .model import TTSResult


class VoiceSender:
    """语音发送器，包含TTS语音发送功能"""

    def __init__(self):
        """初始化语音发送器"""
        pass

    async def send_tts_audio(
        self,
        event: AstrMessageEvent,
        result: TTSResult
    ) -> bool:
        """发送TTS音频

        Args:
            event: 消息事件
            result: TTS转换结果数据模型

        Returns:
            bool: 是否发送成功
        """
        if result.status != "completed":
            logger.info(f"TTS转换失败: {result.error_message or '未知错误'}")
            return False

        if not result.audio_path:
            logger.info("音频文件不存在")
            return False

        try:
            logger.debug(f"正在发送音频: {result.audio_path}")

            # 使用Record组件发送音频
            seg = Record.fromFileSystem(result.audio_path)
            await event.send(event.chain_result([seg]))
            return True
        except Exception as e:
            logger.error(f"音频发送失败: {e}")
            return False
