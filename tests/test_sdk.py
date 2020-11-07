import unittest

from web3 import Web3
from web3.types import TxReceipt

from jasmine_eth import SDK
from jasmine_eth.sdk import Account, _Web3Wrapper
from tests.utils import async_test


class AccountTests(unittest.TestCase):
    def setUp(self) -> None:
        self.web3 = Web3(Web3.HTTPProvider("http://localhost:8545"))

    def test_instantiate_account(self):
        private_key = "0x787ff27e287db81a926333f85bfedd67c497453a08b278afcea0fe9f4c0e235d"
        account = Account(self.web3, private_key)
        self.assertEqual(account.private_key, private_key)
        self.assertEqual(account.address, "0x29B2F1587BCF319eBB510284aFd552F995410C8a")


class Web3WrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.web3 = Web3(Web3.HTTPProvider("http://localhost:8545"))
        self.wrapper = _Web3Wrapper(self.web3)

    @async_test
    async def test_send_transaction(self):
        key = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"
        account = Account(self.web3, key)
        receipt: TxReceipt = await self.wrapper.send_transaction({
            "from": account.address,
            "to": account.address,
            "value": 0,
        }, account)
        self.assertEqual(receipt["from"], account.address)


class SDKTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sdk = SDK("http://localhost:8545")
        self.accounts = [Account(self.sdk.web3, private_key) for private_key in [
            "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d",
            "0x6cbed15c793ce57650b9877cf6fa156fbef513c4e6134f022a85b1ffdd59b2a1",
            "0x6370fd033278c143179d81c5526140625662b8daa446c22ee2d73db3707e620c",
        ]]

    def test_retrieve_account(self):
        key = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"
        account = self.sdk.retrieve_account(key)
        self.assertEqual(account.private_key, key)
        self.assertEqual(account.address, "0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1")

    def test_create_account(self):
        account = self.sdk.create_account()
        self.assertEqual(account.address, self.sdk.web3.eth.account.from_key(account.private_key).address)

    def test_balance_of(self):
        new_account = self.sdk.create_account()
        balance = self.sdk.balance_of(new_account.address)
        self.assertEqual(balance, 0)
        balance = self.sdk.balance_of(self.accounts[2].address)
        self.assertEqual(balance, 100000000000000000000)

    def test_eth_to_wei(self):
        wei = self.sdk.eth_to_wei(1)
        self.assertEqual(wei, 1000000000000000000)

    def test_wei_to_eth(self):
        eth = self.sdk.wei_to_eth(1000000000000000000)
        self.assertEqual(eth, 1)

    @async_test
    async def test_transfer(self):
        balance_before = self.sdk.balance_of(self.accounts[1].address)
        await self.sdk.transfer(self.accounts[1].address, self.sdk.eth_to_wei(1), self.accounts[0])
        balance_after = self.sdk.balance_of(self.accounts[1].address)
        self.assertEqual(balance_after - balance_before, self.sdk.eth_to_wei(1))

    @async_test
    async def test_deploy_tfc_manager(self):
        manager_address = await self.sdk.deploy_tfc_manager(self.accounts[0])
        code = self.sdk.web3.eth.getCode(manager_address)
        self.assertTrue(len(code.hex()) > 2)


