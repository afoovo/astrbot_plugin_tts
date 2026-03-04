import aiohttp
import hashlib
from datetime import datetime
from pathlib import Path

from astrbot.api import logger

from .config import PluginConfig
from .model import TTSResult


class TTSConverter:
    """TTS转换器，负责将文本转换为语音"""

    def __init__(self, config: PluginConfig):
        self.cfg = config
        self.session = aiohttp.ClientSession()
        # 使用插件数据目录下的tts子目录
        self.tts_dir = self.cfg.tts_dir
        self.tts_dir.mkdir(parents=True, exist_ok=True)

    async def close(self):
        """关闭HTTP会话"""
        await self.session.close()

    def _generate_cache_key(self, text: str, ref_audio_path: str) -> str:
        """生成缓存键，包含文本和参考音频参数"""
        content = f"{text}_{ref_audio_path}"
        return hashlib.md5(content.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        # 内部设置音频格式为wav
        return self.tts_dir / f"{cache_key}.wav"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """检查缓存是否有效"""
        if not cache_path.exists():
            return False

        # 内部设置缓存时长为7天
        cache_duration = 7 * 24 * 60 * 60  # 7天
        file_time = cache_path.stat().st_mtime
        current_time = datetime.now().timestamp()
        if current_time - file_time > cache_duration:
            return False

        return True

    async def convert_text_to_audio(self, text: str) -> TTSResult:
        """转换文本为音频

        Args:
            text: 待合成文本

        Returns:
            TTSResult: TTS转换结果数据模型
        """
        # TODO:内置所有TTS请求参数，后续加入配置或自动管理
        ref_audio_path = self.cfg.get_ref_audio_path()  # 参考音频路径
        prompt_text = self.cfg.prompt_text  # 参考音频对应的文本
        prompt_lang = "zh"  # 参考音频语种
        text_lang = "zh"  # 待合成文本语种
        text_split_method = "cut5"
        batch_size = 1
        media_type = "wav"
        streaming_mode = "False"
        top_k = 5
        top_p = 1.0
        temperature = 1.0
        speed_factor = 1.0
        fragment_interval = 0.3
        seed = -1
        parallel_infer = "True"
        repetition_penalty = 1.35
        sample_steps = 32
        super_sampling = "False"

        # 参数校验
        if not self.cfg.tts_enabled:
            raise ValueError("TTS功能未启用")
        if not self.cfg.tts_api_url:
            raise ValueError("TTS API地址未配置")
        if len(text) > 200:
            raise ValueError("文本过长，最多支持200个字符")
        if not ref_audio_path:
            raise ValueError("参考音频文件不存在，请上传音频文件或确保默认音频文件存在")

        # 生成缓存键
        cache_key = self._generate_cache_key(text, ref_audio_path)
        cache_path = self._get_cache_path(cache_key)

        # 检查缓存
        if self._is_cache_valid(cache_path):
            logger.info(f"使用缓存: {cache_path}")
            return TTSResult(
                id=cache_key,
                ref_audio_path=ref_audio_path,
                status="completed",
                audio_path=str(cache_path),
                text=text,
                created_at=datetime.fromtimestamp(cache_path.stat().st_mtime),
                completed_at=datetime.fromtimestamp(cache_path.stat().st_mtime)
            )

        # 创建TTSResult对象
        tts_result = TTSResult(
            id=cache_key,
            ref_audio_path=ref_audio_path,
            status="processing",
            text=text,
            created_at=datetime.now()
        )

        try:
            # 构建请求参数
            params = {
                "text": text,
                "text_lang": text_lang,
                "ref_audio_path": ref_audio_path,
                "prompt_text": prompt_text,
                "prompt_lang": prompt_lang,
                "text_split_method": text_split_method,
                "batch_size": batch_size,
                "media_type": media_type,
                "streaming_mode": streaming_mode,
                "top_k": top_k,
                "top_p": top_p,
                "temperature": temperature,
                "speed_factor": speed_factor,
                "fragment_interval": fragment_interval,
                "seed": seed,
                "parallel_infer": parallel_infer,
                "repetition_penalty": repetition_penalty,
                "sample_steps": sample_steps,
                "super_sampling": super_sampling,
            }

            # 调用TTS API
            api_url = f"{self.cfg.tts_api_url}/tts"
            headers = {}

            logger.info(f"调用TTS API: {api_url}")

            async with self.session.get(api_url, params=params, headers=headers) as response:
                if response.status == 200:
                    # 保存音频文件
                    with open(cache_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)

                    # 更新TTSResult状态
                    tts_result.status = "completed"
                    tts_result.audio_path = str(cache_path)
                    tts_result.completed_at = datetime.now()

                    logger.info(f"TTS转换成功: {cache_path}")
                else:
                    # 处理错误响应
                    error_text = await response.text()
                    logger.error(f"TTS API错误: HTTP {response.status}, {error_text}")

                    tts_result.status = "failed"
                    tts_result.error_message = f"TTS API错误: HTTP {response.status}"
        except Exception as e:
            logger.error(f"TTS转换异常: {e}")
            tts_result.status = "failed"
            tts_result.error_message = str(e)

        return tts_result
