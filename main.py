# import requests
from web3 import Web3
from loguru import logger
import json,os
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed
from  fake_useragent import UserAgent
from eth_account.messages import encode_defunct
import requests
from datetime import timedelta,datetime
import time
import threading
from functools import *
logger.add(
    "Rivalz_TestNet_Bot.log",
    rotation="1 week",
    retention="1 month",
    level="INFO",
    format="{time} {level} {message}",
    compression="zip"  # 轮换日志文件时进行压缩
)
def ckeck_one_day(func):
    def pass_func(name):
        logger.info(f'{name}-距离上次执行-{func.__name__}-还没有一天')
    def update_time(cls,key,wallet):
        wallet[key]=time.time()
        cls.update_wallet(wallet)
    @wraps(func)
    def wrapper(*args, **kwargs):
        this=args[0]
        key=func.__name__+'_ts'
        token=kwargs.get('token')
        
        if token:
            key+=f'_{token}'
        wallet=kwargs['wallet']
        ts=wallet.get(key)
        if not ts:
            func(*args, **kwargs)
            update_time(this,key,wallet)
            return 
        name=wallet['name']
        dt1 = datetime.fromtimestamp(ts)
        now = datetime.fromtimestamp(time.time())
        # 计算时间差
        time_difference = abs(now-dt1)
        if time_difference >= timedelta(days=1):
            func(*args, **kwargs)
            update_time(this,key,wallet)
            return 
        else:
            return pass_func(name)
    return wrapper
