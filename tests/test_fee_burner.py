from tests.tests_helpers import *
from tests.omg_contract_codes import OMGTOKEN_CONTRACT_ABI, OMGTOKEN_CONTRACT_BYTECODE


DEAD_ADDRESS = '0x000000000000000000000000000000000000dEaD'

# TODO: abandon ganache-cli


def mint_token(w3, token, owner, users):
    for user in users:
        tx_hash = token.functions.mint(user, HUGE_AMOUNT).transact()
        w3.eth.waitForTransactionReceipt(tx_hash)

    w3.eth.waitForTransactionReceipt(
        token.functions.finishMinting().transact({'from': owner})
    )


@pytest.fixture()
def omg_token(w3, operator, accounts):
    # NOTE: default account is set to the operator, so it automagically deploys as if deployed by the operator
    contract_interface = {'abi': OMGTOKEN_CONTRACT_ABI, 'bin': OMGTOKEN_CONTRACT_BYTECODE}
    address = deploy_contract(w3, contract_interface)

    omg_token_contract = w3.eth.contract(
        address=address,
        abi=contract_interface['abi']
    )

    mint_token(w3, omg_token_contract, operator, accounts[0:3])

    w3.eth.waitForTransactionReceipt(
        omg_token_contract.functions.transferOwnership(DEAD_ADDRESS).transact()
    )

    return omg_token_contract


@pytest.fixture()
def other_token(w3, operator, accounts):
    compiled_erc20_token = compile_source_file('./tests/sample_erc20_contract/MintableToken.sol')
    contract_interface = compiled_erc20_token['./tests/sample_erc20_contract/MintableToken.sol:MintableToken']

    address = deploy_contract(w3, contract_interface)

    erc20_token = w3.eth.contract(
        address=address,
        abi=contract_interface['abi']
    )

    mint_token(w3, erc20_token, operator, accounts[0:3])

    w3.eth.waitForTransactionReceipt(
        erc20_token.functions.transferOwnership(DEAD_ADDRESS).transact()
    )

    return erc20_token


@pytest.fixture()
def fee_burner(w3, provider, omg_token):
    compiled_fee_burner = compile_source_file('./contracts/FeeBurner.sol')
    contract_interface = compiled_fee_burner['./contracts/FeeBurner.sol:FeeBurner']

    address = deploy_contract(w3, contract_interface, omg_token.address)
    fee_burner_contract = w3.eth.contract(
        address=address,
        abi=contract_interface['abi']
    )

    return fee_burner_contract


# TESTS

def test_add_support_for_some_token(fee_burner, other_token, operator):
    # when: an operator adds support for some token
    fee_burner.functions.addSupportFor(other_token.address, 1, 123).transact()

    # then: this token is supported
    assert fee_burner.functions.getExchangeRate(other_token.address).call()[-2:] == [1, 123]


def test_add_support_for_a_token_by_a_non_operator(fee_burner, non_operator, other_token):
    # when: a non operator tries to add support for a token
    # then: an error occurs
    with RaisesTransactionFailed():
        fee_burner.functions.addSupportFor(other_token.address, 1, 123).transact({'from': non_operator})


def test_failure_when_setting_invalid_initial_rate(fee_burner, operator, other_token):
    # when: an operator tries to set invalid nominator
    # then: an error occurs
    with RaisesTransactionFailed():
        fee_burner.functions.addSupportFor(other_token.address, 0, 123).transact()

    # when: an operator tries to set invalid nominator
    # then: an error occurs
    with RaisesTransactionFailed():
        fee_burner.functions.addSupportFor(other_token.address, 1, 0).transact()


def test_failure_when_adding_already_supported_token(fee_burner, other_token):
    # given: added support for some token
    fee_burner.functions.addSupportFor(other_token.address, 1, 1).transact()

    # when: the operator tries to add it once again
    # then: an error occurs
    with RaisesTransactionFailed():
        fee_burner.functions.addSupportFor(other_token.address, 1, 1).transact()


