from aiogram.fsm.state import State, StatesGroup


class AddCardStates(StatesGroup):
    bank_name = State()
    card_name = State()
    billing_day = State()
    due_day = State()
    credit_limit = State()
    notes = State()


class AddTransactionStates(StatesGroup):
    card = State()
    amount = State()
    review = State()
    input_optional = State()


class MarkPaidStates(StatesGroup):
    person = State()
    transaction = State()
    amount = State()
    notes = State()


class DeleteTransactionStates(StatesGroup):
    menu = State()
    confirm = State()


class MonthlyReportStates(StatesGroup):
    month = State()


class SettingsStates(StatesGroup):
    main = State()
