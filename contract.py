import typing
from algopy import (
    ARC4Contract,
    Account,
    Bytes,
    Global,
    OnCompleteAction,
    TemplateVar,
    Txn,
    UInt64,
    arc4,
    itxn,
    op,
    subroutine,
)
from contract_mab import calculate_mab_pure
from utils import require_payment, get_available_balance, close_offline_on_delete

Bytes32: typing.TypeAlias = arc4.StaticArray[arc4.Byte, typing.Literal[32]]
Bytes64: typing.TypeAlias = arc4.StaticArray[arc4.Byte, typing.Literal[64]]


class PartKeyInfo(arc4.Struct):
    address: arc4.Address
    vote_key: Bytes32
    selection_key: Bytes32
    vote_first: arc4.UInt64
    vote_last: arc4.UInt64
    vote_key_dilution: arc4.UInt64
    state_proof_key: Bytes64


class MessagePartKeyInfo(arc4.Struct):
    who: arc4.Address
    partkey: PartKeyInfo


##################################################
# Ownable
#   allows contract to be owned
##################################################


class OwnableInterface(ARC4Contract):
    """
    Interface for all abimethods operated by owner.
    """

    def __init__(self) -> None:
        self.owner = Account()

    @arc4.abimethod
    def transfer(self, new_owner: arc4.Address) -> None:
        """
        Transfer ownership of the contract to a new owner.
        """
        pass


class Ownable(OwnableInterface):
    def __init__(self) -> None:
        super().__init__()

    @arc4.abimethod
    def transfer(self, new_owner: arc4.Address) -> None:
        assert Txn.sender == self.owner, "must be owner"
        self.owner = new_owner.native


##################################################
# Fundable
#   allows contract to be funded
##################################################


class FundableInterface(ARC4Contract):
    """
    Interface for all methods called by funder.

    This class defines the basic interface for all types of vehicles,
    including methods for starting and stopping the engine. Subclasses
    must implement these methods to provide concrete behavior

    Global State:
    - funder, who funded the contract
    - funding, when funded
    """

    def __init__(self) -> None:
        self.funder = Account()
        self.funding = UInt64()
        self.total = UInt64()

    @arc4.abimethod
    def fill(self) -> None:
        """
        Add funds to the contract and increments total.
        """
        pass

    @arc4.abimethod
    def set_funding(self, funding: arc4.UInt64) -> None:
        """
        Extend the funding period. Should be called before the funding deadline.
        Should not allow setting the funding deadline back. Can be called multiple
        times.
        """
        pass

    @arc4.abimethod(allow_actions=[OnCompleteAction.DeleteApplication])
    def abort_funding(self) -> None:
        """
        Abort funding. Must be called when funding not initialized.
        """
        pass


class Fundable(FundableInterface):
    def __init__(self) -> None:
        super().__init__()

    @arc4.abimethod
    def fill(self) -> None:
        #########################################
        assert Txn.sender == self.funder, "must be funder"
        #########################################
        payment_amount = require_payment(self.funder)
        assert payment_amount >= UInt64(0), "payment amount accurate"
        #########################################
        self.total = self.total + payment_amount

    @arc4.abimethod
    def set_funding(self, funding: arc4.UInt64) -> None:
        #########################################
        assert Txn.sender == self.funder, "must be funder"
        #########################################
        assert (
            self.funding == UInt64(0) or self.funding > Global.latest_timestamp
        ), "funding not be initialized or can be extended"
        #########################################
        self.funding = funding.native

    @arc4.abimethod(allow_actions=[OnCompleteAction.DeleteApplication])
    def abort_funding(self) -> None:
        #########################################
        assert Txn.sender == self.funder, "must be funder"
        #########################################
        assert self.funding == UInt64(0)
        #########################################
        close_offline_on_delete(self.funder)


##################################################
# Stakeable
#   allows contract to participate in consensus,
#   stake
##################################################


class StakeableInterface(ARC4Contract):
    """
    Interface for all abimethods of stakeable contract.
    """

    def __init__(self) -> None:
        self.delegate = Account()
        self.stakeable = bool(1)

    @arc4.abimethod
    def set_delegate(self, delegate: arc4.Address) -> None:
        """
        Set delegate.
        """
        pass

    @arc4.abimethod
    def participate(
        self,
        vote_k: Bytes32,
        sel_k: Bytes32,
        vote_fst: arc4.UInt64,
        vote_lst: arc4.UInt64,
        vote_kd: arc4.UInt64,
        sp_key: Bytes64,
    ) -> None:
        """
        Participate in consensus.
        """
        pass