def test_exchange_omg_for_some_token(non_operator, omg_token, fee_burner, other_token):
    # given: added support for some token and
    fee_burner.functions.addSupportFor(other_token.address, 1, 1).transact()
    other_token.functions.transfer(fee_burner.address, SMALL_AMOUNT).transact()

    # given: a user adds adds allowance on OMG contract and user has some initial tokens
    omg_token.functions.approve(fee_burner.address, SMALL_AMOUNT).transact({'from': non_operator})
    user_initial_balance = other_token.functions.balanceOf(non_operator).call()

    # when: the user sends an exchange demand OMG for other token at rate 1,1 (initial rate)
    fee_burner.functions.exchange(other_token.address, 1, 1, 1, 1).transact({'from': non_operator})

    # then: user has received token and OMGs have been burnt
    assert omg_token.functions.balanceOf(DEAD_ADDRESS).call() == 1
    assert other_token.functions.balanceOf(non_operator).call() == user_initial_balance + 1


def test_exchange_omg_for_ether(w3, non_operator, omg_token, fee_burner):
    # given: a user adds adds allowance on OMG contract and user has some initial tokens
    fee_burner.transact().addSupportFor(ZERO_ADDRESS, 1, 1)
    omg_token.functions.approve(fee_burner.address, HUGE_AMOUNT).transact({'from': non_operator})
    w3.eth.sendTransaction({'to': fee_burner.address, 'value': 10**18})

    user_initial_balance = w3.eth.getBalance(non_operator)

    # when: the user sends an exchange demand OMG for other token at rate 1,1 (initial rate)
    fee_burner.functions.exchange(ZERO_ADDRESS, 1, 1, 10**18, 10**18).transact({'from': non_operator})

    # then: user has received token and OMGs have been burnt
    assert omg_token.functions.balanceOf(DEAD_ADDRESS).call() == 10**18
    assert w3.eth.getBalance(non_operator) > user_initial_balance
    assert w3.eth.getBalance(non_operator) <= user_initial_balance + 10**18


def test_exchange_when_user_offers_more_omgs_then_needed(w3, non_operator, omg_token, fee_burner, other_token):
    # given: added support for some token and
    fee_burner.functions.addSupportFor(other_token.address, 1, 1).transact()
    other_token.functions.transfer(fee_burner.address, SMALL_AMOUNT).transact()

    # given: a user adds adds allowance on OMG contract and user has some initial tokens
    omg_token.functions.approve(fee_burner.address, HUGE_AMOUNT).transact({'from': non_operator})
    user_initial_balance = other_token.functions.balanceOf(non_operator).call()

    # when: the user sends offer at valid rate, but sends to much OMGs
    fee_burner.functions.exchange(other_token.address, 1, 1, 200, 1).transact({'from': non_operator})

    # then: the transaction was valid and tokens were transferred
    assert omg_token.functions.balanceOf(DEAD_ADDRESS).call() == 200
    assert other_token.functions.balanceOf(non_operator).call() == user_initial_balance + 1


def test_exchange_at_invalid_rate(non_operator, omg_token, fee_burner, other_token):
    # given: added support for some token and
    fee_burner.functions.addSupportFor(other_token.address, 1, 1).transact()
    other_token.functions.transfer(fee_burner.address, SMALL_AMOUNT).transact()

    # given: a user adds adds allowance on OMG contract and user has some initial tokens
    omg_token.functions.approve(fee_burner.address, SMALL_AMOUNT).transact({'from': non_operator})

    # when: the user sends an exchange demand OMG for other token at rate 2,1 (not current rate)
    # then: error
    with RaisesTransactionFailed():
        fee_burner.functions.exchange(other_token.address, 2, 1, 2, 1).transact({'from': non_operator})

    # when: the user sends an exchange demand OMG for other token at valid rate, but amounts aren't at this rate
    # then: error
    with RaisesTransactionFailed():
        fee_burner.functions.exchange(other_token.address, 1, 1, 1, 2).transact({'from': non_operator})


