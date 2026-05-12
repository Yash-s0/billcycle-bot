from aiogram.fsm.state import State, StatesGroup


class AddCardStates(StatesGroup):
    bank_name = State()
    card_name = State()
    last_four = State()
    billing_day = State()
    due_day = State()
    credit_limit = State()
    notes = State()


class AddTransactionStates(StatesGroup):
    card = State()
    amount = State()
    merchant = State()
    category = State()
    txn_date = State()
    has_discount = State()
    discount_amount = State()
    ownership = State()
    person_name = State()
    already_paid = State()


class MarkPaidStates(StatesGroup):
    person = State()
    transaction = State()
    amount = State()
    notes = State()


class DeleteTransactionStates(StatesGroup):
    transaction_id = State()
    confirm = State()


class MonthlyReportStates(StatesGroup):
    month = State()


class SettingsStates(StatesGroup):
    main = State()