class Stakeable(StakeableInterface, OwnableInterface):
    def __init__(self) -> None:
        # ownable state
        self.owner = Account()
        # stakeable state
        self.delegate = Account()  # zero address
        self.stakeable = bool(1)  # 1 (Default unlocked)

    @arc4.abimethod
    def set_delegate(self, delegate: arc4.Address) -> None:
        assert Txn.sender == self.owner, "must be owner"
        self.delegate = delegate.native

    @arc4.abimethod
    def participate(
        self,
        vote_k: Bytes32,
        sel_k: Bytes32,
        vote_fst: arc4.UInt64,
        vote_lst: arc4.UInt64,
        vote_kd: arc4.UInt64,
        sp_key: Bytes64,
    ) -> None:
        ###########################################
        assert (
            Txn.sender == self.owner or Txn.sender == self.delegate
        ), "must be owner or delegate"
        ###########################################
        key_reg_fee = Global.min_txn_fee
        # require payment of min fee to prevent draining
        assert require_payment(Txn.sender) == key_reg_fee, "payment amout accurate"
        ###########################################
        itxn.KeyRegistration(
            vote_key=vote_k.bytes,
            selection_key=sel_k.bytes,
            vote_first=vote_fst.native,
            vote_last=vote_lst.native,
            vote_key_dilution=vote_kd.native,
            state_proof_key=sp_key.bytes,
            fee=key_reg_fee,
        ).submit()


##################################################
# Deleteable
#   allows contract to be deleted
##################################################


class DeleteableInterface(ARC4Contract):
    """
    Interface for all abimethods of deletable contract.
    """

    def __init__(self) -> None:
        self.deletable = bool(1)

    @arc4.abimethod
    def on_delete(self) -> None:
        """
        Delete the contract.
        """
        pass


class Deleteable(DeleteableInterface):
    def __init__(self) -> None:
        super().__init__()

    @arc4.baremethod(allow_actions=["DeleteApplication"])
    def on_delete(self) -> None:
        ##########################################
        # WARNING: This app can be deleted by the creator (Development)
        ##########################################
        assert Txn.sender == Global.creator_address, "must be creator"
        assert self.deletable == UInt64(1), "not approved"
        ##########################################


##################################################
# Upgradeable
#   allows contract to be updated
##################################################


class UpgradeableInterface(ARC4Contract):
    """
    Interface for all abimethods of upgradeable contract.
    """

    def __init__(self) -> None:
        self.contract_version = UInt64()
        self.deployment_version = UInt64()
        self.updatable = bool(1)

    @arc4.abimethod
    def set_version(
        self, contract_version: arc4.UInt64, deployment_version: arc4.UInt64
    ) -> None:
        """
        Set contract and deployment version.
        """
        pass

    @arc4.abimethod
    def on_update(self) -> None:
        """
        On update.
        """
        pass

    @arc4.abimethod
    def approve_update(self, approval: arc4.Bool) -> None:
        """
        Approve update.
        """
        pass


class Upgradeable(UpgradeableInterface, OwnableInterface):
    def __init__(self) -> None:
        # ownable state
        self.owner = Account()
        # upgradeable state
        self.contract_version = UInt64()
        self.deployment_version = UInt64()
        self.updatable = bool(1)

    @arc4.abimethod
    def set_version(
        self, contract_version: arc4.UInt64, deployment_version: arc4.UInt64
    ) -> None:
        assert Txn.sender == Global.creator_address, "must be creator"
        self.contract_version = contract_version.native
        self.deployment_version = deployment_version.native

    @arc4.baremethod(allow_actions=["UpdateApplication"])
    def on_update(self) -> None:
        ##########################################
        # WARNING: This app can be updated by the creator
        ##########################################
        assert Txn.sender == Global.creator_address, "must be creator"
        assert self.updatable == UInt64(1), "not approved"
        ##########################################

    ##############################################
    # function: approve_update
    # arguments:
    # - approval, approval status
    # purpose: approve update
    # pre-conditions
    # - only callable by owner
    # post-conditions:
    # - updatable set to approval
    ##############################################
    @arc4.abimethod
    def approve_update(self, approval: arc4.Bool) -> None:
        assert Txn.sender == self.owner, "must be owner"
        self.updatable = approval.native

    ##############################################