class TFCManagerTests(unittest.TestCase):
    @classmethod
    @async_test
    async def setUp(cls) -> None:
        cls.sdk = SDK("http://localhost:8545")
        cls.accounts = [Account(cls.sdk.web3, private_key) for private_key in [
            "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d",
            "0x6cbed15c793ce57650b9877cf6fa156fbef513c4e6134f022a85b1ffdd59b2a1",
            "0x6370fd033278c143179d81c5526140625662b8daa446c22ee2d73db3707e620c",
        ]]
        manager_address = await cls.sdk.deploy_tfc_manager(cls.accounts[0])
        cls.manager = cls.sdk.get_tfc_manager(manager_address)
        tfc_address = cls.manager.tfc_token_address()
        cls.tfc = cls.sdk.get_tfc_token(tfc_address)

    def test_tfc_token_address(self):
        address = self.manager.tfc_token_address()
        code = self.sdk.web3.eth.getCode(address)
        self.assertTrue(len(code.hex()) > 2)

    @async_test
    async def test_claim_tfc(self):
        # invalid signature
        sig = "0x123456"
        try:
            await self.manager.claim_tfc(1, 0, sig, self.accounts[0])
            self.assertFalse(True)
        except Exception as e:
            self.assertIsNotNone(e)

        # wrong claimer
        sig = "0x6b04573d9a5b813e65b7afc77ca931bf1a5787ed1732622034355c75b39fe934194501f3431b2fed46581eaa486cdb636eebcb7f852d2105af4a4b53a25dd27e1c"
        try:
            await self.manager.claim_tfc(1, 0, sig, self.accounts[0])
            self.assertFalse(True)
        except Exception as e:
            self.assertIsNotNone(e)

        # successful
        sig = "0x6b04573d9a5b813e65b7afc77ca931bf1a5787ed1732622034355c75b39fe934194501f3431b2fed46581eaa486cdb636eebcb7f852d2105af4a4b53a25dd27e1c"
        try:
            balance = self.tfc.balance_of(self.accounts[1].address)
            self.assertEqual(balance, 0)
            await self.manager.claim_tfc(1, 0, sig, self.accounts[1])
            balance = self.tfc.balance_of(self.accounts[1].address)
            self.assertEqual(balance, 1)
        except Exception as e:
            self.assertIsNone(e)

        # used nonce
        sig = "0x6b04573d9a5b813e65b7afc77ca931bf1a5787ed1732622034355c75b39fe934194501f3431b2fed46581eaa486cdb636eebcb7f852d2105af4a4b53a25dd27e1c"
        try:
            await self.manager.claim_tfc(1, 0, sig, self.accounts[1])
        except Exception as e:
            self.assertIsNotNone(e)


class TFCTokenTests(unittest.TestCase):
    @classmethod
    @async_test
    async def setUpClass(cls) -> None:
        cls.sdk = SDK("http://localhost:8545")
        cls.accounts = [Account(cls.sdk.web3, private_key) for private_key in [
            "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d",
            "0x6cbed15c793ce57650b9877cf6fa156fbef513c4e6134f022a85b1ffdd59b2a1",
            "0x6370fd033278c143179d81c5526140625662b8daa446c22ee2d73db3707e620c",
        ]]
        manager_address = await cls.sdk.deploy_tfc_manager(cls.accounts[0])
        cls.manager = cls.sdk.get_tfc_manager(manager_address)
        tfc_address = cls.manager.tfc_token_address()
        cls.tfc = cls.sdk.get_tfc_token(tfc_address)
        # faucet 1e-18 TFC
        sig = "0x6b04573d9a5b813e65b7afc77ca931bf1a5787ed1732622034355c75b39fe934194501f3431b2fed46581eaa486cdb636eebcb7f852d2105af4a4b53a25dd27e1c"
        await cls.manager.claim_tfc(1, 0, sig, cls.accounts[1])
        balance = cls.tfc.balance_of(cls.accounts[1].address)
        assert balance == 1

    def test_properties(self):
        self.assertEqual(self.tfc.name, "TFCToken")
        self.assertEqual(self.tfc.symbol, "TFC")
        self.assertEqual(self.tfc.total_supply, 1)
        self.assertEqual(self.tfc.decimals, 18)

    def test_balance_of(self):
        self.assertEqual(self.tfc.balance_of(self.accounts[0].address), 0)
        self.assertEqual(self.tfc.balance_of(self.accounts[1].address), 1)

    def test_allowance(self):
        self.assertEqual(self.tfc.allowance(self.accounts[0].address, self.accounts[1].address), 0)

    @async_test
    async def test_transfer(self):
        # transfer from accounts[1] to accounts[0]
        try:
            await self.tfc.transfer(self.accounts[0].address, 1, self.accounts[1])
            balance = self.tfc.balance_of(self.accounts[0].address)
            self.assertEqual(balance, 1)
            balance = self.tfc.balance_of(self.accounts[1].address)
            self.assertEqual(balance, 0)
        except Exception as e:
            self.assertIsNone(e)

        # accounts[1] approve accounts[1]
        try:
            await self.tfc.approve(self.accounts[1].address, 1, self.accounts[0])
            allowance = self.tfc.allowance(self.accounts[0].address, self.accounts[1].address)
            self.assertEqual(allowance, 1)
        except Exception as e:
            self.assertIsNone(e)

        # transfer from accounts[0] to accounts[1]
        try:
            await self.tfc.transfer_from(self.accounts[0].address, self.accounts[1].address, 1, self.accounts[1])
            balance = self.tfc.balance_of(self.accounts[0].address)
            self.assertEqual(balance, 0)
            balance = self.tfc.balance_of(self.accounts[1].address)
            self.assertEqual(balance, 1)
        except Exception as e:
            self.assertIsNone(e)
