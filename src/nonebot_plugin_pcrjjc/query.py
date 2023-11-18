import asyncio
import traceback
import types
from asyncio import Lock
from json import load, loads
from os.path import join
from pathlib import Path

from nonebot import get_driver, logger, on_regex
from nonebot.adapters.onebot.v11 import Bot
from nonebot.params import RegexGroup
from nonebot.permission import SUPERUSER

from .aiorequests import get
from .config import Config, AccountInfo
from .pcrclient import PcrClient, ApiException, BSdkClient

driver = get_driver()
config = Config.parse_obj(driver.config)

bot: Bot | None = None
captcha_lck = Lock()
queue = asyncio.PriorityQueue()
otto = config.otto
pcrjjc_group = config.pcrjjc_group
ordd = 'x'
validate = None
validating = False
ac_first = False
client = None
captcha_cnt = 0
admin = int(config.superusers[0]) if len(config.superusers) > 0 else 0
data_path = config.data_path
path = join(str(Path()), data_path)
ac_info: list[AccountInfo] = []
if config.pcrjjc_accounts:
    ac_info = config.pcrjjc_accounts
binds_info = {}


@driver.on_startup
async def _():
    await load_config()


@driver.on_bot_connect
async def _(b: Bot):
    global bot, ac_info, binds_info
    b.send_admin_msg_of_pcrjjc = types.MethodType(send_admin_msg_of_pcrjjc, b)
    bot = b
    try:
        while i := next(iter(ac_info)):
            b_client = BSdkClient(i, captcha_verifier)
            pcr_client = PcrClient(b_client)
            loop = asyncio.get_event_loop()
            loop.create_task(query(pcr_client))
            if binds_info == {} or binds_info["arena_bind"] == {}:
                loop.create_task(first_login(pcr_client))
            ac_info.remove(i)  # 遍历删除集合元素，防止有第二个bot对象连接时触发登录事件
    except StopIteration:
        pass


async def send_admin_msg_of_pcrjjc(self, user_id: int, group_id: str, message: str):
    if group_id is None:
        await self.send_private_msg(user_id=user_id, message=message)
    else:
        await self.send_group_msg(group_id=int(group_id), message=message)


async def first_login(pcr_client):
    while pcr_client.shouldLogin:
        await pcr_client.login()


async def load_config():
    global ac_info, binds_info, path
    if not ac_info:
        account_json_name = "account.json"
        try:
            with open(join(path, account_json_name)) as fp:
                ac_info_arr = load(fp)
                ac_info = [AccountInfo(acc['account'], acc['password'], acc['platform'], acc['channel']) for acc in
                           ac_info_arr]
        except FileNotFoundError:
            logger.error("请在配置文件中配置PCRJJC_ACCOUNTS字段，具体格式见自述文件")
    binds_json_name = "binds.json"
    try:
        with open(join(path, binds_json_name)) as fp:
            binds_info = load(fp)
    except FileNotFoundError:
        pass


# noinspection PyUnresolvedReferences
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
        message = f'thread{ordd}: Changed to manual'
        await bot.send_admin_msg_of_pcrjjc(user_id=admin, group_id=pcrjjc_group, message=message)
    elif validate == "auto":
        otto = True
        message = f'thread{ordd}: Changed to auto'
        await bot.send_admin_msg_of_pcrjjc(user_id=admin, group_id=pcrjjc_group, message=message)
    try:
        captcha_lck.release()
    except:
        pass


async def captcha_verifier(gt: str, challenge: str, userid: str):
    global otto, captcha_cnt, ac_first, validating, validate, captcha_lck
    if not ac_first:
        await captcha_lck.acquire()
        ac_first = True

    validating = True

    # 非自动过码
    if not otto:
        online_url_head = f"https://help.tencentbot.top/geetest_/?"
        url = f"captcha_type=1&challenge={challenge}&gt={gt}&userid={userid}&gs=1"
        message = f'pcr账号登录需要验证码，请完成以下链接中的验证内容后将第1个方框的内容点击复制，并加上"validate{ordd} "前缀发送给机器人完成验证'
        f'\n示例：validate{ordd} 123456789\n您也可以发送 validate{ordd} auto 命令bot自动过验证码'
        f'\n验证链接头：{online_url_head}'
        f'\n链接：{url}'
        f'\n为避免tx网页安全验证使验证码过期，请手动拼接链接头和链接'
        await bot.send_admin_msg_of_pcrjjc(user_id=admin, group_id=pcrjjc_group, message=message)
        await captcha_lck.acquire()
        validating = False
        return challenge, gt, validate

    while captcha_cnt < 5:
        captcha_cnt += 1
        try:
            logger.info('测试新版自动过码中，当前尝试第{}次。', captcha_cnt)
            url = f"https://pcrd.tencentbot.top/geetest_renew?captcha_type=1&challenge={challenge}&gt={gt}&userid={userid}&gs=1"
            header = {"Content-Type": "application/json", "User-Agent": "pcrjjc/0.2.0"}
            res = await (await get(url=url, headers=header)).content
            res = loads(res)
            uuid = res["uuid"]
            msg = [f"uuid={uuid}"]

            ccnt = 0
            while ccnt < 10:
                ccnt += 1
                await asyncio.sleep(5)
                res = await (await get(url=f"https://pcrd.tencentbot.top/check/{uuid}", headers=header)).content
                res = loads(res)
                if "queue_num" in res:
                    nu = res["queue_num"]
                    msg.append(f"queue_num={nu}")
                    tim = min(int(nu), 3) * 10
                    msg.append(f"sleep={tim}")
                    logger.info("pcrjjc2:{}", msg)
                    msg = []
                else:
                    info = res["info"]
                    if info in ["fail", "url invalid"]:
                        break
                    elif info == "in running":
                        await asyncio.sleep(5)
                    elif 'validate' in info:
                        logger.info('info={}', info)
                        validating = False
                        return info["challenge"], info["gt_user_id"], info["validate"]
                if ccnt > 10:
                    raise Exception("Captcha Failed")
        except:
            pass
    if captcha_cnt >= 5:
        otto = False
        message1 = f'thread{ordd}: 自动过码多次尝试失败，可能为服务器错误，自动切换为手动。\n确实服务器无误后，可发送 validate{ordd} auto重新触发自动过码。'
        message2 = f'thread{ordd}: Changed to manual'
        await bot.send_admin_msg_of_pcrjjc(user_id=admin, group_id=pcrjjc_group, message=message1)
        await bot.send_admin_msg_of_pcrjjc(user_id=admin, group_id=pcrjjc_group, message=message2)
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