##################################################
# Lockable
#   allows contract to be lock network tokens
##################################################


class LockableInterface(ARC4Contract):
    """
    Interface for all methods of lockable contracts.
    This class defines the basic interface for all types of lockable contracts.
    Subclasses must implement these methods to provide concrete behavior

    Global State:
    - period, lockup period
    - initial, initial balance
    - deadline, deadline for lockup period configuration
    - period_seconds, seconds in a period
    - lockup_delay, lockup delay
    - vesting_delay, vesting delay
    - period_limit, period limit
    """

    def __init__(self) -> None:
        self.period = UInt64()  # 0
        self.initial = UInt64()  # 0
        self.deadline = UInt64()  # 0
        self.period_seconds = TemplateVar[UInt64]("PERIOD_SECONDS")  # ex) 2592000
        self.lockup_delay = TemplateVar[UInt64]("LOCKUP_DELAY")  # ex) 12
        self.vesting_delay = TemplateVar[UInt64]("VESTING_DELAY")  # ex) 12
        self.period_limit = TemplateVar[UInt64]("PERIOD_LIMIT")  # ex) 5
        self.distribution_count = TemplateVar[UInt64]("DISTRIBUTION_COUNT")  # ex) 12
        self.distribution_seconds = TemplateVar[UInt64](
            "DISTRIBUTION_SECONDS"
        )  # ex) 2592000

    @arc4.abimethod
    def preconfigure(self, period: arc4.UInt64, deadline: arc4.UInt64) -> None:
        """
        Preconfigure lockup period and deadline.
        """
        pass

    @arc4.abimethod
    def set_vesting_delay(self, vesting_delay: arc4.UInt64) -> None:
        """
        Set vesting delay. Should be called by creator.
        """
        pass

    @arc4.abimethod
    def set_total(self, funding: arc4.UInt64) -> None:
        """
        Set total funding. Should be called by creator.
        """
        pass

    @arc4.abimethod
    def setup(
        self, owner: arc4.Address, funder: arc4.Address, initial: arc4.UInt64
    ) -> None:
        """
        Setup lockup. Should be called by creator.
        """
        pass

    @arc4.abimethod
    def configure(self, period: arc4.UInt64) -> None:
        """
        Configure lockup period. Should be called by owner.
        """
        pass

    @arc4.abimethod
    def withdraw(self, amount: arc4.UInt64) -> UInt64:
        """
        Withdraw funds from contract. Should be called by owner.
        """
        return UInt64()

    @arc4.abimethod
    def close(self) -> None:
        """
        Close contract. Should be called by owner or funder.
        """
        pass

    @subroutine
    def calculate_min_balance(self) -> UInt64:
        """
        Calculate minimum balance.
        """
        return UInt64()


