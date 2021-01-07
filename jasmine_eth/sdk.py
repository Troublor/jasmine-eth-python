import asyncio
import json
from os import path

from web3.gas_strategies.rpc import rpc_gas_price_strategy
from web3.types import TxParams, TxReceipt, ABI
from web3 import Web3


class _Web3Wrapper(object):
    def __init__(self, web3: Web3):
        self._web3 = web3

    @property
    def web3(self) -> Web3:
        return self._web3

    async def send_transaction(self, transaction: TxParams, sender) -> TxReceipt:
        # TODO implement transaction confirmation requirement
        loop = asyncio.get_event_loop()
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


class Account(_Web3Wrapper):
    """
    Represent an Ethereum account.
    """

    def __init__(self, web3: Web3, private_key: str):
        """
        :param web3: web3py web3 instance
        :param private_key: the private key of the account
        """
        super().__init__(web3)
        self._web3 = web3
        self._private_key = private_key
        self._eth_account = self._web3.eth.account.from_key(private_key)

    @property
    def private_key(self) -> str:
        """
        :return: the private key (str) of the account
        """
        return self._private_key

    @property
    def address(self) -> str:
        """
        :return: the Ethereum address (str) of the account
        """
        return self._eth_account.address


class SDK(_Web3Wrapper):
    """
    The jasmine-eth SDK class
    """

    def __init__(self, endpoint: str):
        """
        :param endpoint: Ethereum endpoint. e.g. http://localhost:8545
        """
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
        """
        Create a new account
        :return: a new Ethereum account
        """
        acc = self.web3.eth.account.create()
        return Account(self.web3, acc.key)

    def retrieve_account(self, private_key: str) -> Account:
        """
        Retrieve an existing account using private key
        :return: the retrieved Ethereum account
        """
        return Account(self.web3, private_key)

    def balance_of(self, address: str) -> int:
        """
        Get the ETH balance of an account
        :param address: the address of the account
        :return: ETH balance in wei
        """
        address = self.web3.toChecksumAddress(address)
        return self.web3.eth.getBalance(address)

    async def transfer(self, recipient: str, amount: int, sender: Account):
        """
        Transfer the amount of ETH from sender to recipient.

        This is an async function will complete only when the transaction is executed on chain.
        If the transaction fails, exception will be thrown.
        :param recipient: the address of recipient address
        :param amount: the amount of ETH to transfer (in wei)
        :param sender: the sender account
        """
        transaction: TxParams = {
            "from": sender.address,
            "to": recipient,
            "value": amount,
        }
        await self.send_transaction(transaction, sender)

    def wei_to_eth(self, amount_wei: int) -> float:
        """
        Convert from wei to ETH
        :param amount_wei: amount of wei
        :return: the amount of ETH according to the amount of wei
        """
        return self.web3.fromWei(amount_wei, 'ether')

    def eth_to_wei(self, amount_eth: float) -> int:
        """
        Convert from ETH to wei
        :param amount_eth: amount of eth
        :return: the amount of wei according to the amount of ETH
        """
        return self.web3.toWei(amount_eth, 'ether')

    async def deploy_tfc_manager(self, deployer: Account) -> str:
        """
        Deploy the TFCManager smart contract, which will implicitly deploy a TFCToken contract.

        This is an async function will complete only when the deployment is executed on chain.
        If the deployment fails, exception will be thrown.
        :param deployer: the Ethereum account used to deploy
        :return: the address of TFCManager contract
        """
        contract = self.web3.eth.contract(abi=TFCManager.abi(), bytecode=TFCManager.bytecode())
        transaction = contract.constructor().buildTransaction({
            "from": deployer.address,
        })
        receipt: TxReceipt = await self.send_transaction(transaction, deployer)
        return receipt["contractAddress"]

    def get_tfc_manager(self, address: str):
        """
        Get the TFCManager contract instance
        :param address: the address of TFCManager contract
        :return: TFCManager contract instance
        """
        address = self.web3.toChecksumAddress(address)
        return TFCManager(self.web3, address)

    def get_tfc_token(self, address: str):
        """
        Get the TFCToken contract instance
        :param address: the address of TFCToken contract
        :return: TFCToken contract instance
        """
        address = self.web3.toChecksumAddress(address)
        return TFCToken(self.web3, address)


