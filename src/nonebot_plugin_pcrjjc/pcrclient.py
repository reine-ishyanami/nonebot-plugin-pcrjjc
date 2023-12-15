from asyncio import sleep
from base64 import b64encode, b64decode
from datetime import datetime
from hashlib import md5
from json import loads
from os.path import join, exists
from pathlib import Path
from random import randint
from re import search

from Crypto.Cipher import AES
from dateutil.parser import parse
from msgpack import packb, unpackb
from nonebot import logger, get_driver

from .aiorequests import post
from .bsgamesdk import login
from .config import Config

driver = get_driver()
config = Config.parse_obj(driver.config)

api_root = 'https://le1-prod-all-gs-gzlj.bilibiligame.net'
debugging = 1

data_path = config.data_path
path = join(str(Path()), data_path)
version_txt = join(path, 'version.txt')
version = config.version

if exists(version_txt):
    with open(version_txt, encoding='utf-8') as fp:
        version = fp.read().strip()

defaultHeaders = {
    'Accept-Encoding': 'gzip',
    'User-Agent': 'Dalvik/2.1.0 (Linux, U, Android 5.1.1, PCRT00 Build/LMY48Z)',
    'X-Unity-Version': '2018.4.30f1',
    'APP-VER': version,
    'BATTLE-LOGIC-VERSION': '4',
    'BUNDLE-VER': '',
    'DEVICE': '2',
    'DEVICE-ID': '7b1703a5d9b394e24051d7a5d4818f17',
    'DEVICE-NAME': 'OPPO PCRT00',
    'EXCEL-VER': '1.0.0',
    'GRAPHICS-DEVICE-NAME': 'Adreno (TM) 640',
    'IP-ADDRESS': '10.0.2.15',
    'KEYCHAIN': '',
    'LOCALE': 'CN',
    'PLATFORM-OS-VERSION': 'Android OS 5.1.1 / API-22 (LMY48Z/rel.se.infra.20200612.100533)',
    'REGION-CODE': '',
    'RES-KEY': 'ab00a0a6dd915a052a2ef7fd649083e5',
    'RES-VER': '10002200',
    'SHORT-UDID': '0'
}


class ApiException(Exception):

    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


class BSdkClient:
    '''
        acccountinfo = {
            'account': '',
            'password': '',
            'platform': 2, # indicates android platform
            'channel': 1, # indicates bilibili channel
        }
    '''

    def __init__(self, account_info, captcha_verifier):
        self.account = account_info.account
        self.pwd = account_info.password
        self.platform = account_info.platform
        self.channel = account_info.channel
        self.captcha_verifier = captcha_verifier

    async def login(self):
        while True:
            resp = await login(self.account, self.pwd, self.captcha_verifier)
            if resp['code'] == 0:
                logger.info("geetest or captcha succeed")
                break
            logger.info(resp['message'])
            if str(resp['message']) == "用户名或密码错误":
                raise Exception("用户名或密码错误")

        return resp['uid'], resp['access_key']