##################################################
# Lockable
#   allows contract to be lock network tokens
# State:
#   hot state
#     - funder, who funded the contract
#     - period, lockup period
#     - funding, when funded
#     - total, total amount funded
#     - initial, initial balance
#     - deadline, funding deadline
#   warm state
#     - vesting_delay, vesting delay
#       periods from funding until lockup
#       vesting delay in early staking rewards
#       depends on period
#       ex)
#         vd = (p + 1) 2 / 3
#               , where p is between 1 and 18
#       otherwise cold
#   cold state
#     - parent_id, parent id
#     - period_seconds, period seconds
#     - lockup_delay, lockup delay
#     - period_limit, period limit
##################################################
class Lockable(LockableInterface, OwnableInterface, FundableInterface):
    def __init__(self) -> None:
        # ownable state
        self.owner = Account()
        # lockable state
        self.period = UInt64()
        self.initial = UInt64()
        self.deadline = UInt64()
        self.period_seconds = TemplateVar[UInt64]("PERIOD_SECONDS")
        self.lockup_delay = TemplateVar[UInt64]("LOCKUP_DELAY")
        self.vesting_delay = TemplateVar[UInt64]("VESTING_DELAY")
        self.period_limit = TemplateVar[UInt64]("PERIOD_LIMIT")
        self.distribution_count = TemplateVar[UInt64]("DISTRIBUTION_COUNT")
        self.distribution_seconds = TemplateVar[UInt64]("DISTRIBUTION_SECONDS")
        # prevent division by zero in calculate_mab_pure
        assert self.distribution_seconds > 0, "distribution seconds must be positive"
        # fundable state
        self.funder = Account()
        self.funding = UInt64()
        self.total = UInt64()

    @arc4.abimethod
    def preconfigure(self, period: arc4.UInt64, deadline: arc4.UInt64) -> None:
        """
        Preconfigure lockup period and deadline.
        """
        ##########################################
        assert self.owner == Global.zero_address, "owner not initialized"
        assert self.funder == Global.zero_address, "funder not initialized"
        ##########################################
        assert Txn.sender == Global.creator_address, "must be creator"
        ##########################################
        self.period = period.native
        self.deadline = deadline.native

    @arc4.abimethod
    def set_vesting_delay(self, vesting_delay: arc4.UInt64) -> None:
        """
        Set vesting delay.
        """
        ##########################################
        assert self.owner == Global.zero_address, "owner not initialized"
        assert self.funder == Global.zero_address, "funder not initialized"
        ##########################################
        assert Txn.sender == Global.creator_address, "must be creator"
        ##########################################
        self.vesting_delay = vesting_delay.native

    @arc4.abimethod
    def set_total(self, funding: arc4.UInt64) -> None:
        """
        Set total funding.
        """
        ##########################################
        assert self.owner == Global.zero_address, "owner not initialized"
        assert self.funder == Global.zero_address, "funder not initialized"
        ##########################################
        assert Txn.sender == Global.creator_address, "must be creator"
        ##########################################
        self.total = funding.native

    @arc4.abimethod
    def setup(
        self,
        owner: arc4.Address,
        funder: arc4.Address,
        initial: arc4.UInt64,
    ) -> None:
        ##########################################
        assert self.owner == Global.zero_address, "owner not initialized"
        assert self.funder == Global.zero_address, "funder not initialized"
        ##########################################
        assert Txn.sender == Global.creator_address, "must be creator"
        ##########################################
        self.owner = owner.native
        self.funder = funder.native
        self.initial = initial.native

    @arc4.abimethod
    def configure(self, period: arc4.UInt64) -> None:
        ##########################################
        assert self.funding == 0, "funding not initialized"
        assert self.total == 0, "total not initialized"
        ##########################################
        assert Txn.sender == self.owner, "must be owner"
        ##########################################
        assert period <= TemplateVar[UInt64]("PERIOD_LIMIT")
        assert period >= 0
        ##########################################
        assert self.deadline > Global.latest_timestamp, "deadline not passed"
        ##########################################
        self.period = period.native

    ##############################################
    # function: withdraw
    # arguments:
    # - amount
    # returns: min balance
    # purpose: extract funds from contract
    # pre-conditions
    # - only callable by owner
    # - let balance be the current balance of the
    #   contract
    # - balance - amount >= min_balance
    #   (fee paid in appl txn)
    # post-conditions:
    # - transfer amount from the contract account
    #   to owner
    # notes: costs 2 fees
    ##############################################
    @arc4.abimethod
    def withdraw(self, amount: arc4.UInt64) -> UInt64:
        """
        Withdraw funds from contract.
        """
        ##########################################
        assert Txn.sender == self.owner, "must be owner"
        ##########################################
        if self.funding > 0:
            min_balance = self.calculate_min_balance()
            available_balance = get_available_balance()
            assert available_balance - amount.native >= min_balance, "balance available"
            if amount > 0:
                itxn.Payment(amount=amount.native, receiver=Txn.sender, fee=0).submit()
            return min_balance
        else:
            min_balance = self.total
            available_balance = get_available_balance()
            assert available_balance - amount.native >= min_balance, "balance available"
            if amount > 0:
                itxn.Payment(amount=amount.native, receiver=Txn.sender, fee=0).submit()
            return min_balance

    ##############################################
    # function: close
    # purpose: deletes contract
    # pre-conditions:
    # - min balance is 0
    # post-conditions:
    # - contract is deleted
    # - account closed out to owner if it has a balance
    # notes:
    # - should be alled with onCompletion
    #   deleteApplication
    ##############################################
    @arc4.abimethod(allow_actions=[OnCompleteAction.DeleteApplication])
    def close(self) -> None:
        ###########################################
        assert self.funding > 0, "funded"
        ###########################################
        assert self.calculate_min_balance() == 0, "min balance not zero"
        ###########################################
        assert (
            Txn.sender == self.owner or Txn.sender == self.funder
        ), "must be owner or funder"
        ###########################################
        close_offline_on_delete(self.owner)

    ##############################################
    # function: min_balance (internal)
    # arguments: None
    # purpose: calcualte minimum balance
    # pre-conditions: None
    # post-conditions: None
    # notes:
    # - let period = number of months to to lockup
    #       total = total amount intially funded (airdrop + lockup bonus)
    #       y = vesting delay in months
    #       p = 1 / (self.period x 12) or 1 / (period)
    # - mimumum balance =
    #     total x min(1, p x max(0, (period - (now() - funding + y x seconds-in-month)) / seconds-in-month))
    ##############################################
    @subroutine
    def calculate_min_balance(self) -> UInt64:
        now: UInt64 = Global.latest_timestamp
        min_balance: UInt64 = calculate_mab_pure(
            now,
            self.vesting_delay,
            self.period_seconds,
            self.lockup_delay,
            self.period,
            self.funding,
            self.total,
            self.distribution_count,
            self.distribution_seconds,
        )
        return min_balance


