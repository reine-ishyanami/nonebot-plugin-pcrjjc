from os.path import join

from pydantic import BaseModel, Extra


class AccountInfo(BaseModel):
    account: str = ""
    password: str = ""
    platform: int = 2
    channel: int = 1

    def __init__(self, account, password, platform, channel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.account = account
        self.password = password
        self.platform = platform
        self.channel = channel


class Config(BaseModel, extra=Extra.ignore):
    """Plugin Config Here"""
    apscheduler_log_level: int = 30
    data_path: str = join("data", "pcrjjc")  # 数据存储目录
    superusers: list[str]  # 超级用户列表，建议只填一个，填多个可能导致后续用户指令失效
    pcrjjc_group: str = None  # 当私聊不可用时，使用指定群聊推送要私聊的消息
    otto: bool = True  # 是否自动过验证码，因自动过码失效，改为手动过码
    version: str = "6.2.0"  # 游戏版本号
    max_pri: int = 0  # 最大私聊人数
    max_pcrid: int = 8  # 每个QQ号绑定的最多数量
    max_history: int = 50  # 每个QQ号保存的最多击剑记录
    notice_cd_min: int = 10  # 上线推送频率
    refresh_second: int = 3  # 刷新频率，可按自身服务器性能输入其他数值，可支持整数、小数
    pcrjjc_accounts: list[AccountInfo] = []  # 登录账号
