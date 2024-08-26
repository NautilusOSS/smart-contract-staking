from collections.abc import Generator
import pytest
from algopy_testing import AlgopyTestContext, algopy_testing_context
from unittest.mock import MagicMock
import typing
import algopy
from contract import Airdrop

zero_address = algopy.arc4.Address(
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ"
)


class MockApp:
    def __init__(self, context: AlgopyTestContext):
        self.created_app = context.any.application()


class MockAbiCall:
    def __call__(
        self, *args: typing.Any, **_kwargs: typing.Any
    ) -> tuple[typing.Any, typing.Any]:
        return (MagicMock(),)

    def __getitem__(self, _item: object) -> typing.Self:
        return self


@pytest.fixture()
def context() -> Generator[AlgopyTestContext, None, None]:
    with algopy_testing_context() as ctx:
        yield ctx


@pytest.fixture()
def contract(context: AlgopyTestContext) -> Airdrop:  # noqa: ARG001
    context.set_template_var("PERIOD_SECONDS", 60)
    context.set_template_var("LOCKUP_DELAY", 12)
    context.set_template_var("VESTING_DELAY", 12)
    context.set_template_var("PERIOD_LIMIT", 5)
    context.set_template_var("MESSENGER_ID", 1)
    context.set_template_var("DISTRIBUTION_COUNT", 12)
    context.set_template_var("DISTRIBUTION_SECONDS", 60)
    return Airdrop()


def test_airdrop(contract: Airdrop):
    assert contract is not None
    assert contract.period_seconds == 60  # template variable
    assert contract.lockup_delay == 12  # template variable
    assert contract.vesting_delay == 12  # template variable
    assert contract.period_limit == 5  # template variable
    assert contract.messenger_id == 1
    assert contract.contract_version == 0
    assert contract.deployment_version == 0
    assert contract.period == 0
    assert contract.total == 0
    assert contract.funding == 0
    assert contract.deadline == 0
    assert contract.funder == zero_address
    assert contract.owner == zero_address
    assert contract.delegate == zero_address
    assert contract.initial == 0
    assert contract.parent_id == 0
    assert contract.stakeable == 1
    assert contract.updatable == 1


# TODO write test
# when called offline key reg and close out to creator address
def test_fundable_abort_funding():
    # see lockable close
    #   can be called by owner or funder before funding
    #   close offline to owner
    pass