##################################################
# Receiver
#   reference to messenger
##################################################


class ReceiverInterface(ARC4Contract):
    """
    Interface for all abimethods of receiver contract.
    """

    def __init__(self) -> None:
        self.messenger_id = UInt64()


class Receiver(ReceiverInterface):
    def __init__(self) -> None:
        self.messenger_id = TemplateVar[UInt64]("MESSENGER_ID")


##################################################
# Messenger
#   emits events
##################################################


class MessengerInterface(ARC4Contract):
    """
    Interface for all abimethods of messenger contract.
    """

    @arc4.abimethod
    def partkey_broastcast(
        self,
        address: arc4.Address,
        vote_k: Bytes32,
        sel_k: Bytes32,
        vote_fst: arc4.UInt64,
        vote_lst: arc4.UInt64,
        vote_kd: arc4.UInt64,
        sp_key: Bytes64,
    ) -> None:
        """
        Broastcast partkey information.
        """
        pass


class Messenger(MessengerInterface, Upgradeable):
    def __init__(self) -> None:
        # upgradeable state
        self.contract_version = UInt64()  # 0
        self.deployment_version = UInt64()  # 0
        self.updatable = bool(1)  # 1 (Default unlocked)

    @arc4.abimethod
    def partkey_broastcast(
        self,
        address: arc4.Address,
        vote_k: Bytes32,
        sel_k: Bytes32,
        vote_fst: arc4.UInt64,
        vote_lst: arc4.UInt64,
        vote_kd: arc4.UInt64,
        sp_key: Bytes64,
    ) -> None:
        arc4.emit(
            MessagePartKeyInfo(
                arc4.Address(Txn.sender),
                PartKeyInfo(
                    address, vote_k, sel_k, vote_fst, vote_lst, vote_kd, sp_key
                ),
            )
        )


##################################################
# Deployable
#   ensures that contract is created by factory
#   and recorded
##################################################


class DeployableInterface(ARC4Contract):
    """
    Interface for all abimethods of deployable contract.
    """

    def __init__(self) -> None:
        self.parent_id = UInt64()

    @arc4.abimethod(create="require")
    def on_create(self) -> None:
        """
        Execute on create.
        """
        pass


class Deployable(DeployableInterface):
    def __init__(self) -> None:
        super().__init__()

    @arc4.baremethod(create="require")
    def on_create(self) -> None:
        caller_id = Global.caller_application_id
        assert caller_id > 0, "must be created by factory"
        self.parent_id = caller_id


##################################################
# Airdrop
#   facilitates airdrop staking
##################################################