class TFCManager(_Web3Wrapper):
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
        address = self.web3.toChecksumAddress(address)
        self._contract = self.web3.eth.contract(address=address, abi=self.abi())

    def tfc_token_address(self) -> str:
        """
        Get the TFCToken contract address linked to this TFCManager
        :return: address of TFCToken contract
        """
        return self._contract.functions.tfcToken().call()

    async def claim_tfc(self, amount: int, nonce: int, signature: str, claimer: Account):
        """
        Claim TFC ERC20 token.
        It takes the amount of TFC token to claim, the nonce used and the signature signed by TFCManager admin account.
        The amount of TFC token is in the minimal unit 10^-18.

        This is an async function will complete only when the claim transaction is executed on chain.
        If the claim transaction fails, exception will be thrown.
        :param amount: the amount of TFC token to claim (unit 10^-18)
        :param nonce: the nonce used in this claim
        :param signature: the signature signed by TFCManager admin account
        :param claimer: the Ethereum account which wants to claim these TFC
        """
        sig = self.web3.toBytes(hexstr=signature)
        transaction = self._contract.functions.claimTFC(amount, nonce, sig).buildTransaction({
            "from": claimer.address
        })
        await self.send_transaction(transaction, claimer)


class TFCToken(_Web3Wrapper):
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
        address = web3.toChecksumAddress(address)
        self._contract = self.web3.eth.contract(address=address, abi=self.abi())

    @property
    def name(self):
        """
        :return: the name of this ERC20 contract
        """
        return self._contract.functions.name().call()

    @property
    def symbol(self):
        """
        :return: the symbol of this ERC20
        """
        return self._contract.functions.symbol().call()

    @property
    def decimals(self):
        """
        :return: the decimals used by this ERC20
        """
        return self._contract.functions.decimals().call()

    @property
    def total_supply(self):
        """
        :return: total supply of this ERC20
        """
        return self._contract.functions.totalSupply().call()

    def allowance(self, owner: str, spender: str) -> int:
        """
        Get the allowance of TFC token which the owner allows the spender to spend
        :param owner: the owner address
        :param spender: the spender address
        :return: the amount of allowance (in unit 10^-18)
        """
        return self._contract.functions.allowance(owner, spender).call()

    def balance_of(self, owner: str) -> int:
        """
        Get the TFC token balance of an account
        :param owner: the address of the account
        :return: the amount of TFC balance (in unit 10^-18)
        """
        return self._contract.functions.balanceOf(owner).call()

    async def transfer(self, recipient: str, amount: int, sender: Account):
        """
        Transfer the amount of TFC from sender to recipient.

        This is an async function will complete only when the transaction is executed on chain.
        If the transaction fails, exception will be thrown.
        :param recipient: the address of recipient
        :param amount: the amount of TFC to transfer (in unit 10^-18)
        :param sender: the sender account
        """
        transaction = self._contract.functions.transfer(recipient, amount).buildTransaction({
            "from": sender.address
        })
        await self.send_transaction(transaction, sender)

    async def transfer_from(self, sender: str, recipient: str, amount: int, spender: Account):
        """
        Spender transfer the amount of TFC from sender to recipient.

        This is an async function will complete only when the transaction is executed on chain.
        If the transaction fails, exception will be thrown.
        :param sender: the sender address
        :param recipient: the address of recipient
        :param amount: the amount of TFC to transfer (in unit 10^-18)
        :param spender: the account which has the allowance to transfer TFC from the sender
        """
        transaction = self._contract.functions.transferFrom(sender, recipient, amount).buildTransaction({
            "from": spender.address
        })
        await self.send_transaction(transaction, spender)

    async def approve(self, spender: str, amount: int, owner: Account):
        """
        Approve the amount of TFC for spender to spend. (Give the allowance)
        :param spender: the spender address
        :param amount: the amount of TFC to approve (in unit 10^-18)
        :param owner: the owner account
        :return:
        """
        transaction = self._contract.functions.approve(spender, amount).buildTransaction({
            "from": owner.address
        })
        await self.send_transaction(transaction, owner)