def test_exchange_when_user_has_not_allowed_transfer(non_operator, omg_token, fee_burner, other_token):
    # given: added support for some token
    fee_burner.functions.addSupportFor(other_token.address, 1, 1).transact()
    other_token.functions.transfer(fee_burner.address, SMALL_AMOUNT).transact()

    # when: user sends an exchange demand not having allowed for the transfer
    # then: error
    with RaisesTransactionFailed():
        fee_burner.functions.exchange(other_token.address, 1, 1, 1, 1).transact({'from': non_operator})

    assert omg_token.functions.balanceOf(DEAD_ADDRESS).call() == 0
    assert other_token.functions.balanceOf(fee_burner.address).call() == SMALL_AMOUNT


def test_exchange_when_user_does_not_have_funds(accounts, omg_token, fee_burner, other_token):

    user = accounts[5]

    # given: added support for some token and
    fee_burner.functions.addSupportFor(other_token.address, 1, 1).transact()
    other_token.functions.transfer(fee_burner.address, SMALL_AMOUNT).transact()

    # given: a user adds adds allowance on OMG contract
    omg_token.functions.approve(fee_burner.address, SMALL_AMOUNT).transact({'from': user})

    # when: user sends an exchange demand not having allowed for the transfer
    # then: error
    with RaisesTransactionFailed():
        fee_burner.functions.exchange(other_token.address, 1, 1, 1, 1).transact({'from': user})

    assert omg_token.functions.balanceOf(DEAD_ADDRESS).call() == 0
    assert other_token.functions.balanceOf(fee_burner.address).call() == SMALL_AMOUNT


def test_exchange_when_fee_burner_does_not_have_funds(non_operator, omg_token, fee_burner, other_token):
    # given: added support for some token and
    fee_burner.functions.addSupportFor(other_token.address, 1, 1).transact()

    # given: a user adds adds allowance on OMG contract and user has some initial tokens
    omg_token.functions.approve(fee_burner.address, SMALL_AMOUNT).transact({'from': non_operator})
    user_initial_balance = other_token.functions.balanceOf(non_operator).call()

    # when: the user sends an exchange demand OMG for other token at rate 1,1 (initial rate),
    # then: error
    with RaisesTransactionFailed():
        fee_burner.functions.exchange(other_token.address, 1, 1, 1, 1).transact({'from': non_operator})

    assert other_token.functions.balanceOf(non_operator).call() == user_initial_balance


def test_set_new_ether_exchange_rate(fee_burner, w3, provider):
    # given: initial exchange rate
    fee_burner.transact().addSupportFor(ZERO_ADDRESS, 1, 1)
    mine_blocks(provider, fee_burner.call().NEW_RATE_MATURITY_MARGIN() + 1)
    initial_rate = fee_burner.functions.getExchangeRate(ZERO_ADDRESS).call()

    # when: an operator changes Ether exchange rate
    fee_burner.functions.setExchangeRate(ZERO_ADDRESS, 11, 11).transact()

    # then: exchange rate is set and the old one is still active
    assert fee_burner.functions.getExchangeRate(ZERO_ADDRESS).call() == [w3.eth.blockNumber, 11, 11]
    assert fee_burner.functions.getPreviousExchangeRate(ZERO_ADDRESS).call() == initial_rate


def test_change_exchange_rate_by_a_non_operator(fee_burner, accounts, non_operator):
    # given: initial exchange rate
    initial_rate = fee_burner.functions.getExchangeRate(ZERO_ADDRESS).call()

    # when: a user tries to set an new exchange rate
    with RaisesTransactionFailed():
        fee_burner.functions.setExchangeRate(ZERO_ADDRESS, 1, 1).transact({'from': non_operator})

    # then: rate has not changed
    assert fee_burner.functions.getExchangeRate(ZERO_ADDRESS).call() == initial_rate


def test_set_invalid_exchange_rate(fee_burner, operator):

    # when: the operator tries to set nominator to 0, expect error
    with RaisesTransactionFailed():
        fee_burner.functions.setExchangeRate(ZERO_ADDRESS, 0, 1).transact()

    # when: the operator tries to set denominator to 0, expect error
    with RaisesTransactionFailed():
        fee_burner.functions.setExchangeRate(ZERO_ADDRESS, 1, 0).transact()


