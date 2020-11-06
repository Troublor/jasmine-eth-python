from __future__ import annotations

import asyncio
import json
from os import path

from web3.gas_strategies.rpc import rpc_gas_price_strategy
from web3.types import TxParams, TxReceipt, ABI
from web3 import Web3


class Web3Wrapper(object):
    def __init__(self, web3: Web3):
        self._web3 = web3

    @property
    def web3(self) -> Web3:
        return self._web3

    async def send_transaction(self, transaction: TxParams, sender: Account) -> TxReceipt:
        # TODO implement transaction confirmation requirement
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        # check transaction fields
        if "gas" not in transaction:
            transaction["gas"] = self._web3.eth.estimateGas(transaction)
        if "gasPrice" not in transaction:
            self._web3.eth.setGasPriceStrategy(rpc_gas_price_strategy)
            transaction["gasPrice"] = self._web3.eth.generateGasPrice(transaction)
        if "nonce" not in transaction:
            transaction["nonce"] = self._web3.eth.getTransactionCount(sender.address)

        # sign transaction
        signed_tx = self._web3.eth.account.sign_transaction(transaction, sender.private_key)

        async def transaction_task():
            try:
                tx_hash = self._web3.eth.sendRawTransaction(signed_tx.rawTransaction)
                receipt: TxReceipt = self._web3.eth.waitForTransactionReceipt(tx_hash)
                future.set_result(receipt)
            except Exception as e:
                future.set_exception(e)

        loop.create_task(transaction_task())
        return await future


class Account(Web3Wrapper):
    def __init__(self, web3: Web3, private_key: str):
        super().__init__(web3)
        self._web3 = web3
        self._private_key = private_key
        self._eth_account = self._web3.eth.account.from_key(private_key)

    @property
    def private_key(self) -> str:
        return self._private_key

    @property
    def address(self) -> str:
        return self._eth_account.address


class SDK(Web3Wrapper):
    def __init__(self, endpoint: str):
        # initiate web3
        endpoint = endpoint.strip()
        if endpoint is not None and endpoint.startswith("http"):
            provider = Web3.HTTPProvider(endpoint)
        elif endpoint is not None and endpoint.startswith("ws"):
            provider = Web3.WebsocketProvider(endpoint)
        else:
            raise ValueError("unsupported Ethereum endpoint {}".format(endpoint))
        super().__init__(Web3(provider))

    def create_account(self) -> Account:
        acc = self.web3.eth.account.create()
        return Account(self.web3, acc.key)

    def retrieve_account(self, private_key: str) -> Account:
        return Account(self.web3, private_key)

    def balance_of(self, address: str) -> int:
        return self.web3.eth.getBalance(address)

    async def transfer(self, recipient: str, amount: int, sender: Account):
        transaction: TxParams = {
            "from": sender.address,
            "to": recipient,
            "value": amount,
        }
        await self.send_transaction(transaction, sender)

    def wei_to_eth(self, amount_wei: int) -> float:
        return self.web3.fromWei(amount_wei, 'ether')

    def eth_to_wei(self, amount_eth: float) -> int:
        return self.web3.toWei(amount_eth, 'ether')

    async def deploy_tfc_manager(self, deployer: Account) -> str:
        contract = self.web3.eth.contract(abi=TFCManager.abi(), bytecode=TFCManager.bytecode())
        transaction = contract.constructor().buildTransaction({
            "from": deployer.address,
        })
        receipt: TxReceipt = await self.send_transaction(transaction, deployer)
        return receipt["contractAddress"]

    def get_tfc_manager(self, address: str) -> TFCManager:
        return TFCManager(self.web3, address)

    def get_tfc_token(self, address: str) -> TFCToken:
        return TFCToken(self.web3, address)


class TFCManager(Web3Wrapper):
    @staticmethod
    def bytecode() -> str:
        dir_path = path.dirname(path.realpath(__file__))
        with open(path.join(dir_path, "contracts", "TFCManager.bin")) as file:
            return file.readline()

    @staticmethod
    def abi() -> ABI:
        dir_path = path.dirname(path.realpath(__file__))
        with open(path.join(dir_path, "contracts", "TFCManager.abi.json")) as file:
            return json.load(file)

    def __init__(self, web3: Web3, address: str):
        super().__init__(web3)
        self._contract = self.web3.eth.contract(address=address, abi=self.abi())

    def tfc_token_address(self) -> str:
        return self._contract.functions.tfcToken().call()

    async def claim_tfc(self, amount: int, nonce: int, signature: str, claimer: Account):
        sig = self.web3.toBytes(hexstr=signature)
        transaction = self._contract.functions.claimTFC(amount, nonce, sig).buildTransaction({
            "from": claimer.address
        })
        await self.send_transaction(transaction, claimer)


class TFCToken(Web3Wrapper):
    @staticmethod
    def bytecode() -> str:
        dir_path = path.dirname(path.realpath(__file__))
        with open(path.join(dir_path, "contracts", "TFCToken.bin")) as file:
            return file.readline()

    @staticmethod
    def abi() -> ABI:
        dir_path = path.dirname(path.realpath(__file__))
        with open(path.join(dir_path, "contracts", "TFCToken.abi.json")) as file:
            return json.load(file)

    def __init__(self, web3: Web3, address: str):
        super().__init__(web3)
        self._contract = self.web3.eth.contract(address=address, abi=self.abi())

    @property
    def name(self):
        return self._contract.functions.name().call()

    @property
    def symbol(self):
        return self._contract.functions.symbol().call()

    @property
    def decimals(self):
        return self._contract.functions.decimals().call()

    @property
    def total_supply(self):
        return self._contract.functions.totalSupply().call()

    def allowance(self, owner: str, spender: str) -> int:
        return self._contract.functions.allowance(owner, spender).call()

    def balance_of(self, owner: str) -> int:
        return self._contract.functions.balanceOf(owner).call()

    async def transfer(self, recipient: str, amount: int, sender: Account):
        transaction = self._contract.functions.transfer(recipient, amount).buildTransaction({
            "from": sender.address
        })
        await self.send_transaction(transaction, sender)

    async def transfer_from(self, sender: str, recipient: str, amount: int, spender: Account):
        transaction = self._contract.functions.transferFrom(sender, recipient, amount).buildTransaction({
            "from": spender.address
        })
        await self.send_transaction(transaction, spender)

    async def approve(self, spender: str, amount: int, owner: Account):
        transaction = self._contract.functions.approve(spender, amount).buildTransaction({
            "from": owner.address
        })
        await self.send_transaction(transaction, owner)
