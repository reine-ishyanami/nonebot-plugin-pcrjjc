import asyncio
import os.path
import traceback
from asyncio import Lock
from json import load, loads, dump
from os.path import join
from pathlib import Path

from nonebot import get_driver, logger, on_regex
from nonebot.adapters.onebot.v11 import Bot
from nonebot.params import RegexGroup
from nonebot.permission import SUPERUSER

from .aiorequests import get
from .config import Config
from .pcrclient import PcrClient, ApiException, BSdkClient

driver = get_driver()
config = Config.parse_obj(driver.config)

bot: Bot | None = None
captcha_lck = Lock()
queue = asyncio.PriorityQueue()
otto = config.otto
ordd = 'x'
validate = None
validating = False
ac_first = False
client = None
captcha_cnt = 0
admin = int(config.superusers[0]) if len(config.superusers) > 0 else 0
data_path = config.data_path
path = join(str(Path()), data_path)
ac_info = []
binds_info = {}
account_json_template = [
    {
        "account": "account1",
        "password": "password",
        "platform": 2,
        "channel": 1
    },
    {
        "account": "account2",
        "password": "password",
        "platform": 2,
        "channel": 1
    }
]


@driver.on_startup
async def _():
    await load_config()


@driver.on_bot_connect
async def _(b: Bot):
    global bot, ac_info, binds_info
    bot = b
    try:
        while i := ac_info.__iter__().__next__():
            b_client = BSdkClient(i, captcha_verifier)
            pcr_client = PcrClient(b_client)
            loop = asyncio.get_event_loop()
            loop.create_task(query(pcr_client))
            if binds_info == {} or binds_info["arena_bind"] == {}:
                loop.create_task(first_login(pcr_client))
            ac_info.remove(i)  # 遍历删除集合元素，防止有第二个bot对象连接时触发登录事件
    except StopIteration:
        pass


async def first_login(pcr_client):
    while pcr_client.shouldLogin:
        await pcr_client.login()


async def load_config():
    global ac_info, binds_info, path, account_json_template
    account_json_name = "account.json"
    binds_json_name = "binds.json"
    try:
        with open(join(path, account_json_name)) as fp:
            ac_info = load(fp)
    except FileNotFoundError:
        if not os.path.exists(path):
            os.makedirs(path)
        with open(join(path, account_json_name), 'w') as fp:
            dump(account_json_template, fp, indent=4)
        logger.info("未发现路径下存在{}文件，已自动生成", account_json_name)
        logger.info("路径为:{}", path)
        logger.info("请修改account和password字段，可添加多个")
    try:
        with open(join(path, binds_json_name)) as fp:
            binds_info = load(fp)
    except FileNotFoundError:
        pass


@driver.on_shutdown
async def _():
    # 清空队列中的任务
    global queue
    while not queue.empty():
        await queue.get()
        queue.task_done()
    queue = None


@on_regex(pattern=rf'^validate{ordd} ?(\S+)$', permission=SUPERUSER).handle()
async def validate(group: tuple = RegexGroup()):
    global validate, captcha_lck, otto
    validate = group[0]
    if validate == "manual":
        otto = False
        await bot.send_private_msg(user_id=admin, message=f'thread{ordd}: Changed to manual')
    elif validate == "auto":
        otto = True
        await bot.send_private_msg(user_id=admin, message=f'thread{ordd}: Changed to auto')
    try:
        captcha_lck.release()
    except:
        pass


async def captcha_verifier(*args):
    global otto
    if len(args) == 0:
        return otto
    global captcha_cnt
    if len(args) == 1 and type(args[0]) == int:
        captcha_cnt = args[0]
        return captcha_cnt

    global ac_first, validating
    global validate, captcha_lck
    if not ac_first:
        await captcha_lck.acquire()
        ac_first = True

    validating = True
    if not otto:
        gt = args[0]
        challenge = args[1]
        userid = args[2]
        online_url_head = f"https://help.tencentbot.top/geetest_/?"
        url = f"captcha_type=1&challenge={challenge}&gt={gt}&userid={userid}&gs=1"
        await bot.send_private_msg(
            user_id=admin,
            message=f'pcr账号登录需要验证码，请完成以下链接中的验证内容后将第1个方框的内容点击复制，并加上"validate{ordd} "前缀发送给机器人完成验证'
                    f'\n示例：validate{ordd} 123456789\n您也可以发送 validate{ordd} auto 命令bot自动过验证码'
                    f'\n验证链接头：{online_url_head}'
                    f'\n链接：{url}'
                    f'\n为避免tx网页安全验证使验证码过期，请手动拼接链接头和链接'
        )
        await captcha_lck.acquire()
        validating = False
        return validate

    while captcha_cnt < 5:
        captcha_cnt += 1
        try:
            logger.info('测试新版自动过码中，当前尝试第{}次。', captcha_cnt)

            await asyncio.sleep(1)
            uuid = loads(await (await get(url="https://pcrd.tencentbot.top/geetest")).content)["uuid"]
            logger.info('uuid={}', uuid)

            ccnt = 0
            while ccnt < 3:
                ccnt += 1
                await asyncio.sleep(5)
                res = await (await get(url=f"https://pcrd.tencentbot.top/check/{uuid}")).content
                res = loads(res)
                if "queue_num" in res:
                    nu = res["queue_num"]
                    logger.info("queue_num={}", nu)
                    tim = min(int(nu), 3) * 5
                    logger.info("sleep={}", tim)
                    await asyncio.sleep(tim)
                else:
                    info = res["info"]
                    if info in ["fail", "url invalid"]:
                        break
                    elif info == "in running":
                        await asyncio.sleep(5)
                    else:
                        logger.info('info={}', info)
                        validating = False
                        return info
        except:
            pass

    if captcha_cnt >= 5:
        otto = False
        await bot.send_private_msg(user_id=admin,
                                   message=f'thread{ordd}: 自动过码多次尝试失败，可能为服务器错误，自动切换为手动。\n确实服务器无误后，可发送 validate{ordd} auto重新触发自动过码。')
        await bot.send_private_msg(user_id=admin, message=f'thread{ordd}: Changed to manual')
        validating = False
        return "manual"

    logger.info("captchaVerifier: uncaught exception")
    validating = False
    return False


async def query(pcr_client):
    while True:
        if queue is None:
            break
        try:
            DA = await queue.get()
            data = DA[1]
        except:
            await asyncio.sleep(1)
            continue
        try:
            if validating:
                await asyncio.sleep(1)
                raise ApiException('账号被风控，请联系管理员输入验证码并重新登录', -1)
            while pcr_client.shouldLogin:
                await pcr_client.login()
            res = (await pcr_client.callapi('/profile/get_profile', {'target_viewer_id': int(data[1])}))
            if 'user_info' not in res:  # 失败重连
                await pcr_client.login()
                res = (await pcr_client.callapi('/profile/get_profile', {'target_viewer_id': int(data[1])}))
            data[2]["res"] = res
            await data[0](data[2])
        except:
            traceback.print_exc()
        finally:
            if queue is not None:
                queue.task_done()
