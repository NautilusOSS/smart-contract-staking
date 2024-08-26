from collections.abc import Generator
import pytest
from algopy_testing import AlgopyTestContext, algopy_testing_context
import algopy
from unittest.mock import patch, MagicMock
import typing
from contract import Fundable

zero_address = algopy.arc4.Address(
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ"
)

application_address = "OKSDOCOXVGMBXQ5TP5YA4VWTZWZJLJP3OMIILPHMHGHURUFE2Q3JP62QNU"


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
def contract(context: AlgopyTestContext) -> Fundable:  # noqa: ARG001
    return Fundable()


def test_fundable(contract: Fundable, context: AlgopyTestContext):
    """
    Test the Fundable contract
    """
    assert contract is not None
    assert contract.funder == zero_address
    assert contract.funding == 0
    assert contract.total == 0


def test_fundable_fill(contract: Fundable, context: AlgopyTestContext):
    """
    Test the fill function
    Must be called by funder
    """
    contract.funder = context.default_sender
    app = context.ledger.get_app(contract)
    extra_payment = context.any.txn.payment(
        amount=99999,
        sender=context.default_sender,
        receiver=app.address,
    )
    deferred_call = context.txn.defer_app_call(
        contract.fill,
    )
    with patch("algopy.arc4.abi_call", MockAbiCall()):
        with context.txn.create_group([extra_payment, deferred_call]):
            deferred_call.submit()
    # contract.total += extra_payment.amount
    # TODO test state after abi call


# TODO write test
# when called new funding becomes funding
def test_fundable_set_funding():
    pass


# TODO write test
# when called offline key reg and close out to creator address
def test_fundable_abort_funding():
    # see lockable close
    #   close offline to funder
    pass
