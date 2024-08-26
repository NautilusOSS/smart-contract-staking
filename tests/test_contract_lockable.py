from collections.abc import Generator
import pytest
from algopy_testing import AlgopyTestContext, algopy_testing_context
import algopy
from contract import Lockable

zero_address = algopy.arc4.Address(
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ"
)

application_address = "OKSDOCOXVGMBXQ5TP5YA4VWTZWZJLJP3OMIILPHMHGHURUFE2Q3JP62QNU"


@pytest.fixture()
def context() -> Generator[AlgopyTestContext, None, None]:
    with algopy_testing_context() as ctx:
        yield ctx


@pytest.fixture()
def contract(context: AlgopyTestContext) -> Lockable:  # noqa: ARG001
    context.set_template_var("PERIOD_SECONDS", 60)
    context.set_template_var("LOCKUP_DELAY", 12)
    context.set_template_var("VESTING_DELAY", 12)
    context.set_template_var("PERIOD_LIMIT", 5)
    context.set_template_var("DISTRIBUTION_COUNT", 12)
    context.set_template_var("DISTRIBUTION_SECONDS", 60)
    return Lockable()


def test_lockable(contract: Lockable, context: AlgopyTestContext):
    """
    Test the Lockable contract
    """
    assert contract is not None
    assert contract.owner == zero_address
    assert contract.period == 0
    assert contract.initial == 0
    assert contract.deadline == 0
    assert contract.period_seconds == 60
    assert contract.lockup_delay == 12
    assert contract.vesting_delay == 12
    assert contract.period_limit == 5
    assert contract.funder == zero_address
    assert contract.funding == 0
    assert contract.total == 0


def test_lockable_transfer(contract: Lockable, context: AlgopyTestContext):
    """
    Test the preconfigure function
    Must be called before setup by creator
    """
    # TODO test abi_call by creator
    new_period = context.any.arc4.uint64()
    new_deadline = context.any.arc4.uint64()
    assert contract.period == 0
    assert contract.deadline == 0
    contract.preconfigure(new_period, new_deadline)
    assert contract.period == new_period
    assert contract.deadline == new_deadline


def test_lockable_set_vesting_delay(contract: Lockable, context: AlgopyTestContext):
    """
    Test the set_vesting_delay function
    Must be called before setup by creator
    """
    # TODO test abi_call by creator
    new_vesting_delay = context.any.arc4.uint64()
    assert contract.vesting_delay == 12
    contract.set_vesting_delay(new_vesting_delay)
    assert contract.vesting_delay == new_vesting_delay


def test_lockable_set_total(contract: Lockable, context: AlgopyTestContext):
    """
    Test the set_lockup_delay function
    Must be called before setup by creator
    """
    # TODO test abi_call by creator
    new_total = context.any.arc4.uint64()
    assert contract.total == 0
    contract.set_total(new_total)
    assert contract.total == new_total


def test_lockable_setup(contract: Lockable, context: AlgopyTestContext):
    """
    Test the setup function
    Must be called by creator
    """
    # TODO test abi_call by creator
    new_owner = context.any.arc4.address()
    new_funder = context.any.arc4.address()
    new_initial = context.any.arc4.uint64()
    contract.setup(new_owner, new_funder, new_initial)
    assert contract.owner == new_owner
    assert contract.funder == new_funder
    assert contract.initial == new_initial


def test_lockable_configure(contract: Lockable, context: AlgopyTestContext):
    """
    Test the configure function
    Must be called by owner
    """
    contract.owner = context.default_sender
    contract.deadline = context.any.uint64(
        18446744073709551615
    )  # HACK to ensure future deadline
    assert contract.owner == context.default_sender
    new_period = context.any.arc4.uint64(min_value=0, max_value=5)
    contract.configure(new_period)
    assert contract.period == new_period


def test_lockable_withdraw(contract: Lockable, context: AlgopyTestContext):
    """
    Test the withdraw function
    Must be called by owner
    """
    account = algopy.Account(application_address)
    # Factory creation ensures min_balance is satisfied
    context.ledger.update_account(
        application_address, balance=algopy.Global.min_balance
    )
    contract.owner = context.default_sender
    assert contract.owner == context.default_sender
    # case 1: funding <= 0, total = 0, balance = 1mb, amount = 0
    assert contract.funding == 0
    return_value = contract.withdraw(algopy.arc4.UInt64(0))
    assert return_value == 0
    # case 2: funding <= 0, total = 1mb, balance = 2mb, amount = 0
    context.ledger.update_account(
        application_address, balance=algopy.Global.min_balance * 2
    )
    contract.total = algopy.Global.min_balance
    return_value = contract.withdraw(algopy.arc4.UInt64(0))
    assert return_value == algopy.Global.min_balance
    # case 3: funding <= 0, total = 1mb, balacne = 3mb, amount > 0
    context.ledger.update_account(
        application_address, balance=algopy.Global.min_balance * 3
    )
    assert account.balance == algopy.Global.min_balance * 3
    return_value = contract.withdraw(algopy.arc4.UInt64(algopy.Global.min_balance))
    payment_txn = context.txn.last_group.last_itxn.payment
    assert return_value == algopy.Global.min_balance
    assert payment_txn.amount == algopy.Global.min_balance
    # case 4: funding > 0, total = balance - 1mb, amount = 0
    context.ledger.set_block(index=1, seed=1, timestamp=1)
    contract.funding = 1
    contract.total = algopy.Global.min_balance * 9
    context.ledger.update_account(
        application_address, balance=algopy.Global.min_balance * 10
    )
    return_value = contract.withdraw(algopy.arc4.UInt64(0))
    assert return_value == algopy.Global.min_balance * 9
    # TODO test with different blocks


def test_lockable_close(contract: Lockable, context: AlgopyTestContext):
    ## must be called by owner
    contract.owner = context.default_sender
    contract.funding = algopy.UInt64(1)
    contract.total = algopy.UInt64(99990)
    contract.vesting_delay = algopy.UInt64(1)
    context.ledger.update_account(
        application_address, balance=99999 + algopy.Global.min_balance
    )
    account = algopy.Account(application_address)
    account_balance = 99999 + algopy.Global.min_balance
    assert account.balance == account_balance
    assert contract.owner.balance == 0
    # with context.txn.create_group(
    #     active_txn_overrides={
    #         "on_completion": algopy.OnCompleteAction.DeleteApplication
    #     },
    # ):
    contract.close()
    # TODO test nonparticipation itx
    payment_txn = context.txn.last_group.last_itxn.payment
    # TODO receiver is creator address
    # TODO amount is global min balance
    assert payment_txn.close_remainder_to == contract.owner
    # TODO close remaineder amount is balance before minus global min balance
    # TODO test outcome of close_remainder_to contract owner


def test_lockable_calculate_min_balance(contract: Lockable, context: AlgopyTestContext):
    """
    Test the calculate_min_balance function
    """
    pass