def test_events_emission_when_adding_support_for_a_token(w3, fee_burner, other_token):
    event_filter = fee_burner.events.ExchangeRateChanged.createFilter(fromBlock='latest')
    # when: operator adds support for a new token
    fee_burner.functions.addSupportFor(other_token.address, 1, 123).transact()

    # then: ExchangeRateChanged event was emitted
    emitted_events = event_filter.get_new_entries()

    assert len(emitted_events) == 1
    assert emitted_events[0]['args']['token'] == other_token.address
    assert emitted_events[0]['args']['blockNo'] == w3.eth.blockNumber
    assert emitted_events[0]['args']['nominator'] == 1
    assert emitted_events[0]['args']['denominator'] == 123


def test_events_emission_when_changing_rate(w3, provider, fee_burner, other_token):
    fee_burner.transact().addSupportFor(ZERO_ADDRESS, 1, 1)
    mine_blocks(provider, fee_burner.call().NEW_RATE_MATURITY_MARGIN() + 1)
    event_filter = fee_burner.events.ExchangeRateChanged.createFilter(fromBlock='latest')

    # when: exchange rate is changed
    fee_burner.functions.setExchangeRate(ZERO_ADDRESS, 11, 12).transact()

    # then: ExchangeRateChanged event was emitted
    emitted_events = event_filter.get_new_entries()

    assert len(emitted_events) == 1
    assert emitted_events[0]['args']['blockNo'] == w3.eth.blockNumber
    assert emitted_events[0]['args']['nominator'] == 11
    assert emitted_events[0]['args']['denominator'] == 12
    assert emitted_events[0]['args']['token'] == ZERO_ADDRESS


def test_set_new_rate_of_an_unsupported_token(fee_burner, operator, other_token):
    # when: the operator tries to set a new exchange rate to a non existent token
    # then: expect error
    with RaisesTransactionFailed():
        fee_burner.functions.setExchangeRate(other_token.address, 1, 1).transact()


def test_setting_new_rate_when_maturity_period_has_not_passed(provider, fee_burner):
    # given: pending exchange rate
    fee_burner.transact().addSupportFor(ZERO_ADDRESS, 1, 1)
    mine_blocks(provider, fee_burner.call().NEW_RATE_MATURITY_MARGIN() + 1)
    fee_burner.functions.setExchangeRate(ZERO_ADDRESS, 11, 11).transact()

    # when: the operator tires to change the rate one more
    # then: expect error
    with RaisesTransactionFailed():
        fee_burner.functions.setExchangeRate(ZERO_ADDRESS, 22, 22).transact()


def test_setting_new_rate_when_maturity_period_has_passed(w3, provider, fee_burner):
    # given: pending exchange rate
    fee_burner.transact().addSupportFor(ZERO_ADDRESS, 1, 1)
    mine_blocks(provider, fee_burner.call().NEW_RATE_MATURITY_MARGIN() + 1)
    fee_burner.functions.setExchangeRate(ZERO_ADDRESS, 11, 22).transact()
    changed_rate = fee_burner.functions.getExchangeRate(ZERO_ADDRESS).call()

    # when: maturity period has come
    mine_blocks(provider, fee_burner.functions.NEW_RATE_MATURITY_MARGIN().call() + 1)
    block_no = w3.eth.blockNumber

    # then: operator can once more change the exchange rate
    fee_burner.functions.setExchangeRate(ZERO_ADDRESS, 22, 33).transact()
    assert fee_burner.functions.getExchangeRate(ZERO_ADDRESS).call() == [block_no + 1, 22, 33]
    assert fee_burner.functions.getPreviousExchangeRate(ZERO_ADDRESS).call() == changed_rate