class Airdrop(
    Lockable, Ownable, Fundable, Deployable, Stakeable, Upgradeable, Receiver
):
    def __init__(self) -> None:
        # deployable state
        self.parent_id = UInt64()
        # stakeable state
        self.delegate = Account()
        self.stakeable = bool(1)
        # upgradeable state
        self.contract_version = UInt64()
        self.deployment_version = UInt64()
        self.updatable = bool(1)
        # ownable state
        self.owner = Account()
        # lockable state
        self.period = UInt64()
        self.initial = UInt64()
        self.deadline = UInt64()
        self.period_seconds = TemplateVar[UInt64]("PERIOD_SECONDS")
        self.lockup_delay = TemplateVar[UInt64]("LOCKUP_DELAY")
        self.vesting_delay = TemplateVar[UInt64]("VESTING_DELAY")
        self.period_limit = TemplateVar[UInt64]("PERIOD_LIMIT")
        self.distribution_count = TemplateVar[UInt64]("DISTRIBUTION_COUNT")
        self.distribution_seconds = TemplateVar[UInt64]("DISTRIBUTION_SECONDS")
        # fundable state
        self.funder = Account()
        self.funding = UInt64()
        self.total = UInt64()
        # receiver state
        self.messenger_id = TemplateVar[UInt64]("MESSENGER_ID")

    # override fundable abort_funding abimethod
    #   close offline on delete to owner
    @arc4.abimethod(allow_actions=[OnCompleteAction.DeleteApplication])
    def abort_funding(self) -> None:
        ##########################################
        assert (
            Txn.sender == self.funder or Txn.sender == self.owner
        ), "must be funder or owner"
        ##########################################
        assert self.funding == UInt64(0)
        ##########################################
        close_offline_on_delete(self.owner)


##################################################
# BaseFactory
#   factory for airdrop also serves as a base for
#   upgrading contracts if applicable
##################################################


class BaseFactory(Upgradeable):
    """
    Base factory for all factories.
    """

    def __init__(self) -> None:
        """
        Initialize factory.
        """
        # upgradeable state
        self.contract_version = UInt64()  # 0
        self.deployment_version = UInt64()  # 0
        self.updatable = bool(1)  # 1 (Default unlocked)

        ##############################################
        # @arc4.abimethod
        # def update(self) -> None:
        #      pass
        ##############################################
        # @arc4.abimethod
        # def remote_update(self, app_id: arc4.UInt64) -> None:
        #     pass
        ##############################################
        # @arc4.abimethod
        # def create(self, *args) -> UInt64:
        #    return UInt64()
        ##############################################

    @subroutine
    def get_initial_payment(self) -> UInt64:
        """
        Get initial payment.
        """
        payment_amount = require_payment(Txn.sender)
        mbr_increase = UInt64(677500)
        min_balance = op.Global.min_balance  # 100000
        assert (
            payment_amount >= mbr_increase + min_balance
        ), "payment amount accurate"  # 777500
        initial = payment_amount - mbr_increase - min_balance
        return initial


##################################################
# AirdropFactory
#   factory for airdrop also serves as a base for
#   upgrading contracts if applicable
##################################################


class AirdropFactory(BaseFactory):
    """
    Factory for airdrop requiring lockup period
    configuration and funding.
    """

    def __init__(self) -> None:
        super().__init__()

    @arc4.abimethod
    def create(
        self,
        owner: arc4.Address,
        funder: arc4.Address,
        deadline: arc4.UInt64,
        initial: arc4.UInt64,
    ) -> UInt64:
        """
        Create airdrop.

        Arguments:
        - owner, who is the beneficiary
        - funder, who funded the contract
        - deadline, funding deadline
        - initial, initial funded value not including lockup bonus

        Returns:
        - app id
        """
        ##########################################
        self.get_initial_payment()
        ##########################################
        base_app = arc4.arc4_create(Airdrop).created_app
        arc4.abi_call(Airdrop.preconfigure, UInt64(0), deadline, app_id=base_app)
        itxn.Payment(
            receiver=base_app.address, amount=op.Global.min_balance, fee=0  # 100000
        ).submit()
        arc4.abi_call(Airdrop.setup, owner, funder, initial, app_id=base_app)
        # configured by owner
        # funder
        #   fill
        #   set funding
        # vesting
        # lockup
        # done
        ##########################################
        return base_app.id


##################################################
# VanillaFactory
#   factory for staking contract vesting and lockup
##################################################


# class VanillaFactory(BaseFactory):
#     """
#     Factory for staking contract without vesting and lockup.
#     """

#     def __init__(self) -> None:
#         super().__init__()

