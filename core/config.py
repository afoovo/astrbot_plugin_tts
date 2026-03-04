from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from pathlib import Path
from types import MappingProxyType, UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.star.context import Context
from astrbot.core.star.star_tools import StarTools
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_path


class ConfigNode:
    """
    配置节点, 把 dict 变成强类型对象。

    规则：
    - schema 来自子类类型注解
    - 声明字段：读写，写回底层 dict
    - 未声明字段和下划线字段：仅挂载属性，不写回
    - 支持 ConfigNode 多层嵌套（lazy + cache）
    """

    _SCHEMA_CACHE: dict[type, dict[str, type]] = {}
    _FIELDS_CACHE: dict[type, set[str]] = {}

    @classmethod
    def _schema(cls) -> dict[str, type]:
        return cls._SCHEMA_CACHE.setdefault(cls, get_type_hints(cls))

    @classmethod
    def _fields(cls) -> set[str]:
        return cls._FIELDS_CACHE.setdefault(
            cls,
            {k for k in cls._schema() if not k.startswith("_")},
        )

    @staticmethod
    def _is_optional(tp: type) -> bool:
        if get_origin(tp) in (Union, UnionType):
            return type(None) in get_args(tp)
        return False

    def __init__(self, data: MutableMapping[str, Any]):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_children", {})
        for key, tp in self._schema().items():
            if key.startswith("_"):
                continue
            if key in data:
                continue
            if hasattr(self.__class__, key):
                continue
            if self._is_optional(tp):
                continue
            logger.warning(f"[config:{self.__class__.__name__}] 缺少字段: {key}")

    def __getattr__(self, key: str) -> Any:
        if key in self._fields():
            value = self._data.get(key)
            tp = self._schema().get(key)

            if isinstance(tp, type) and issubclass(tp, ConfigNode):
                children: dict[str, ConfigNode] = self.__dict__["_children"]
                if key not in children:
                    if not isinstance(value, MutableMapping):
                        raise TypeError(
                            f"[config:{self.__class__.__name__}] "
                            f"字段 {key} 期望 dict，实际是 {type(value).__name__}"
                        )
                    children[key] = tp(value)
                return children[key]

            return value

        if key in self.__dict__:
            return self.__dict__[key]

        raise AttributeError(key)

    def __setattr__(self, key: str, value: Any) -> None:
        if key in self._fields():
            self._data[key] = value
            return
        object.__setattr__(self, key, value)

    def raw_data(self) -> Mapping[str, Any]:
        """
        底层配置 dict 的只读视图
        """
        return MappingProxyType(self._data)

    def save_config(self) -> None:
        """
        保存配置到磁盘（仅允许在根节点调用）
        """
        if not isinstance(self._data, AstrBotConfig):
            raise RuntimeError(
                f"{self.__class__.__name__}.save_config() 只能在根配置节点上调用"
            )
        self._data.save_config()


class PluginConfig(ConfigNode):
    tts_enabled: bool
    tts_api_url: str
    ref_audio_path: list
    prompt_text: str

    def __init__(self, config: AstrBotConfig, context: Context):
        super().__init__(config)
        self.context = context

        self.data_dir = StarTools.get_data_dir("astrbot_plugin_tts")
        self.tts_dir = self.data_dir / "tts"
        self.tts_dir.mkdir(parents=True, exist_ok=True)

        # 添加插件目录属性
        # 从 core/config.py 向上两级到达插件根目录
        self.plugin_dir = Path(__file__).parent.parent

    def get_ref_audio_path(self) -> str:
        """获取参考音频文件的完整路径
        
        Returns:
            str: 参考音频文件的完整路径
        """
        # 默认音频文件路径
        default_audio = self.plugin_dir / "zh_vo_Main_Linaxita_2_4_3_8.wav"
        
        # 如果用户上传了文件
        if self.ref_audio_path and len(self.ref_audio_path) > 0:
            # 获取第一个上传的文件名
            uploaded_file = self.ref_audio_path[0]
            
            # 构建完整路径：data/plugin_data/astrbot_plugin_tts/files/ref_audio_path/
            file_path = self.data_dir / "files" / "ref_audio_path" / uploaded_file
            
            # 检查文件是否存在
            if file_path.exists():
                logger.info(f"使用用户上传的参考音频: {file_path}")
                return str(file_path)
            else:
                logger.warning(f"用户上传的参考音频文件不存在: {file_path}，将使用默认音频")
        
        # 使用默认音频文件
        if default_audio.exists():
            logger.info(f"使用默认参考音频: {default_audio}")
            return str(default_audio)
        else:
            logger.error(f"默认参考音频文件不存在: {default_audio}")
            return ""
