from nonebot.plugin import PluginMetadata

from .config import Config

from .main import *  # noqa: F403

__plugin_meta__ = PluginMetadata(
    name="pcrjjc",
    config=Config,
    description="公主连结（国服）排名监测工具",
    usage="发送 竞技场帮助 获取详细使用说明",
    type="application",
    homepage="https://github.com/reine-ishyanami/nonebot-plugin-pcrjjc",
    supported_adapters={"~onebot.v11"}
)

