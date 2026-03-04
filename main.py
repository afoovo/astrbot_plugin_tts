from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig

from .core.config import PluginConfig
from .core.sender import VoiceSender
from .core.tts_converter import TTSConverter


class TTSPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.cfg = PluginConfig(config, context)

    async def initialize(self):
        """插件初始化"""
        # 初始化TTS转换器
        self.tts_converter = TTSConverter(self.cfg)

        # 初始化语音发送器
        self.voice_sender = VoiceSender()

    async def terminate(self):
        """插件卸载"""
        # 关闭TTS转换器
        if hasattr(self, 'tts_converter'):
            await self.tts_converter.close()

    @filter.command("语音转换")
    async def text_to_speech(self, event: AstrMessageEvent, text: str):
        """语音转换 <文本> - 将文本直接转换为语音"""
        try:
            # 调用TTS转换器
            result = await self.tts_converter.convert_text_to_audio(text)
            
            # 检查转换结果状态
            if result.status != "completed":
                logger.error(f"TTS转换失败: {result.error_message or '未知错误'}")
                event.stop_event()
                return

            # 发送TTS音频
            send_success = await self.voice_sender.send_tts_audio(event, result)
            if not send_success:
                logger.error("TTS音频发送失败")
        except ValueError as e:
            logger.error(f"TTS参数错误: {e}")
        except Exception as e:
            logger.error(f"TTS转换异常: {e}")

        event.stop_event()

    @filter.command("语音回复")
    async def text_to_speech_with_llm(self, event: AstrMessageEvent, text: str):
        """语音回复 <文本> - 获取大模型回复并转换为语音"""
        try:
            # 获取第一个可用的 Provider
            all_providers = self.context.get_all_providers()
            if not all_providers or len(all_providers) == 0:
                logger.error("没有可用的LLM Provider")
                event.stop_event()
                return
            
            provider = all_providers[0]
            provider_id = provider.meta().id

            # 调用llm_generate方法获取回复
            llm_response = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=text,
            )

            # 获取回复文本
            reply_text = llm_response.completion_text
            
            if not reply_text:
                logger.error("LLM返回的回复文本为空")
                event.stop_event()
                return

            # 调用TTS转换器将回复转换为语音
            result = await self.tts_converter.convert_text_to_audio(reply_text)
            
            # 检查转换结果状态
            if result.status != "completed":
                logger.error(f"TTS转换失败: {result.error_message or '未知错误'}")
                event.stop_event()
                return

            # 发送TTS音频
            send_success = await self.voice_sender.send_tts_audio(event, result)
            if not send_success:
                logger.error("TTS音频发送失败")
        except ValueError as e:
            logger.error(f"TTS参数错误: {e}")
        except Exception as e:
            logger.error(f"TTS转换异常: {e}")

        # 停止事件传播，避免重复处理
        event.stop_event()