#     @arc4.abimethod
#     def create(self, delegate: arc4.Address) -> UInt64:
#         ##########################################
#         owner = Txn.sender
#         initial = self.get_initial_payment()
#         ##########################################
#         base_app = arc4.arc4_create(Airdrop).created_app
#         itxn.Payment(
#             receiver=base_app.address,
#             amount=initial + op.Global.min_balance,  # initial + 100000
#             fee=0,
#         ).submit()
#         arc4.abi_call(
#             Airdrop.preconfigure, UInt64(0), Global.latest_timestamp, app_id=base_app
#         )
#         arc4.abi_call(Airdrop.set_delegate, delegate, app_id=base_app)
#         arc4.abi_call(Airdrop.set_total, initial, app_id=base_app)
#         arc4.abi_call(
#             Airdrop.setup,
#             owner,  # owner
#             Global.current_application_address,  # funder
#             initial,
#             app_id=base_app,
#         )
#         arc4.abi_call(Airdrop.set_funding, Global.latest_timestamp, app_id=base_app)
#         # withdraw particpate
#         # close
#         ##########################################
#         return base_app.id


##################################################
# StakeRewardFactory
#   factory for stake reward
##################################################
# class StakeRewardFactory(BaseFactory):
#     """
#     Factory for stake reward.
#     """

#     def __init__(self) -> None:
#         super().__init__()

#     @arc4.abimethod
#     def create(
#         self,
#         owner: arc4.Address,
#         funder: arc4.Address,
#         delegate: arc4.Address,
#         period: arc4.UInt64,
#     ) -> UInt64:
#         """
#         Create stake reward.

#         Arguments:
#         - owner, who is the beneficiary
#         - funder, who funded the contract
#         - delegate, who is the delegate
#         - period, lockup period

#         Returns:
#         - app id
#         """
#         ##########################################
#         initial = self.get_initial_payment()
#         ##########################################
#         base_app = arc4.arc4_create(Airdrop).created_app
#         itxn.Payment(
#             receiver=base_app.address, amount=initial + op.Global.min_balance, fee=0
#         ).submit()
#         # common in stake reward
#         #   set delgate and prevent furture changes by owner
#         arc4.abi_call(
#             Airdrop.preconfigure, period, Global.latest_timestamp, app_id=base_app
#         )
#         arc4.abi_call(Airdrop.set_delegate, delegate, app_id=base_app)
#         # common in airdrop
#         #   set owner and funder locking out further changes by creator
#         arc4.abi_call(
#             Airdrop.setup,
#             owner,
#             funder,
#             initial,
#             app_id=base_app,
#         )
#         # funder
#         #   fill
#         #   set funding
#         # vesting, lockup
#         #   withdraw
#         #   participate
#         # close
#         ##########################################
#         return base_app.id


##################################################
# EarlyStakeRewardFactory
#   factory for early stake reward
##################################################


# class EarlyStakeRewardFactory(BaseFactory):
#     def __init__(self) -> None:
#         """
#         Factory for early stake reward.
#         """

#     @arc4.abimethod
#     def create(
#         self,
#         owner: arc4.Address,
#         funder: arc4.Address,
#         delegate: arc4.Address,
#         period: arc4.UInt64,
#     ) -> UInt64:
#         """
#         Create early stake reward.

#         Arguments:
#         - owner, who is the beneficiary
#         - funder, who funded the contract
#         - delegate, who is the delegate
#         - period, lockup period

#         Returns:
#         - app id
#         """
#         ##########################################
#         initial = self.get_initial_payment()
#         ##########################################
#         base_app = arc4.arc4_create(Airdrop).created_app
#         itxn.Payment(
#             receiver=base_app.address, amount=initial + op.Global.min_balance, fee=0
#         ).submit()
#         # common in stake reward
#         #   set delgate and prevent furture changes by owner
#         arc4.abi_call(
#             Airdrop.preconfigure, period, Global.latest_timestamp, app_id=base_app
#         )
#         arc4.abi_call(Airdrop.set_delegate, delegate, app_id=base_app)
#         # unique to early staking
#         #   locks initial deposit to be vested
#         arc4.abi_call(Airdrop.set_total, initial, app_id=base_app)
#         # unique to early staking
#         #   variable vesting delay adjustment
#         arc4.abi_call(
#             Airdrop.set_vesting_delay,
#             (period.native + UInt64(1)) * UInt64(2) // UInt64(3),
#             app_id=base_app,
#         )
#         # common in airdrop
#         arc4.abi_call(
#             Airdrop.setup,
#             owner,
#             funder,
#             initial,
#             app_id=base_app,
#         )
#         # funder
#         #   fill, set funding
#         # vesting, lockup
#         #   withdraw, participate
#         # close
#         #########################################
#         return base_app.id