ua=UserAgent()
class Rivalz_TestNet_Bot:


    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        # Requests sorts cookies= alphabetically
        'Cookie': 'chakra-ui-color-mode=light; chakra-ui-color-mode-hex=#FFFFFF; ph_phc_TXdpocbGVeZVm5VJmAsHTMrCofBQu3e0kN8HGMNGTVW_posthog=%7B%22distinct_id%22%3A%22019121a6-c1e0-727a-a0e4-552b2d846698%22%2C%22%24sesid%22%3A%5B1722846474878%2C%22019121a6-c1df-7212-ac87-bcd3766e8484%22%2C1722846462431%5D%7D',
        'Pragma': 'no-cache',
        'Referer': 'https://rivalz2.explorer.caldera.xyz/address/0x72691a36ED1fAC3b197Fb42612Dc15a8958bf9f2?tab=tokens_nfts',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0',
        'sec-ch-ua': '"Not)A;Brand";v="99", "Microsoft Edge";v="127", "Chromium";v="127"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }
    _lock=threading.Lock()
    def __init__(self,wallet_path='./wallets',contract_path='./contract',rpc_url = 'https://rivalz2.rpc.caldera.xyz/infra-partner-http'):
        self.rpc_url=rpc_url
        self.wallet_path=wallet_path
        self.contract_path=contract_path
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        self.ip_pool=[]
        # 检查连接是否成功
        if not self.web3.is_connected():
            raise Exception("无法连接到 plumenet 节点")
        self.chain_id=6966
        # 初始化钱包
        self.wallets=[]
        self.get_contract()
        logger.success(f'初始化智能合约成功：{self.contracts.keys()}')
        self.get_wallets()
        logger.success(f'初始化钱包成功-钱包数量：{len(self.wallets)}')

    def get_sign(self,wallet,msg):
        # 账户信息
        private_key = wallet['private_key']
        address =wallet['address']
        # 使用web3.py编码消息
        message_encoded = encode_defunct(text=msg)
        # 签名消息
        signed_message = self.web3.eth.account.sign_message(message_encoded, private_key=private_key)
        # 打印签名的消息
        return signed_message.signature.hex()
    def check_balance(self,address):
        # 获取账户余额（单位是 Wei）
        balance_wei = self.web3.eth.get_balance(address)
        # 将余额从 Wei 转换为 Ether
        balance_ether = self.web3.from_wei(balance_wei, 'ether')
        params = {
            'type': 'ERC-1155',
        }

        response = requests.get(f'https://rivalz2.explorer.caldera.xyz/api/v2/addresses/{address}/tokens', params=params, headers=self.headers)
        data=[int(i.get('value',0)) for i in  response.json()['items']]
        return {
            "ETH":round(float(balance_ether),5),
            "NTFs":sum(data)
        }
    def generate_and_save_wallet(self,filename):
        # 生成新账户
        account = self.web3.eth.account.create()
        # 获取地址和私钥
        address = account.address
        try:
            private_key = account.privateKey.hex()
        except:
            private_key = account._private_key.hex()
        # 将地址和私钥保存到 JSON 文件
        wallet_info = {
            'address': address,
            'private_key': private_key
        }
        with open(filename, 'w') as file:
            json.dump(wallet_info, file, indent=4)
        logger.success(f"创建钱包成功-已保存到 {filename}")
    def load_wallet(self,filename):
        # 从 JSON 文件中读取钱包信息
        with open(filename, 'r') as file:
            wallet_info = json.load(file)
        wallet_name=filename.split('/')[-1].replace('.json','')
        wallet_info['name']=wallet_name
        wallet_info['balance']=self.check_balance(wallet_info['address'])
        wallet_info['init']=bool(wallet_info['balance']['ETH']>0)
        wallet_info['filename']=filename
        
        return wallet_info
    def load_contract(self,filename:str):
        # 从 JSON 文件中读取钱包信息
        with open(filename, 'r') as file:
            contract_info = json.load(file)
        return contract_info
    
    def update_wallet(self,wallet:dict,**params):
        filename=wallet.get('filename')
        for k,v in params.items():
            wallet[k]=v
        with open(filename, 'w') as file:
            json.dump(wallet, file, indent=4)
        logger.success(f"钱包信息已更新 {filename}")
        
    def get_wallets(self,max_workers=10):
        self.wallets=[]
        wallets_list = glob.glob(os.path.join(self.wallet_path, '*'))
        # 使用线程池来并发加载钱包
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.load_wallet, wallet) for wallet in wallets_list]

            for future in as_completed(futures):
                try:
                    wallet_data = future.result()
                    self.wallets.append(wallet_data)
                except Exception as e:
                    logger.error(f"Error loading wallet: {e}")
        self.show_inited_account()
        return wallets_list
    def get_contract(self):
        self.contracts={}
        contracts_list = glob.glob(os.path.join(self.contract_path, '*'))
        # 使用线程池来并发加载钱包
        for contract_path in contracts_list:
            contract_info=self.load_contract(contract_path)
            name=contract_info.get('name')
            contract_address=contract_info.get('address')
            abi=contract_info.get('abi')
            contract_address=self.web3.to_checksum_address(contract_address)
            contract = self.web3.eth.contract(address=contract_address, abi=abi)
            self.contracts[name]=contract
    def create_wallets(self,num=1):
        index=len(self.wallets)+1
        for i in range(index,index+num):
            filename=os.path.join(self.wallet_path,f'wallet{i}.json')
            self.generate_and_save_wallet(filename)
            wallet=self.load_wallet(filename)
            self.wallets.append(
            wallet
            )
        time.sleep(5)
        self.init_accounts()

    
    
    def get_contract_transaction_gas_limit(self,func,address):
        # 估算所需的 gas
        gas_estimate = func.estimate_gas({
        'from': address
        })
        # 获取当前 gas 价格
        gas_price = self.web3.eth.gas_price
        # 获取账户余额
        balance = self.web3.eth.get_balance(address)
        # 计算总费用
        total_cost = gas_estimate * gas_price
        # 判断 gas 或转账是否合理
        if total_cost > balance:
            ValueError('gas不足改日领水后重试')
        # 返回估算的 gas
        return gas_estimate
    def approve(self,wallet,spender='0x4c722a53cf9eb5373c655e1dd2da95acc10152d1',value=100000,token='GOON'):
        name=wallet['name']
        address=wallet['address']
        private_key=wallet['private_key']
        token_contract=self.contracts[token]
        spender=self.web3.to_checksum_address(spender)
        decimals = token_contract.functions.decimals().call()
        value=int(value * (10 ** decimals))
        gas_limit=self.get_contract_transaction_gas_limit(token_contract.functions.approve(spender,value),address)
        transaction =token_contract.functions.approve(
            spender,value
        ).build_transaction(
            {
            'chainId': self.chain_id,  # 主网的链 ID，测试网可能不同
            'gas': gas_limit,  # Gas 限额
            'gasPrice': int(self.web3.eth.gas_price*1.2),  # Gas 价格
            'nonce': self.web3.eth.get_transaction_count(address),  # 获取 nonce
        }
        )
        # 签署交易
        signed_transaction = self.web3.eth.account.sign_transaction(transaction, private_key=private_key)
        # 等待交易被挖矿
        # 发送已签署的交易
        tx_hash = self.web3.eth.send_raw_transaction(signed_transaction.rawTransaction)
        # 等待交易被挖矿
        try:
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            logger.success(f'{name}-授权成功-Transaction-交易哈希: {tx_hash.hex()}-交易状态: {receipt.status}')
        except Exception as e:
            logger.error(f'{name}-授权成功-ERROR：{e}')
    
    # @ckeck_one_day
    def checkin(self,wallet:dict):
        count=0
        while count<=20:
            checkin_func=self.contracts['claim'].functions.claim()
            # 构建交易
            name=wallet['name']
            address=wallet['address']
            private_key=wallet['private_key']
            try:
                gas_limit=self.get_contract_transaction_gas_limit(checkin_func,address)
            except Exception as e:
                gas_limit=210000
            with self._lock:
                transaction = checkin_func.build_transaction({
                    'chainId': self.chain_id,  # 主网的链 ID，测试网可能不同
                    'gas': gas_limit,  # Gas 限额
                    'gasPrice': int(self.web3.eth.gas_price*1.2),  # Gas 价格
                    'nonce': self.web3.eth.get_transaction_count(address),  # 获取 nonce
                })
                # 签署交易
                signed_transaction = self.web3.eth.account.sign_transaction(transaction, private_key=private_key)
            # 等待交易被挖矿
            # 发送已签署的交易
            tx_hash = self.web3.eth.send_raw_transaction(signed_transaction.rawTransaction)
            # 等待交易被挖矿
            try:
                receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
                logger.success(f'{name}签到成功-count:{count}-Transaction-交易哈希: {tx_hash.hex()}-交易状态: {receipt.status}')
                wallet['checkin_time']=time.time()
                if receipt.status:
                    count+=1
            except Exception as e:
                logger.error(f'{name}签到失败-count:{count}-ERROR：{e}')
    
    def show_inited_account(self):
        print_str=f'\n{"index":<3}\t{"name":<10}\t{"balance":<80}\n'
        for wallet in self.wallets:
            name=wallet['name'].split('\\')[-1].replace('.json','')
            print_str+=f"{self.wallets.index(wallet):<3}\t{name:<10}\t{str(wallet.get('balance')):<80}\n"
        if not self.wallets:
            print_str+='暂无钱包，请创建...'
        logger.success(print_str)
   
    
    def daily_task(self,wallet):
        try:
            self.checkin(wallet=wallet)

        except Exception as e:
            logger.warning(f"{wallet.get('name')}-当日已签到或错误-{e}")
       
    
    def do_daily_tasks(self,max_workers=10):
        self.get_wallets()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.daily_task, wallet) for wallet in self.wallets]
            for future in as_completed(futures):
                try:
                    data = future.result()
                except Exception as e:
                    logger.error(f"Error daily_task wallet: {e}")
        
        self.get_wallets()
        
bot=Rivalz_TestNet_Bot()
# bot.create_wallets(1)
bot.do_daily_tasks(max_workers=1)
# bot.swap(bot.wallets[0])
