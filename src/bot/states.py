from aiogram.fsm.state import State, StatesGroup


class AddCardStates(StatesGroup):
    bank_name = State()
    card_name = State()
    billing_day = State()
    due_day = State()
    credit_limit = State()
    notes = State()


class AddTransactionStates(StatesGroup):
    account = State()
    mode = State()
    card = State()
    amount = State()
    review = State()
    input_optional = State()


class MarkPaidStates(StatesGroup):
    card = State()
    action = State()
    amount = State()


class EditCardStates(StatesGroup):
    card = State()
    action = State()
    field = State()
    input_value = State()
    confirm_delete = State()


class EditTransactionStates(StatesGroup):
    mode = State()
    card = State()
    transaction = State()
    action = State()
    field = State()
    input_value = State()
    confirm_delete = State()


class MonthlyReportStates(StatesGroup):
    month = State()


class ReportStates(StatesGroup):
    menu = State()
    month = State()
    custom_from = State()
    custom_to = State()


class SettingsStates(StatesGroup):
    main = State()
    reminder_time_input = State()
