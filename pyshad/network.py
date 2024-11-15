import asyncio
import aiohttp
import rubpy
import aiofiles
import json
import os
from .crypto import Crypto
from . import exceptions
from .types import Results

def capitalize(text: str):
    return ''.join([c.title() for c in text.split('_')])

class Network:
    HEADERS = {'user-agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko)'
                              'Chrome/102.0.0.0 Safari/537.36'),
            	'origin': 'https://web.shad.ir',
            	'referer': 'https://web.shad.ir/',
                'connection': 'keep-alive',
                }

    def __init__(self, client: "rubpy.Client") -> None:
        self.client = client
        connector = aiohttp.TCPConnector(verify_ssl=False)
        self.json_decoder = json.JSONDecoder().decode
        self.json_encoder = json.JSONEncoder().encode
        self.session = aiohttp.ClientSession(
            connector=connector,
            headers=self.HEADERS,
            timeout=aiohttp.ClientTimeout(client.timeout),
        )

        if client.bot_token is not None:
            self.bot_api_url = f'https://messengerg2b1.iranlms.ir/v3/{client.bot_token}/'

        self.api_url = None
        self.wss_url = None

    async def close(self):
        await self.session.close()

    async def get_dcs(self):
        try_count = 0

        while True:
            try:
                async with self.session.get("https://shgetdcmess.iranlms.ir/", verify_ssl=False) as response:
                    if not response.ok:
                        continue

                    response = (await response.json()).get('data')

                self.api_url = response.get('API').get(response.get('default_api')) + '/'
                self.wss_url = response.get('socket').get(response.get('default_socket'))
                return True

            except aiohttp.ServerTimeoutError:
                try_count += 1
                print(f'Server timeout error ({try_count})')
                await asyncio.sleep(try_count)
                continue

            except aiohttp.ClientConnectionError:
                try_count += 1
                print(f'Client connection error ({try_count})')
                await asyncio.sleep(try_count)
                continue

    async def request(self, url: str, data: dict):
        if not isinstance(data, str):
            data = self.json_encoder(data)

        if isinstance(data, str):
            data = data.encode('utf-8')

        for _ in range(3):
            try:
                async with self.session.post(url=url, data=data, verify_ssl=False) as response:
                    if response.ok:
                        return self.json_decoder(await response.text())

            except aiohttp.ServerTimeoutError:
                print('Rubika server timeout error, try again ({})'.format(_))

            except aiohttp.ClientError:
                print('Client error, try again ({})'.format(_))

            except Exception as err:
                print('Unknown Error:', err, '{}'.format(_))

    async def send(self, **kwargs):
        api_version: str = str(kwargs.get('api_version', self.client.API_VERSION))
        auth: str = kwargs.get('auth', self.client.auth)
        client: dict = kwargs.get('client', self.client.DEFAULT_PLATFORM)
        input: dict = kwargs.get('input', {})
        method: str = kwargs.get('method', 'getUserInfo')
        encrypt: bool = kwargs.get('encrypt', True)
        tmp_session: bool = kwargs.get('tmp_session', False)
        url: str = kwargs.get('url', self.api_url)

        data = dict(
            api_version=api_version,
        )
        if not self.client.decode_auth:
            self.client.decode_auth = Crypto.decode_auth(auth)
        if tmp_session:
            data['tmp_session'] = auth
        else:
            data['auth'] = self.client.decode_auth
        if api_version == '6':
            data_enc = dict(
                client=client,
                method=method,
                input=input,
            )

            if encrypt is True:
                data['data_enc'] = Crypto.encrypt(data_enc, key=self.client.key)

            if tmp_session is False:
                data['sign'] = Crypto.makeSignFromData(private_key=self.client.private_key, data_enc=data['data_enc'])
            return await self.request(url, data=data)

        elif api_version == '0':
            data['auth'] = auth
            data['client'] = client
            data['data'] = input
            data['method'] = method

        elif api_version == '4':
            data['client'] = client
            data['method'] = method

        if api_version == 'bot':
            return await self.request(
                url=self.bot_api_url + method,
                data=input,
            )


        return await self.request(url, data=data)

    async def update_handler(self, update: dict):
        if isinstance(update, str):
            update: dict = self.json_decoder(update)

        data_enc: str = update.get('data_enc')

        if data_enc:
            result = Crypto.decrypt(data_enc, key=self.client.key)
            user_guid = result.pop('user_guid')

            async def complete(name, package):
                if not isinstance(package, list):
                    return

                for update in package:
                    update['client'] = self.client
                    update['user_guid'] = user_guid

                for func, handler in self.client.handlers.items():
                    try:
                        # if handler is empty filters
                        if isinstance(handler, type):
                            handler = handler()

                        if handler.__name__ != capitalize(name):
                            return

                        # analyze handlers
                        if not await handler(update=update):
                            return

                        asyncio.create_task(func(handler))

                    except exceptions.StopHandler:
                        break

                    except Exception:
                        pass

            for name, package in result.items():
                asyncio.create_task(complete(name, package))
                        # self._client._logger.error(
                        #     'handler raised an exception', extra={'data': update}, exc_info=True)

    async def get_updates(self):
        while True:
            try:
                async with self.session.ws_connect(self.wss_url, verify_ssl=False, heartbeat=30) as ws:
                    await self.send_json_to_ws(ws)
                    asyncio.create_task(self.send_json_to_ws(ws, data=True))

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            asyncio.create_task(self.update_handler(msg.data))
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            break
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            break

            except aiohttp.ClientError:
                continue

            except Exception:
                continue

    async def send_json_to_ws(self, ws: aiohttp.ClientWebSocketResponse, data=False):
        if data:
            while True:
                try:
                    await asyncio.sleep(10)
                    await ws.send_json({})
                    await self.client.get_chats_updates()
                except:
                    pass

        return await ws.send_json(dict(
            method='handShake',
            auth=self.client.auth,
            api_version='5',
            data='',
        ))

    async def upload_file(self, file, mime: str = None, file_name: str = None, chunk: int = 1048576 * 2,
                          callback=None, *args, **kwargs):
        if isinstance(file, str):
            if not os.path.exists(file):
                raise ValueError('file not found in the given path')

            if file_name is None:
                file_name = os.path.basename(file)

            async with aiofiles.open(file, 'rb') as file:
                file = await file.read()

        elif not isinstance(file, bytes):
            raise TypeError('file arg value must be file path or bytes')

        if file_name is None:
            raise ValueError('the file_name is not set')

        if mime is None:
            mime = file_name.split('.')[-1]

        result = await self.client.request_send_file(file_name, len(file), mime)

        id = result.id
        index = 0
        dc_id = result.dc_id
        total = int(len(file) / chunk + 1)
        upload_url = result.upload_url
        access_hash_send = result.access_hash_send

        while index < total:
            data = file[index * chunk: index * chunk + chunk]
            try:
                result = await self.session.post(
                        upload_url,
                        headers={
                            'auth': self.client.auth,
                            'file-id': id,
                            'total-part': str(total),
                            'part-number': str(index + 1),
                            'chunk-size': str(len(data)),
                            'access-hash-send': access_hash_send
                        },
                        data=data
                    )
                result = await result.json()

                if result.get('status') != 'OK':
                    raise exceptions.UploadError(result.get('status'),
                                                 result.get('status_det'),
                                                 dev_message=result.get('dev_message'))

                if callable(callback):
                    try:
                        await callback(len(file), index * chunk)

                    except exceptions.CancelledError:
                        return None

                    except Exception:
                        pass

                index += 1

            except Exception:
                   pass

        status = result['status']
        status_det = result['status_det']

        if status == 'OK' and status_det == 'OK':
            result = {
                'mime': mime,
                'size': len(file),
                'dc_id': dc_id,
                'file_id': id,
                'file_name': file_name,
                'access_hash_rec': result['data']['access_hash_rec']
            }

            return Results(result)

        #self._client._logger.debug('upload failed', extra={'data': result})
        raise exceptions(status_det)(result, request=result)

    async def download(self, dc_id: int, file_id: int, access_hash: str, size: int, chunk=131072, callback=None):
        hosts = {"storages": {"501": "https://shstorage501.iranlms.ir/GetFile.ashx",
                         "502": "https://shstorage502.iranlms.ir/GetFile.ashx",
                         "503": "https://shstorage503.iranlms.ir/GetFile.ashx",
                         "504": "https://shstorage504.iranlms.ir/GetFile.ashx",
                         "505": "https://shstorage505.iranlms.ir/GetFile.ashx",
                         "506": "https://shstorage506.iranlms.ir/GetFile.ashx",
                         "507": "https://shstorage507.iranlms.ir/GetFile.ashx",
                         "508": "https://shstorage508.iranlms.ir/GetFile.ashx",
                         "509": "https://shstorage509.iranlms.ir/GetFile.ashx",
                         "510": "https://shstorage510.iranlms.ir/GetFile.ashx",
                         "511": "https://shstorage511.iranlms.ir/GetFile.ashx",
                         "512": "https://shstorage512.iranlms.ir/GetFile.ashx",
                         "513": "https://shstorage513.iranlms.ir/GetFile.ashx",
                         "514": "https://shstorage514.iranlms.ir/GetFile.ashx",
                         "515": "https://shstorage515.iranlms.ir/GetFile.ashx",
                         "516": "https://shstorage516.iranlms.ir/GetFile.ashx",
                         "517": "https://shstorage517.iranlms.ir/GetFile.ashx",
                         "518": "https://shstorage518.iranlms.ir/GetFile.ashx",
                         "519": "https://shstorage519.iranlms.ir/GetFile.ashx",
                         "520": "https://shstorage520.iranlms.ir/GetFile.ashx",
                         "521": "https://shstorage521.iranlms.ir/GetFile.ashx",
                         "522": "https://shstorage522.iranlms.ir/GetFile.ashx",
                         "523": "https://shstorage523.iranlms.ir/GetFile.ashx",
                         "524": "https://shstorage524.iranlms.ir/GetFile.ashx",
                         "525": "https://shstorage525.iranlms.ir/GetFile.ashx",
                         "526": "https://shstorage526.iranlms.ir/GetFile.ashx",
                         "527": "https://shstorage527.iranlms.ir/GetFile.ashx",
                         "528": "https://shstorage528.iranlms.ir/GetFile.ashx",
                         "529": "https://shstorage529.iranlms.ir/GetFile.ashx",
                         "530": "https://shstorage530.iranlms.ir/GetFile.ashx",
                         "531": "https://shstorage531.iranlms.ir/GetFile.ashx",
                         "532": "https://shstorage532.iranlms.ir/GetFile.ashx",
                         "533": "https://shstorage533.iranlms.ir/GetFile.ashx",
                         "534": "https://shstorage534.iranlms.ir/GetFile.ashx",
                         "535": "https://shstorage535.iranlms.ir/GetFile.ashx",
                         "536": "https://shstorage536.iranlms.ir/GetFile.ashx",
                         "537": "https://shstorage537.iranlms.ir/GetFile.ashx",
                         "538": "https://shstorage538.iranlms.ir/GetFile.ashx",
                         "539": "https://shstorage539.iranlms.ir/GetFile.ashx",
                         "540": "https://shstorage540.iranlms.ir/GetFile.ashx",
                         "541": "https://shstorage541.iranlms.ir/GetFile.ashx",
                         "542": "https://shstorage542.iranlms.ir/GetFile.ashx",
                         "543": "https://shstorage543.iranlms.ir/GetFile.ashx",
                         "544": "https://shstorage544.iranlms.ir/GetFile.ashx",
                         "545": "https://shstorage545.iranlms.ir/GetFile.ashx",
                         "546": "https://shstorage546.iranlms.ir/GetFile.ashx",
                         "547": "https://shstorage547.iranlms.ir/GetFile.ashx",
                         "548": "https://shstorage548.iranlms.ir/GetFile.ashx",
                         "549": "https://shstorage549.iranlms.ir/GetFile.ashx",
                         "550": "https://shstorage550.iranlms.ir/GetFile.ashx",
                         "10001": "https://shadpubup1.iranlms.ir/GetFile.ashx",
                         "101": "https://shst101.iranlms.ir/GetFile.ashx",
                         "102": "https://shst102.iranlms.ir/GetFile.ashx",
                         "103": "https://shst103.iranlms.ir/GetFile.ashx",
                         "104": "https://shst104.iranlms.ir/GetFile.ashx",
                         "105": "https://shst105.iranlms.ir/GetFile.ashx",
                         "106": "https://shst106.iranlms.ir/GetFile.ashx",
                         "107": "https://shst107.iranlms.ir/GetFile.ashx",
                         "108": "https://shst108.iranlms.ir/GetFile.ashx",
                         "109": "https://shst109.iranlms.ir/GetFile.ashx",
                         "110": "https://shst110.iranlms.ir/GetFile.ashx",
                         "111": "https://shst111.iranlms.ir/GetFile.ashx",
                         "112": "https://shst112.iranlms.ir/GetFile.ashx",
                         "113": "https://shst113.iranlms.ir/GetFile.ashx",
                         "114": "https://shst114.iranlms.ir/GetFile.ashx",
                         "115": "https://shst115.iranlms.ir/GetFile.ashx",
                         "116": "https://shst116.iranlms.ir/GetFile.ashx",
                         "117": "https://shst117.iranlms.ir/GetFile.ashx",
                         "118": "https://shst118.iranlms.ir/GetFile.ashx",
                         "119": "https://shst119.iranlms.ir/GetFile.ashx",
                         "120": "https://shst120.iranlms.ir/GetFile.ashx",
                         "121": "https://shst121.iranlms.ir/GetFile.ashx",
                         "122": "https://shst122.iranlms.ir/GetFile.ashx",
                         "123": "https://shst123.iranlms.ir/GetFile.ashx",
                         "124": "https://shst124.iranlms.ir/GetFile.ashx",
                         "125": "https://shst125.iranlms.ir/GetFile.ashx",
                         "126": "https://shst126.iranlms.ir/GetFile.ashx",
                         "127": "https://shst127.iranlms.ir/GetFile.ashx",
                         "128": "https://shst128.iranlms.ir/GetFile.ashx",
                         "129": "https://shst129.iranlms.ir/GetFile.ashx",
                         "130": "https://shst130.iranlms.ir/GetFile.ashx",
                         "131": "https://shst131.iranlms.ir/GetFile.ashx",
                         "132": "https://shst132.iranlms.ir/GetFile.ashx",
                         "133": "https://shst133.iranlms.ir/GetFile.ashx",
                         "134": "https://shst134.iranlms.ir/GetFile.ashx",
                         "135": "https://shst135.iranlms.ir/GetFile.ashx",
                         "136": "https://shst136.iranlms.ir/GetFile.ashx",
                         "137": "https://shst137.iranlms.ir/GetFile.ashx",
                         "138": "https://shst138.iranlms.ir/GetFile.ashx",
                         "139": "https://shst139.iranlms.ir/GetFile.ashx",
                         "140": "https://shst140.iranlms.ir/GetFile.ashx",
                         "141": "https://shst141.iranlms.ir/GetFile.ashx",
                         "142": "https://shst142.iranlms.ir/GetFile.ashx",
                         "143": "https://shst143.iranlms.ir/GetFile.ashx",
                         "144": "https://shst144.iranlms.ir/GetFile.ashx",
                         "145": "https://shst145.iranlms.ir/GetFile.ashx",
                         "146": "https://shst146.iranlms.ir/GetFile.ashx",
                         "147": "https://shst147.iranlms.ir/GetFile.ashx",
                         "148": "https://shst148.iranlms.ir/GetFile.ashx",
                         "149": "https://shst149.iranlms.ir/GetFile.ashx",
                         "150": "https://shst150.iranlms.ir/GetFile.ashx",
                         "151": "https://shst151.iranlms.ir/GetFile.ashx",
                         "152": "https://shst152.iranlms.ir/GetFile.ashx",
                         "153": "https://shst153.iranlms.ir/GetFile.ashx",
                         "154": "https://shst154.iranlms.ir/GetFile.ashx",
                         "155": "https://shst155.iranlms.ir/GetFile.ashx",
                         "156": "https://shst156.iranlms.ir/GetFile.ashx",
                         "157": "https://shst157.iranlms.ir/GetFile.ashx",
                         "158": "https://shst158.iranlms.ir/GetFile.ashx",
                         "159": "https://shst159.iranlms.ir/GetFile.ashx",
                         "160": "https://shst160.iranlms.ir/GetFile.ashx",
                         "161": "https://shst161.iranlms.ir/GetFile.ashx",
                         "162": "https://shst162.iranlms.ir/GetFile.ashx",
                         "163": "https://shst163.iranlms.ir/GetFile.ashx",
                         "164": "https://shst164.iranlms.ir/GetFile.ashx",
                         "165": "https://shst165.iranlms.ir/GetFile.ashx",
                         "166": "https://shst166.iranlms.ir/GetFile.ashx",
                         "167": "https://shst167.iranlms.ir/GetFile.ashx",
                         "168": "https://shst168.iranlms.ir/GetFile.ashx",
                         "169": "https://shst169.iranlms.ir/GetFile.ashx",
                         "170": "https://shst170.iranlms.ir/GetFile.ashx",
                         "171": "https://shst171.iranlms.ir/GetFile.ashx",
                         "172": "https://shst172.iranlms.ir/GetFile.ashx",
                         "173": "https://shst173.iranlms.ir/GetFile.ashx",
                         "174": "https://shst174.iranlms.ir/GetFile.ashx",
                         "175": "https://shst175.iranlms.ir/GetFile.ashx",
                         "176": "https://shst176.iranlms.ir/GetFile.ashx",
                         "177": "https://shst177.iranlms.ir/GetFile.ashx",
                         "178": "https://shst178.iranlms.ir/GetFile.ashx",
                         "179": "https://shst179.iranlms.ir/GetFile.ashx",
                         "180": "https://shst180.iranlms.ir/GetFile.ashx",
                         "181": "https://shst181.iranlms.ir/GetFile.ashx",
                         "182": "https://shst182.iranlms.ir/GetFile.ashx",
                         "183": "https://shst183.iranlms.ir/GetFile.ashx",
                         "184": "https://shst184.iranlms.ir/GetFile.ashx",
                         "185": "https://shst185.iranlms.ir/GetFile.ashx",
                         "186": "https://shst186.iranlms.ir/GetFile.ashx",
                         "187": "https://shst187.iranlms.ir/GetFile.ashx",
                         "188": "https://shst188.iranlms.ir/GetFile.ashx",
                         "189": "https://shst189.iranlms.ir/GetFile.ashx",
                         "190": "https://shst190.iranlms.ir/GetFile.ashx",
                         "191": "https://shst191.iranlms.ir/GetFile.ashx",
                         "192": "https://shst192.iranlms.ir/GetFile.ashx",
                         "193": "https://shst193.iranlms.ir/GetFile.ashx",
                         "194": "https://shst194.iranlms.ir/GetFile.ashx",
                         "195": "https://shst195.iranlms.ir/GetFile.ashx",
                         "196": "https://shst196.iranlms.ir/GetFile.ashx",
                         "197": "https://shst197.iranlms.ir/GetFile.ashx",
                         "198": "https://shst198.iranlms.ir/GetFile.ashx",
                         "199": "https://shst199.iranlms.ir/GetFile.ashx",
                         "200": "https://shst200.iranlms.ir/GetFile.ashx",
                         "201": "https://shst201.iranlms.ir/GetFile.ashx",
                         "202": "https://shst202.iranlms.ir/GetFile.ashx",
                         "203": "https://shst203.iranlms.ir/GetFile.ashx",
                         "204": "https://shst204.iranlms.ir/GetFile.ashx",
                         "205": "https://shst205.iranlms.ir/GetFile.ashx",
                         "206": "https://shst206.iranlms.ir/GetFile.ashx",
                         "207": "https://shst207.iranlms.ir/GetFile.ashx",
                         "208": "https://shst208.iranlms.ir/GetFile.ashx",
                         "209": "https://shst209.iranlms.ir/GetFile.ashx",
                         "210": "https://shst210.iranlms.ir/GetFile.ashx",
                         "211": "https://shst211.iranlms.ir/GetFile.ashx",
                         "212": "https://shst212.iranlms.ir/GetFile.ashx",
                         "213": "https://shst213.iranlms.ir/GetFile.ashx",
                         "214": "https://shst214.iranlms.ir/GetFile.ashx",
                         "215": "https://shst215.iranlms.ir/GetFile.ashx",
                         "216": "https://shst216.iranlms.ir/GetFile.ashx",
                         "217": "https://shst217.iranlms.ir/GetFile.ashx",
                         "218": "https://shst218.iranlms.ir/GetFile.ashx",
                         "219": "https://shst219.iranlms.ir/GetFile.ashx",
                         "220": "https://shst220.iranlms.ir/GetFile.ashx",
                         "221": "https://shst221.iranlms.ir/GetFile.ashx",
                         "222": "https://shst222.iranlms.ir/GetFile.ashx",
                         "223": "https://shst223.iranlms.ir/GetFile.ashx",
                         "224": "https://shst224.iranlms.ir/GetFile.ashx",
                         "225": "https://shst225.iranlms.ir/GetFile.ashx",
                         "226": "https://shst226.iranlms.ir/GetFile.ashx",
                         "227": "https://shst227.iranlms.ir/GetFile.ashx",
                         "228": "https://shst228.iranlms.ir/GetFile.ashx",
                         "229": "https://shst229.iranlms.ir/GetFile.ashx",
                         "230": "https://shst230.iranlms.ir/GetFile.ashx",
                         "231": "https://shst231.iranlms.ir/GetFile.ashx",
                         "232": "https://shst232.iranlms.ir/GetFile.ashx",
                         "233": "https://shst233.iranlms.ir/GetFile.ashx",
                         "234": "https://shst234.iranlms.ir/GetFile.ashx",
                         "235": "https://shst235.iranlms.ir/GetFile.ashx",
                         "236": "https://shst236.iranlms.ir/GetFile.ashx",
                         "237": "https://shst237.iranlms.ir/GetFile.ashx",
                         "238": "https://shst238.iranlms.ir/GetFile.ashx",
                         "239": "https://shst239.iranlms.ir/GetFile.ashx",
                         "240": "https://shst240.iranlms.ir/GetFile.ashx",
                         "241": "https://shst241.iranlms.ir/GetFile.ashx",
                         "242": "https://shst242.iranlms.ir/GetFile.ashx",
                         "243": "https://shst243.iranlms.ir/GetFile.ashx",
                         "244": "https://shst244.iranlms.ir/GetFile.ashx",
                         "245": "https://shst245.iranlms.ir/GetFile.ashx",
                         "246": "https://shst246.iranlms.ir/GetFile.ashx",
                         "247": "https://shst247.iranlms.ir/GetFile.ashx",
                         "248": "https://shst248.iranlms.ir/GetFile.ashx",
                         "249": "https://shst249.iranlms.ir/GetFile.ashx",
                         "250": "https://shst250.iranlms.ir/GetFile.ashx",
                         "251": "https://shst251.iranlms.ir/GetFile.ashx",
                         "252": "https://shst252.iranlms.ir/GetFile.ashx",
                         "253": "https://shst253.iranlms.ir/GetFile.ashx",
                         "254": "https://shst254.iranlms.ir/GetFile.ashx",
                         "255": "https://shst255.iranlms.ir/GetFile.ashx",
                         "256": "https://shst256.iranlms.ir/GetFile.ashx",
                         "257": "https://shst257.iranlms.ir/GetFile.ashx",
                         "258": "https://shst258.iranlms.ir/GetFile.ashx",
                         "259": "https://shst259.iranlms.ir/GetFile.ashx",
                         "260": "https://shst260.iranlms.ir/GetFile.ashx",
                         "261": "https://shst261.iranlms.ir/GetFile.ashx",
                         "262": "https://shst262.iranlms.ir/GetFile.ashx",
                         "263": "https://shst263.iranlms.ir/GetFile.ashx",
                         "264": "https://shst264.iranlms.ir/GetFile.ashx",
                         "265": "https://shst265.iranlms.ir/GetFile.ashx",
                         "266": "https://shst266.iranlms.ir/GetFile.ashx",
                         "267": "https://shst267.iranlms.ir/GetFile.ashx",
                         "268": "https://shst268.iranlms.ir/GetFile.ashx",
                         "269": "https://shst269.iranlms.ir/GetFile.ashx",
                         "270": "https://shst270.iranlms.ir/GetFile.ashx",
                         "271": "https://shst271.iranlms.ir/GetFile.ashx",
                         "272": "https://shst272.iranlms.ir/GetFile.ashx",
                         "273": "https://shst273.iranlms.ir/GetFile.ashx",
                         "274": "https://shst274.iranlms.ir/GetFile.ashx",
                         "275": "https://shst275.iranlms.ir/GetFile.ashx",
                         "276": "https://shst276.iranlms.ir/GetFile.ashx",
                         "277": "https://shst277.iranlms.ir/GetFile.ashx",
                         "278": "https://shst278.iranlms.ir/GetFile.ashx",
                         "279": "https://shst279.iranlms.ir/GetFile.ashx",
                         "280": "https://shst280.iranlms.ir/GetFile.ashx",
                         "281": "https://shst281.iranlms.ir/GetFile.ashx",
                         "282": "https://shst282.iranlms.ir/GetFile.ashx",
                         "283": "https://shst283.iranlms.ir/GetFile.ashx",
                         "284": "https://shst284.iranlms.ir/GetFile.ashx",
                         "285": "https://shst285.iranlms.ir/GetFile.ashx",
                         "286": "https://shst286.iranlms.ir/GetFile.ashx",
                         "287": "https://shst287.iranlms.ir/GetFile.ashx",
                         "288": "https://shst288.iranlms.ir/GetFile.ashx",
                         "289": "https://shst289.iranlms.ir/GetFile.ashx",
                         "290": "https://shst290.iranlms.ir/GetFile.ashx",
                         "291": "https://shst291.iranlms.ir/GetFile.ashx",
                         "292": "https://shst292.iranlms.ir/GetFile.ashx",
                         "301": "https://shst301.iranlms.ir/GetFile.ashx",
                         "302": "https://shst302.iranlms.ir/GetFile.ashx",
                         "303": "https://shst303.iranlms.ir/GetFile.ashx",
                         "304": "https://shst304.iranlms.ir/GetFile.ashx",
                         "305": "https://shst305.iranlms.ir/GetFile.ashx",
                         "306": "https://shst306.iranlms.ir/GetFile.ashx",
                         "307": "https://shst307.iranlms.ir/GetFile.ashx",
                         "308": "https://shst308.iranlms.ir/GetFile.ashx",
                         "309": "https://shst309.iranlms.ir/GetFile.ashx",
                         "310": "https://shst310.iranlms.ir/GetFile.ashx",
                         "311": "https://shst311.iranlms.ir/GetFile.ashx",
                         "312": "https://shst312.iranlms.ir/GetFile.ashx",
                         "313": "https://shst313.iranlms.ir/GetFile.ashx",
                         "314": "https://shst314.iranlms.ir/GetFile.ashx",
                         "315": "https://shst315.iranlms.ir/GetFile.ashx",
                         "316": "https://shst316.iranlms.ir/GetFile.ashx",
                         "317": "https://shst317.iranlms.ir/GetFile.ashx",
                         "318": "https://shst318.iranlms.ir/GetFile.ashx",
                         "319": "https://shst319.iranlms.ir/GetFile.ashx",
                         "320": "https://shst320.iranlms.ir/GetFile.ashx",
                         "321": "https://shst321.iranlms.ir/GetFile.ashx",
                         "322": "https://shst322.iranlms.ir/GetFile.ashx",
                         "323": "https://shst323.iranlms.ir/GetFile.ashx",
                         "324": "https://shst324.iranlms.ir/GetFile.ashx",
                         "325": "https://shst325.iranlms.ir/GetFile.ashx",
                         "326": "https://shst326.iranlms.ir/GetFile.ashx",
                         "327": "https://shst327.iranlms.ir/GetFile.ashx",
                         "328": "https://shst328.iranlms.ir/GetFile.ashx",
                         "329": "https://shst329.iranlms.ir/GetFile.ashx",
                         "330": "https://shst330.iranlms.ir/GetFile.ashx",
                         "331": "https://shst331.iranlms.ir/GetFile.ashx",
                         "332": "https://shst332.iranlms.ir/GetFile.ashx",
                         "333": "https://shst333.iranlms.ir/GetFile.ashx",
                         "334": "https://shst334.iranlms.ir/GetFile.ashx",
                         "335": "https://shst335.iranlms.ir/GetFile.ashx",
                         "336": "https://shst336.iranlms.ir/GetFile.ashx",
                         "337": "https://shst337.iranlms.ir/GetFile.ashx",
                         "338": "https://shst338.iranlms.ir/GetFile.ashx",
                         "339": "https://shst339.iranlms.ir/GetFile.ashx",
                         "340": "https://shst340.iranlms.ir/GetFile.ashx",
                         "341": "https://shst341.iranlms.ir/GetFile.ashx",
                         "342": "https://shst342.iranlms.ir/GetFile.ashx",
                         "343": "https://shst343.iranlms.ir/GetFile.ashx",
                         "344": "https://shst344.iranlms.ir/GetFile.ashx",
                         "345": "https://shst345.iranlms.ir/GetFile.ashx",
                         "346": "https://shst346.iranlms.ir/GetFile.ashx",
                         "347": "https://shst347.iranlms.ir/GetFile.ashx",
                         "348": "https://shst348.iranlms.ir/GetFile.ashx",
                         "349": "https://shst349.iranlms.ir/GetFile.ashx",
                         "350": "https://shst350.iranlms.ir/GetFile.ashx",
                         "351": "https://shst351.iranlms.ir/GetFile.ashx",
                         "352": "https://shst352.iranlms.ir/GetFile.ashx",
                         "353": "https://shst353.iranlms.ir/GetFile.ashx",
                         "354": "https://shst354.iranlms.ir/GetFile.ashx",
                         "355": "https://shst355.iranlms.ir/GetFile.ashx",
                         "356": "https://shst356.iranlms.ir/GetFile.ashx",
                         "357": "https://shst357.iranlms.ir/GetFile.ashx",
                         "358": "https://shst358.iranlms.ir/GetFile.ashx",
                         "359": "https://shst359.iranlms.ir/GetFile.ashx",
                         "360": "https://shst360.iranlms.ir/GetFile.ashx",
                         "361": "https://shst361.iranlms.ir/GetFile.ashx",
                         "362": "https://shst362.iranlms.ir/GetFile.ashx",
                         "363": "https://shst363.iranlms.ir/GetFile.ashx",
                         "364": "https://shst364.iranlms.ir/GetFile.ashx",
                         "365": "https://shst365.iranlms.ir/GetFile.ashx",
                         "366": "https://shst366.iranlms.ir/GetFile.ashx",
                         "367": "https://shst367.iranlms.ir/GetFile.ashx",
                         "368": "https://shst368.iranlms.ir/GetFile.ashx",
                         "369": "https://shst369.iranlms.ir/GetFile.ashx",
                         "370": "https://shst370.iranlms.ir/GetFile.ashx",
                         "371": "https://shst371.iranlms.ir/GetFile.ashx",
                         "372": "https://shst372.iranlms.ir/GetFile.ashx",
                         "373": "https://shst373.iranlms.ir/GetFile.ashx",
                         "374": "https://shst374.iranlms.ir/GetFile.ashx",
                         "375": "https://shst375.iranlms.ir/GetFile.ashx",
                         "376": "https://shst376.iranlms.ir/GetFile.ashx",
                         "377": "https://shst377.iranlms.ir/GetFile.ashx",
                         "378": "https://shst378.iranlms.ir/GetFile.ashx",
                         "379": "https://shst379.iranlms.ir/GetFile.ashx",
                         "380": "https://shst380.iranlms.ir/GetFile.ashx",
                         "381": "https://shst381.iranlms.ir/GetFile.ashx",
                         "382": "https://shst382.iranlms.ir/GetFile.ashx",
                         "383": "https://shst383.iranlms.ir/GetFile.ashx",
                         "384": "https://shst384.iranlms.ir/GetFile.ashx",
                         "385": "https://shst385.iranlms.ir/GetFile.ashx",
                         "386": "https://shst386.iranlms.ir/GetFile.ashx",
                         "387": "https://shst387.iranlms.ir/GetFile.ashx",
                         "388": "https://shst388.iranlms.ir/GetFile.ashx",
                         "389": "https://shst389.iranlms.ir/GetFile.ashx",
                         "390": "https://shst390.iranlms.ir/GetFile.ashx",
                         "391": "https://shst391.iranlms.ir/GetFile.ashx",
                         "392": "https://shst392.iranlms.ir/GetFile.ashx",
                         "393": "https://shst393.iranlms.ir/GetFile.ashx",
                         "394": "https://shst394.iranlms.ir/GetFile.ashx",
                         "395": "https://shst395.iranlms.ir/GetFile.ashx",
                         "396": "https://shst396.iranlms.ir/GetFile.ashx",
                         "397": "https://shst397.iranlms.ir/GetFile.ashx",
                         "398": "https://shst398.iranlms.ir/GetFile.ashx",
                         "399": "https://shst399.iranlms.ir/GetFile.ashx",
                         "400": "https://shst400.iranlms.ir/GetFile.ashx",
                         "401": "https://shst401.iranlms.ir/GetFile.ashx",
                         "402": "https://shst402.iranlms.ir/GetFile.ashx",
                         "403": "https://shst403.iranlms.ir/GetFile.ashx",
                         "404": "https://shst404.iranlms.ir/GetFile.ashx",
                         "405": "https://shst405.iranlms.ir/GetFile.ashx",
                         "406": "https://shst406.iranlms.ir/GetFile.ashx",
                         "407": "https://shst407.iranlms.ir/GetFile.ashx",
                         "408": "https://shst408.iranlms.ir/GetFile.ashx",
                         "409": "https://shst409.iranlms.ir/GetFile.ashx",
                         "410": "https://shst410.iranlms.ir/GetFile.ashx",
                         "411": "https://shst411.iranlms.ir/GetFile.ashx",
                         "412": "https://shst412.iranlms.ir/GetFile.ashx",
                         "413": "https://shst413.iranlms.ir/GetFile.ashx",
                         "414": "https://shst414.iranlms.ir/GetFile.ashx",
                         "415": "https://shst415.iranlms.ir/GetFile.ashx",
                         "416": "https://shst416.iranlms.ir/GetFile.ashx",
                         "417": "https://shst417.iranlms.ir/GetFile.ashx",
                         "418": "https://shst418.iranlms.ir/GetFile.ashx",
                         "419": "https://shst419.iranlms.ir/GetFile.ashx",
                         "420": "https://shst420.iranlms.ir/GetFile.ashx",
                         "421": "https://shst421.iranlms.ir/GetFile.ashx",
                         "422": "https://shst422.iranlms.ir/GetFile.ashx",
                         "423": "https://shst423.iranlms.ir/GetFile.ashx",
                         "424": "https://shst424.iranlms.ir/GetFile.ashx",
                         "425": "https://shst425.iranlms.ir/GetFile.ashx",
                         "426": "https://shst426.iranlms.ir/GetFile.ashx",
                         "427": "https://shst427.iranlms.ir/GetFile.ashx",
                         "428": "https://shst428.iranlms.ir/GetFile.ashx",
                         "429": "https://shst429.iranlms.ir/GetFile.ashx",
                         "430": "https://shst430.iranlms.ir/GetFile.ashx",
                         "431": "https://shst431.iranlms.ir/GetFile.ashx",
                         "432": "https://shst432.iranlms.ir/GetFile.ashx",
                         "433": "https://shst433.iranlms.ir/GetFile.ashx",
                         "434": "https://shst434.iranlms.ir/GetFile.ashx",
                         "435": "https://shst435.iranlms.ir/GetFile.ashx",
                         "436": "https://shst436.iranlms.ir/GetFile.ashx",
                         "437": "https://shst437.iranlms.ir/GetFile.ashx",
                         "438": "https://shst438.iranlms.ir/GetFile.ashx",
                         "439": "https://shst439.iranlms.ir/GetFile.ashx",
                         "440": "https://shst440.iranlms.ir/GetFile.ashx",
                         "441": "https://shst441.iranlms.ir/GetFile.ashx",
                         "442": "https://shst442.iranlms.ir/GetFile.ashx",
                         "443": "https://shst443.iranlms.ir/GetFile.ashx",
                         "444": "https://shst444.iranlms.ir/GetFile.ashx",
                         "445": "https://shst445.iranlms.ir/GetFile.ashx",
                         "446": "https://shst446.iranlms.ir/GetFile.ashx",
                         "447": "https://shst447.iranlms.ir/GetFile.ashx",
                         "448": "https://shst448.iranlms.ir/GetFile.ashx",
                         "449": "https://shst449.iranlms.ir/GetFile.ashx",
                         "450": "https://shst450.iranlms.ir/GetFile.ashx",
                         "451": "https://shst451.iranlms.ir/GetFile.ashx",
                         "452": "https://shst452.iranlms.ir/GetFile.ashx",
                         "453": "https://shst453.iranlms.ir/GetFile.ashx"},
            "default_api_urls": ["https://shadmessenger162.iranlms.ir", "https://shadmessenger75.iranlms.ir",
                                 "https://shadmessenger28.iranlms.ir"],
            "default_sockets": ["wss://shsocket8.iranlms.ir:80", "wss://shsocket4.iranlms.ir:80",
                                "wss://shsocket11.iranlms.ir:80"],
            "default_bot_urls": ["https://shadmessenger6.iranlms.ir", "https://shadmessenger3.iranlms.ir",
                                 "https://shadmessenger7.iranlms.ir"]}
        url = hosts['storages'][dc_id]
        start_index = 0
        result = b''

        headers = {
            'auth': self.client.auth,
            'access-hash-rec': access_hash,
            'file-id': str(file_id),
            'user-agent': self.client.user_agent
        }

        async with aiohttp.ClientSession() as session:
            while True:
                last_index = start_index + chunk - 1 if start_index + chunk < size else size - 1

                headers['start-index'] = str(start_index)
                headers['last-index'] = str(last_index)

                response = await session.post(url, headers=headers)
                if response.ok:
                    data = await response.read()
                    if data:
                        result += data

                        if callback:
                            await callback(size, len(result))

                # Check for the end of the file
                if len(result) >= size:
                    break

                # Update the start_index value to fetch the next part of the file
                start_index = last_index + 1

        return result