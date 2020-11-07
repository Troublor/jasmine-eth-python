# Jasmine Project Ethereum SDK (Python)

This SDK provides the following functionalities: 
1. Create/retrieve new/existing Ethereum accounts
2. Transfer ETH and query ETH balance
3. Deploy TFCManager smart contracts along with TFCToken ERC20 contracts.
4. Claim TFC token through TFCManager using a signature signed by the TFCManager deployer account.
Signing functionality is not provided in this SDK by now. 
Alternatively, use [Golang SDK](https://github.com/Troublor/jasmine-eth-go) or [JavaScript SDK](https://github.com/Troublor/jasmine-eth-go).
5. Perform [ERC20 standard](https://eips.ethereum.org/EIPS/eip-20) actions on TFC ERC20 token, including transfer, transferFrom and approve.

## Installation

Requires Python `>=3.6`

```bash
pip install jasmine_eth
```

## Usage

Instantiate an SDK object using Ethereum endpoint: 
```python
from jasmine_eth import SDK
sdk = SDK("http://localhost:8545")
```

Create/retrieve an Ethereum account
```python
private_key = "0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d"
account = sdk.retrieve_account(private_key) # retrieve account using private key
account = sdk.create_account() # create a new account
print(account.address) # Ethereum address
print(account.private_key) # account private key
```

Deploy TFCManager contract, which will implicitly deploy TFCToken ERC20 contract. 
```python
# make sure the account have enough ETH balance to deploy contracts
manager_address = await sdk.deploy_tfc_manager(account) 
```

Get the TFCManager contract instance and TFCToken contract instance:
```python
manager = sdk.get_tfc_manager(manager_address)
tfc_erc20_address = manager.tfc_token_address()
tfc = sdk.get_tfc_token(tfc_erc20_address)
```

Claim TFC: 
```python
amount: int = 1000000000000000000 # 1 TFC
nonce: int = 0
signature: str = "0x6b04573d9a5b813e65b7afc77ca931bf1a5787ed1732622034355c75b39fe934194501f3431b2fed46581eaa486cdb636eebcb7f852d2105af4a4b53a25dd27e1c"
# account claim the amount of TFC using signature signed by TFCManager deployer
await manager.claim_tfc(amount, nonce, signature, account)
```

Get TFC balance
```python
balance: int = tfc.balance_of(account.address)
```

Transfer TFC
```python
amount: int = 1000000000000000000 # 1 TFC
await tfc.transfer(recipient_account.address, amount, account)
await tfc.approve(spender_account.address, amount, account)
await tfc.transfer_from(account.address, recipient_account.address, amount, spender_account)
```

**Note: All methods that involve sending transactions are `async` functions and should be awaited.**