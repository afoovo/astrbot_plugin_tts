from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class TTSResult:
    """TTS转换结果数据模型"""
    id: str
    """转换结果ID"""

    ref_audio_path: str
    """参考音频路径"""

    status: str
    """状态：pending/processing/completed/failed"""

    audio_url: str | None = None
    """音频URL"""

    audio_path: str | None = None
    """音频文件路径"""

    text: str | None = None
    """转换的文本内容"""

    created_at: datetime | None = None
    """创建时间"""

    completed_at: datetime | None = None
    """完成时间"""

    error_message: str | None = None
    """错误信息"""