class PcrClient:

    def __init__(self, bs_client: BSdkClient):
        self.viewer_id = 0
        self.b_sdk = bs_client

        self.headers = {}
        for key in defaultHeaders.keys():
            self.headers[key] = defaultHeaders[key]

        self.shouldLogin = True
        self.shouldLoginB = True

    async def bili_login(self):
        self.uid, self.access_key = await self.b_sdk.login()
        self.platform = self.b_sdk.platform
        self.channel = self.b_sdk.channel
        self.headers['PLATFORM'] = str(self.platform)
        self.headers['PLATFORM-ID'] = str(self.platform)
        self.headers['CHANNEL-ID'] = str(self.channel)
        self.shouldLoginB = False

    @staticmethod
    def create_key() -> bytes:
        return bytes([ord('0123456789abcdef'[randint(0, 15)]) for _ in range(32)])

    @staticmethod
    def add_to_16(b: bytes) -> bytes:
        n = len(b) % 16
        n = n // 16 * 16 - n + 16
        return b + (n * bytes([n]))

    @staticmethod
    def pack(data: object, key: bytes) -> bytes:
        aes = AES.new(key, AES.MODE_CBC, b'ha4nBYA2APUD6Uv1')
        return aes.encrypt(PcrClient.add_to_16(packb(data, use_bin_type=False))) + key

    @staticmethod
    def encrypt(data: str, key: bytes) -> bytes:
        aes = AES.new(key, AES.MODE_CBC, b'ha4nBYA2APUD6Uv1')
        return aes.encrypt(PcrClient.add_to_16(data.encode('utf8'))) + key

    @staticmethod
    def decrypt(data: bytes):
        data = b64decode(data.decode('utf8'))
        aes = AES.new(data[-32:], AES.MODE_CBC, b'ha4nBYA2APUD6Uv1')
        return aes.decrypt(data[:-32]), data[-32:]

    @staticmethod
    def unpack(data: bytes):
        data = b64decode(data.decode('utf8'))
        aes = AES.new(data[-32:], AES.MODE_CBC, b'ha4nBYA2APUD6Uv1')
        dec = aes.decrypt(data[:-32])
        return unpackb(dec[:-dec[-1]], strict_map_key=False), data[-32:]

    async def callapi(self, api_url: str, request: dict, crypte: bool = True, noerr: bool = True):
        # 按api_url创建json文件 保存api_url request data_headers data
        key = PcrClient.create_key()

        try:
            if self.viewer_id is not None:
                request['viewer_id'] = b64encode(PcrClient.encrypt(
                    str(self.viewer_id), key)) if crypte else str(self.viewer_id)

            response = await (await post(api_root + api_url,
                                         data=PcrClient.pack(request, key) if crypte else str(request).encode('utf8'),
                                         headers=self.headers, timeout=10)).content

            response = PcrClient.unpack(
                response)[0] if crypte else loads(response)

            data_headers = response['data_headers']
            if "/check/game_start" == api_url and "store_url" in data_headers:
                global version
                import re
                pattern = re.compile(r"\d\.\d\.\d")
                version = pattern.findall(data_headers["store_url"])[0]

                defaultHeaders['APP-VER'] = version
                self.headers['APP-VER'] = version
                with open(version_txt, "w", encoding='utf-8') as fp:
                    print(version, file=fp)

            # logger.debug("data_headers\ntype={}\n{}", type(data_headers), data_headers)

            if 'sid' in data_headers and data_headers["sid"] != '':
                t = md5()
                t.update((data_headers['sid'] + 'c!SID!n').encode('utf8'))
                self.headers['SID'] = t.hexdigest()

            if 'request_id' in data_headers:
                self.headers['REQUEST-ID'] = data_headers['request_id']

            if 'viewer_id' in data_headers:
                self.viewer_id = data_headers['viewer_id']

            data = response['data']

            if not noerr and 'server_error' in data:
                data = data['server_error']
                logger.info('pcrclient: {} api failed {}', api_url, data)
                raise ApiException(data['message'], data['status'])

            # logger.debug('pcrclient: {} api called', api_url)
            return data
        except:
            self.shouldLogin = True
            raise

    async def login(self):
        if self.shouldLoginB:
            await self.bili_login()

        if 'REQUEST-ID' in self.headers:
            self.headers.pop('REQUEST-ID')

        while True:
            manifest = await self.callapi('/source_ini/get_maintenance_status?format=json', {}, False, noerr=True)
            if 'maintenance_message' not in manifest:
                break

            try:
                match = search('\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d',
                               manifest['maintenance_message']).group()
                end = parse(match)
                logger.info('server is in maintenance until {}', match)
                while datetime.now() < end:
                    await sleep(1)
            except:
                logger.info('server is in maintenance. waiting for 60 secs')
                await sleep(60)

        ver = manifest['required_manifest_ver']
        logger.info('using manifest ver = {}', ver)
        self.headers['MANIFEST-VER'] = str(ver)
        l_res = await self.callapi('/tool/sdk_login',
                                   {'uid': str(self.uid), 'access_key': self.access_key, 'channel': str(self.channel),
                                    'platform': str(self.platform)})
        if 'is_risk' in l_res and l_res['is_risk'] == 1:
            self.shouldLoginB = True
            return

        gamestart = await self.callapi('/check/game_start',
                                       {'apptype': 0, 'campaign_data': '', 'campaign_user': randint(0, 99999)})

        try:
            if not gamestart['now_tutorial']:
                raise Exception("该账号没过完教程!")
        except:
            pass

        load_index = await self.callapi('/load/index', {'carrier': 'OPPO'})
        home_index = await self.callapi('/home/index',
                                        {'message_id': 1, 'tips_id_list': [], 'is_first': 1, 'gold_history': 0})

        self.shouldLogin = False
        return load_index, home_index