def test_during_maturity_period_both_rates_should_be_valid(provider, non_operator, fee_burner, other_token, omg_token):
    # given: pending exchange rate, set allowances and non-zero balances
    fee_burner.functions.addSupportFor(other_token.address, 1, 1).transact()
    mine_blocks(provider, fee_burner.functions.NEW_RATE_MATURITY_MARGIN().call() + 1)

    fee_burner.functions.setExchangeRate(other_token.address, 2, 1).transact()

    other_token.functions.transfer(fee_burner.address, 3*SMALL_AMOUNT).transact()
    omg_token.functions.approve(fee_burner.address, HUGE_AMOUNT).transact({'from': non_operator})

    # then: both rates are valid
    fee_burner.functions.exchange(other_token.address, 1, 1, 1, 1).transact({'from': non_operator})
    fee_burner.functions.exchange(other_token.address, 2, 1, 2, 1).transact({'from': non_operator})

    assert omg_token.functions.balanceOf(DEAD_ADDRESS).call() == 3


def test_after_maturity_period_only_new_rate_is_valid \
 \
    (provider, operator, non_operator, fee_burner, omg_token, other_token):

    # given: pending exchange rate, set allowances and non-zero balances
    fee_burner.functions.addSupportFor(other_token.address, 1, 1).transact()
    mine_blocks(provider, fee_burner.functions.NEW_RATE_MATURITY_MARGIN().call() + 1)

    fee_burner.functions.setExchangeRate(other_token.address, 2, 1).transact()

    other_token.functions.transfer(fee_burner.address, 3*SMALL_AMOUNT).transact()
    omg_token.functions.approve(fee_burner.address, HUGE_AMOUNT).transact({'from': non_operator})

    # when: maturity period has come
    mine_blocks(provider, fee_burner.functions.NEW_RATE_MATURITY_MARGIN().call() + 1)

    # then: old rate is invalid
    with RaisesTransactionFailed():
        fee_burner.functions.exchange(other_token.address, 1, 1, 1, 1).transact({'from': non_operator})

    # then: new rate is valid
    fee_burner.functions.exchange(other_token.address, 2, 1, 2, 1).transact({'from': non_operator})

    assert omg_token.functions.balanceOf(DEAD_ADDRESS).call() == 2


@pytest.mark.parametrize("nominator, denominator, omg_amount, token_amount", [
    (1, 1, 1, 1),

    (1, 1, 2, 1),
    (1, 1, 1, 2),

    (3, 4, 1, 1),
    (4, 3, 1, 1),
    (3, 4, 6, 7),
    (4, 3, 7, 6),

    (5, 7, 7, 10),
    (5, 7, 8, 10),
    (7, 5, 10, 7),
    (7, 5, 10, 8),

    (3, 4, 17, 24),
    (3, 4, 19, 24),
    (4, 3, 24, 17),
    (4, 3, 24, 19),

    (121, 73, 6, 4),
    (73, 121, 4, 6),
    (121, 73, 7, 4),
    (73, 121, 4, 7),
])
def test_exchange_with_different_rates_and_amounts\
                (fee_burner, other_token, omg_token, non_operator, nominator, denominator, omg_amount, token_amount):

    # given: added support for some token and
    fee_burner.functions.addSupportFor(other_token.address, nominator, denominator).transact()
    other_token.functions.transfer(fee_burner.address, HUGE_AMOUNT).transact()

    # given: a user adds adds allowance on OMG contract and user has some initial tokens
    omg_token.functions.approve(fee_burner.address, HUGE_AMOUNT).transact({'from': non_operator})
    user_initial_balance = other_token.functions.balanceOf(non_operator).call()

    # when: the user sends an exchange demand OMG for other token at given

    failed = False

    try:
        fee_burner.functions.exchange(other_token.address, nominator, denominator, omg_amount, token_amount)\
            .transact({'from': non_operator})
        assert omg_token.functions.balanceOf(DEAD_ADDRESS).call() == omg_amount
        assert other_token.functions.balanceOf(non_operator).call() == user_initial_balance + token_amount
    except ValueError:
        failed = True
    finally:
        assert ((omg_amount / token_amount) < (nominator / denominator)) == failed
