from pydantic import BaseModel, Extra


class Config(BaseModel, extra=Extra.ignore):
    """Plugin Config Here"""
    apscheduler_log_level: int = 30
    data_path: str = "data\\pcrjjc"
    superusers: list[str]
    version: str = "6.2.0"
    max_pri: int = 0  # 最大私聊人数
    max_pcrid: int = 8  # 每个QQ号绑定的最多数量
    max_history: int = 50  # 每个QQ号保存的最多击剑记录
    notice_cd_min: int = 10  # 上线推送频率
    refresh_second: int = 3  # 刷新频率，可按自身服务器性能输入其他数值，可支持整数、小数
